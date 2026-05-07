# AI Companion Local

> 从你的微信 / QQ 聊天记录中，复活一个懂你、会回忆、会发表情包的 AI 伴侣——完全本地运行，隐私优先。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 项目简介

本项目旨在将个人聊天记录转化为一个风格高度拟人、具备长期记忆的本地 AI 对话伴侣。通过 **"你说什么 → Ta 如何回应"的对话对分析** 提取互动模式，用 QLoRA 微调技术克隆说话语气，结合向量数据库实现往事回忆，营造与真人好友聊天的沉浸体验。

**核心特性：**
- **隐私至上**：聊天记录预处理、模型微调、对话推理均在本地完成，不上传任何数据
- **人格 Skill 生成**：从聊天记录自动生成 AI 角色设定文件，可直接用于 ChatGPT/DeepSeek 等云端模型（cloud-safe 版本不含原文对话）
- **风格克隆**：基于 `Qwen2.5-7B`，利用 `LLaMA-Factory` 进行 QLoRA 微调，精准模仿目标人物的语气与用词习惯
- **长期记忆**：使用 `ChromaDB` 向量存储对话历史，让 AI 记住过往的关键事件与细节
- **表情包同步**：AI 回复中自动嵌入情感标签（如 `[happy]`），客户端可根据标签映射本地表情包
- **跨平台数据诊断**：支持 Windows / macOS / Linux / WSL2 的微信聊天数据路径自动探测
- **模块化设计**：数据清洗、Skill 生成、微调、记忆检索、对话引擎各模块解耦，便于二次开发

## 适用场景

- 个人留念与纪念
- AI 陪伴应用的原型验证
- 本地大模型微调技术学习与实践

## 项目结构

```
AI-Companion-Local/
├── scripts/
│   ├── wizard.py              # 交互式 CLI 向导（零基础用户入口）
│   ├── diagnose.py            # 跨平台微信/QQ 数据路径探测 (Win/Mac/Linux/WSL2)
│   ├── clean_data.py          # 聊天记录清洗、说话人识别、Session 分段
│   ├── generate_skill.py      # 人格 Skill 一键生成入口
│   ├── parsers/               # 多格式聊天记录解析器
│   │   ├── base.py            #   Message 数据结构 + 共享时间解析
│   │   ├── wechat_csv.py      #   微信 CSV 解析（兼容新旧版导出格式）
│   │   └── qq_json.py         #   QQ JSON 导出解析
│   └── skill_gen/             # 人格 Skill 生成引擎
│       ├── pair_builder.py    #   上下文窗口对话对构建器
│       ├── report_generator.py #   双版本 Markdown 报告生成
│       └── analyzers/         #   互动模式分析器（5 维度）
│           ├── language_style.py    #   语言风格
│           ├── reply_pattern.py     #   回复模式
│           ├── emotion_dynamic.py   #   情感互动
│           ├── relationship_role.py #   关系角色
│           └── content_themes.py    #   话题偏好
├── bot/
│   ├── main.py                # CLI 对话入口（ChatML + Ollama）
│   ├── emotion_engine.py      # 情感关键词检测引擎
│   ├── memory/
│   │   └── vector_store.py    # ChromaDB 长期记忆接口
│   └── config.yaml            # Ollama 连接与记忆配置
├── finetune/
│   └── configs/
│       └── qlora_config.yaml  # LLaMA-Factory QLoRA 微调配置
├── data/
│   ├── raw/                   # 原始导出聊天记录 (.gitignore)
│   └── processed/             # 清洗后数据 + Skill 文件 (.gitignore)
├── models/                    # 微调后模型文件 (.gitignore)
├── chroma_db/                 # ChromaDB 持久化数据 (.gitignore)
├── .gitignore
├── LICENSE
├── requirements.txt
└── README.md
```

## 技术栈

- **模型微调**：LLaMA-Factory + QLoRA + Qwen2.5-7B
- **对话框架**：可集成 AstrBot 或自研 WebSocket 服务
- **记忆存储**：ChromaDB (向量检索，余弦相似度)
- **数据预处理**：Python (pathlib, argparse, csv, json) + 平台原生接口
- **本地推理**：Ollama + OpenAI 兼容 API

## 环境要求

- **操作系统**：Windows 10/11、macOS、Linux、WSL2
- **Python**：3.11 及以上
- **GPU**（仅微调需要）：推荐 NVIDIA RTX 3060 及以上，至少 8GB 显存
- **内存**：16GB 及以上
- **软件依赖**：Ollama（仅对话机器人需要），Git

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Eliauk-Lik/AI-Companion-Local.git
cd AI-Companion-Local
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 导出聊天记录

> 微信 4.0 及以上版本不再支持直接导出 CSV，推荐使用开源工具 WeFlow。

**微信（推荐：WeFlow）：**

[WeFlow](https://github.com/hicccc77/WeFlow) 是一个完全本地运行的微信聊天记录查看与导出工具，支持微信 4.0+。

1. 前往 [WeFlow Releases](https://github.com/hicccc77/WeFlow/releases) 下载对应系统的安装包
2. 启动 WeFlow，选择要导出的聊天对话
3. 导出为 CSV 格式，保存到本地
4. 将 CSV 文件放到项目的 `data/raw/` 目录下

> WeFlow 支持 Windows / macOS / Linux，MIT 开源协议，数据完全本地处理。

**QQ：**
1. 打开 QQ → `设置` → `安全设置` → `消息管理` → `导出消息记录`
2. 选择 JSON 格式导出

### 4. 运行交互式向导（推荐）

```bash
python scripts/wizard.py
```

向导会引导你完成：选择目标对象 → 提供聊天文件 → 自动清洗处理，全程交互式问答。

### 5. 生成人格 Skill 文件

```bash
python scripts/generate_skill.py
```

输出两个版本：
- `skill_<name>_cloud_safe.md` — 仅统计描述，可安全粘贴到 ChatGPT
- `skill_<name>_local_full.md` — 含对话片段，仅供本地 Ollama 使用

### 6. 或逐步手动运行

```bash
# 步骤1：诊断微信数据路径（可选）
python scripts/diagnose.py

# 步骤2：清洗聊天记录
python scripts/clean_data.py --input data/raw/wechat.csv

# 步骤3：生成 Skill 文件
python scripts/generate_skill.py
```

### 7. 启动 AI 对话伴侣

本项目支持多种本地推理方案，按上手难度排序推荐。

#### 方案一：Ollama（推荐，默认集成）

[Ollama](https://ollama.com) 是最易用的本地 LLM 推理工具，底层基于 llama.cpp，
一行命令即可运行模型，并提供 OpenAI 兼容 API。

```bash
# 1. 安装 Ollama（macOS/Linux 一行，Windows 下载安装包）
curl -fsSL https://ollama.com/install.sh | sh

# 2. 启动服务
ollama serve

# 3. 下载模型（推荐 qwen2.5:7b，8GB 显存可流畅运行）
ollama pull qwen2.5:7b

# 4. 启动 AI 对话伴侣
python bot/main.py
```

`bot/config.yaml` 中的默认配置指向 `localhost:11434`，与 Ollama 默认端口一致，
开箱即用。

#### 方案二：llama.cpp（进阶，性能最优）

[llama.cpp](https://github.com/ggerganov/llama.cpp) 是 Ollama 的底层推理引擎，
直接使用可省去 ~0.2GB VRAM 开销、获得 ~6% 的速度提升。适合追求极致性能或
想在低配设备（树莓派、老笔记本）上运行的用户。

```bash
# 1. 克隆并编译
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && make -j

# 2. 启动 OpenAI 兼容 API（端口 8080）
./llama-server -m models/qwen2.5-7b-q4_k_m.gguf --port 8080
```

修改 `bot/config.yaml` 将 endpoint 指向 `http://localhost:8080` 即可对接。

> Ollama 和 LM Studio（GUI 工具）底层也是 llama.cpp。三者的速度差距在 10% 以内，
> 普通用户直接用 Ollama 即可，不需要折腾编译。

#### 部署微调后的模型

完成 QLoRA 微调后，将模型部署为 GGUF + Ollama：

```bash
# 1. 合并 LoRA 适配器
python -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
base = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-7B-Instruct')
model = PeftModel.from_pretrained(base, 'finetune/output/checkpoint-xxx')
model = model.merge_and_unload()
model.save_pretrained('./models/companion-merged')
AutoTokenizer.from_pretrained('Qwen/Qwen2.5-7B-Instruct').save_pretrained('./models/companion-merged')
"

# 2. 转换为 GGUF
pip install gguf
python llama.cpp/convert_hf_to_gguf.py ./models/companion-merged --outtype f16

# 3. 量化（Q4_K_M 是 8GB 显存的最佳平衡点）
llama.cpp/build/bin/llama-quantize ./models/companion-merged-f16.gguf Q4_K_M

# 4. 注册到 Ollama
cat > Modelfile << EOF
FROM ./models/companion-merged-Q4_K_M.gguf
SYSTEM "$(cat data/processed/skill_xxx_cloud_safe.md)"
PARAMETER temperature 0.8
PARAMETER repeat_penalty 1.1
EOF
ollama create companion -f Modelfile

# 5. 运行
ollama run companion
```

### VRAM 估算参考

| 模型规模 | Q4_K_M 大小 | 推荐显存 | 适用硬件 |
|----------|------------|----------|----------|
| 1.5B | ~1.0 GB | 4 GB | 无独显笔记本 |
| 7B | ~4.7 GB | 8 GB | RTX 3060/4060 |
| 14B | ~8.5 GB | 12 GB | RTX 4070+ |
| 32B | ~20 GB | 24 GB | RTX 3090/4090 |

## WSL2 用户注意

在 WSL2 中运行时，`diagnose.py` 会自动检测 Windows 侧的微信数据目录（通过 `/mnt/c/` 路径）。导出聊天记录的 CSV 文件后，在 WSL2 中可通过 `/mnt/c/Users/你的用户名/...` 路径访问。

## 隐私与伦理声明

- **所有数据处理在本地完成**，代码不包含任何云端上传逻辑
- `.gitignore` 已配置排除 `data/raw/`、`data/processed/`、`models/`、`chroma_db/`、`config_local.yaml` 等敏感目录
- 生成的人格 Skill 文件提供两个版本：`cloud_safe`（无原文对话，可安全粘贴到云端 LLM）和 `local_full`（含对话片段，仅本地使用）
- 每个 Skill 文件头部嵌入了伦理使用声明，明确使用边界

## 开发路线图

- [x] Phase 1 — 数据基础层：跨平台路径探测、多格式解析、交互式说话人识别、CLI 向导
- [x] Phase 2 — 核心分析引擎：上下文窗口对话对构建、5 维度互动模式分析、双版本 Skill Markdown 生成
- [ ] Phase 3 — 体验增强：bot 集成 Skill 文件、Mac/Linux QQ 支持、AstrBot Provider、微调文档

## 开源协议

MIT License — 详见 [LICENSE](LICENSE)
