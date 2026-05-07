#!/usr/bin/env python3
"""
AI Companion 命令行对话入口

功能：
- 加载本地配置（Ollama 地址、模型名）
- 集成向量记忆存储（ChromaDB）
- 集成表情标签引擎
- 调用 Ollama 生成回复，并附加上下文记忆
- 提供简单的命令行交互界面

使用方法：
    python bot/main.py
"""

import os
import sys
import yaml
import requests
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.memory.vector_store import get_memory_store
from bot.emotion_engine import EmotionEngine


def _detect_wsl_host(endpoint: str) -> str:
    """WSL2 环境下自动检测 Windows 宿主 IP，替代 localhost"""
    if "localhost" not in endpoint and "127.0.0.1" not in endpoint:
        return endpoint
    # 仅在 WSL2 中尝试自动检测
    try:
        with open("/proc/version") as f:
            if "microsoft" not in f.read().lower() and "wsl" not in f.read().lower():
                return endpoint
    except OSError:
        return endpoint
    # 从路由表获取 Windows 宿主 IP
    import subprocess, re
    try:
        result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
        m = re.search(r"via\s+([\d.]+)", result.stdout)
        if m:
            host_ip = m.group(1)
            new_endpoint = endpoint.replace("localhost", host_ip).replace("127.0.0.1", host_ip)
            print(f"🔍 WSL2 检测到 Windows 宿主 IP: {host_ip}，使用端点: {new_endpoint}")
            return new_endpoint
    except Exception:
        pass
    print("⚠️ WSL2 环境下 localhost 可能无法访问 Ollama，请手动设置 OLLAMA_HOST=0.0.0.0")
    return endpoint


class AIChatBot:
    def __init__(self, config_path: str = "bot/config.yaml"):
        """初始化聊天机器人"""
        self.config = self._load_config(config_path)
        self.ollama_endpoint = _detect_wsl_host(self.config["ollama"]["endpoint"])
        self.model = self.config["ollama"]["model"]
        self.memory_store = get_memory_store(
            self.config.get("memory", {}).get("persist_dir", "./chroma_db")
        )
        self.top_k = self.config.get("memory", {}).get("top_k", 5)
        self.emotion_engine = EmotionEngine() if self.config.get("emotion", {}).get("enable", True) else None

        # 对话历史（当前会话的短期记忆）
        self.conversation_history: List[Dict[str, str]] = []

        # 加载人格 Skill 文件作为系统提示词
        self.system_prompt = self._load_skill()

    def _load_config(self, config_path: str) -> Dict:
        """加载 YAML 配置文件"""
        config_file = Path(config_path)
        if not config_file.exists():
            print(f"⚠️ 配置文件 {config_path} 不存在，使用默认配置")
            return {
                "ollama": {"endpoint": "http://localhost:11434", "model": "qwen2.5-coder:7b"},
                "memory": {"persist_dir": "./chroma_db", "top_k": 5},
                "emotion": {"enable": True}
            }
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _load_skill(self) -> str:
        """加载人格 Skill 文件作为系统提示词

        优先级：config 中指定的路径 > 自动检测 data/processed/ 下的 cloud_safe 文件 > 默认提示词
        """
        skill_path = self.config.get("personality", {}).get("skill_file", "")

        # 如果未指定，自动检测
        if not skill_path:
            processed_dir = Path("data/processed")
            if processed_dir.exists():
                candidates = list(processed_dir.glob("skill_*_cloud_safe.md"))
                if candidates:
                    skill_path = str(candidates[0])
                    print(f"📄 自动检测到 Skill 文件: {skill_path}")

        # 读取 Skill 文件
        if skill_path:
            skill_file = Path(skill_path)
            if skill_file.exists():
                content = skill_file.read_text(encoding="utf-8")
                # 从第一个 ## 标题开始取，跳过伦理声明头部
                idx = content.find("\n## ")
                if idx != -1:
                    content = content[idx + 1:]
                print(f"✅ 已加载人格 Skill: {skill_path}")
                return content.strip()

        # 默认提示词
        print("ℹ️ 未找到 Skill 文件，使用默认系统提示词。")
        print("   提示：运行 python scripts/generate_skill.py 生成人格文件。")
        return """你是一个贴心的AI伴侣，正在与一位熟悉的朋友聊天。你的回复应该：
- 自然、亲切，像真人朋友一样
- 回答用户的问题，并适当展开话题
- 如果提到了过去的回忆，可以自然地提及
- 回复长度适中，避免机械重复"""

    def _retrieve_context(self, user_input: str) -> str:
        """从长期记忆中检索相关历史对话，拼接成上下文字符串"""
        memories = self.memory_store.retrieve_relevant(user_input, top_k=self.top_k)
        if not memories:
            return ""
        context = "【以下是你们过去的对话回忆，可参考但不必逐字重复】\n"
        for i, mem in enumerate(memories, 1):
            context += f"{i}. {mem}\n"
        return context

    def _build_prompt(self, user_input: str, context: str) -> str:
        """构建发送给模型的完整提示词（采用 ChatML 格式，对 Qwen 系列更友好）"""
        system_prompt = self.system_prompt

        # 构建消息列表
        messages = []
        messages.append({"role": "system", "content": system_prompt})

        # 加入长期记忆上下文（如果有）
        if context:
            messages.append({"role": "system", "content": context})

        # 加入近期对话历史（最多10条，避免过长）
        for msg in self.conversation_history[-10:]:
            role = "user" if msg["role"] == "用户" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

        # 当前用户消息
        messages.append({"role": "user", "content": user_input})

        # 手动构造 ChatML 格式提示词
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += f"<|im_start|>system\n{msg['content']}<|im_end|>\n"
            elif msg["role"] == "user":
                prompt += f"<|im_start|>user\n{msg['content']}<|im_end|>\n"
            elif msg["role"] == "assistant":
                prompt += f"<|im_start|>assistant\n{msg['content']}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"  # 引导模型开始生成回复

        return prompt

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """调用 Ollama API 生成回复（优化参数以减少重复）"""
        url = f"{self.ollama_endpoint}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,          # 稍微提高随机性
                "top_p": 0.95,
                "top_k": 40,
                "repeat_penalty": 1.1,       # 惩罚重复
                "repeat_last_n": 64,
                "num_predict": 512,          # 限制生成长度
                "stop": ["<|im_end|>", "<|im_start|>"],  # 停止标记
            }
        }
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.ConnectionError:
            print("\n❌ 无法连接到 Ollama，请确保 Ollama 正在运行。")
            print(f"   尝试连接地址: {self.ollama_endpoint}")
            return None
        except Exception as e:
            print(f"\n❌ 调用 Ollama 出错: {e}")
            return None

    def chat(self, user_input: str) -> Optional[str]:
        """处理单轮对话"""
        # 1. 检索长期记忆
        context = self._retrieve_context(user_input)

        # 2. 构建提示词
        prompt = self._build_prompt(user_input, context)

        # 3. 调用模型
        reply = self._call_ollama(prompt)
        if reply is None:
            return None

        # 4. 添加表情标签
        if self.emotion_engine:
            reply = self.emotion_engine.enrich_response(reply)

        # 5. 存储到长期记忆
        self.memory_store.add_memory(user_input, reply)

        # 6. 更新短期对话历史
        self.conversation_history.append({"role": "用户", "content": user_input})
        self.conversation_history.append({"role": "助手", "content": reply})

        return reply

    def reset_memory(self):
        """清空短期对话历史（长期记忆保留）"""
        self.conversation_history = []
        print("🔄 短期对话历史已清空。")

    def run(self):
        """启动命令行交互循环"""
        print("\n" + "=" * 50)
        print("🤖 AI Companion 命令行对话")
        print("=" * 50)
        print(f"📌 当前模型: {self.model}")
        print(f"📌 记忆条数: {self.memory_store.collection.count()}")
        print("💡 输入 'quit' 或 'exit' 退出，输入 'clear' 清空短期记忆")
        print("-" * 50)

        while True:
            try:
                user_input = input("\n🧑 你: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n👋 再见！")
                break

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit"]:
                print("👋 再见！")
                break

            if user_input.lower() == "clear":
                self.reset_memory()
                continue

            # 显示思考中
            print("🤖 助手: ", end="", flush=True)
            reply = self.chat(user_input)
            if reply:
                print(reply)
            else:
                print("[回复生成失败，请检查 Ollama 服务]")


def main():
    # 切换到项目根目录，确保相对路径正确
    os.chdir(Path(__file__).parent.parent)
    bot = AIChatBot()
    bot.run()


if __name__ == "__main__":
    main()