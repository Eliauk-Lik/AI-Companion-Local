# AI Companion Local

> 从你的微信 / QQ 聊天记录中，复活一个懂你、会回忆、会发表情包的 AI 伴侣——完全本地运行，隐私优先。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 📌 项目简介

本项目旨在将个人聊天记录转化为一个风格高度拟人、具备长期记忆的本地 AI 对话伴侣。通过 QLoRA 微调技术克隆说话语气，结合向量数据库实现往事回忆，并支持在回复中自动触发对应的表情包，营造与真人好友聊天的沉浸体验。

**核心特性：**
- 🔒 **隐私至上**：聊天记录预处理、模型微调、对话推理均在本地完成，不上传任何数据。
- 🧠 **风格克隆**：基于 `Qwen2.5-7B` 或 `Qwen3.5-9B`，利用 `LLaMA-Factory` 进行 QLoRA 微调，精准模仿目标人物的语气与用词习惯。
- 📅 **长期记忆**：使用 `ChromaDB` 向量存储对话历史，让 AI 记住过往的关键事件与细节。
- 😊 **表情包同步**：AI 回复中自动嵌入情感标签（如 `[happy]`），客户端可根据标签映射本地表情包，还原真实聊天氛围。
- 🩺 **数据诊断**：内置微信聊天记录健康扫描工具，帮助用户识别并修复损坏的数据库文件，最大化数据完整度。
- 🧩 **模块化设计**：数据清洗、微调、记忆检索、对话引擎各模块解耦，便于二次开发与定制。

## 🚀 适用场景
- 个人留念与纪念
- AI 陪伴应用的原型验证
- 本地大模型微调技术学习与实践

## 🛠️ 技术栈
- **模型微调**：LLaMA-Factory + QLoRA + Qwen2.5-7B
- **对话框架**：可集成 AstrBot 或自研 WebSocket 服务
- **记忆存储**：ChromaDB (向量检索)
- **数据预处理**：Python (pandas, regex) + 聊天记录导出工具
- **本地推理**：Ollama + OpenAI 兼容 API

## 📋 环境要求

- **操作系统**：Windows 10/11（推荐），或 WSL2 (Debian/Ubuntu)
- **Python**：3.11 及以上
- **GPU**：推荐 NVIDIA RTX 3060 及以上，至少 8GB 显存
- **内存**：16GB 及以上
- **软件依赖**：Ollama，Git

## ⚙️ 快速开始

### 1. 克隆仓库并进入目录
```bash
git clone https://github.com/Eliauk-Lik/AI-Companion-Local.git
cd AI-Companion-Local