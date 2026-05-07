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

**微信：**
1. 打开微信 PC 版 → 进入目标聊天窗口
2. 点击右上角 `…` → `聊天记录` → `导出聊天记录`
3. 选择 CSV 格式，保存到本地

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

```bash
# 确保 Ollama 已启动并加载了模型
ollama serve
ollama pull qwen2.5:7b

# 启动对话
python bot/main.py
```

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
