#!/usr/bin/env python3
"""
QLoRA 微调脚本

基于 transformers + peft + bitsandbytes，在 8GB 显存上微调 Qwen2.5-7B。

用法：
    python scripts/train_qlora.py --train data/train.json --eval data/eval.json
    python scripts/train_qlora.py --train data/train.json --epochs 1
"""

import json
import os
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
)
from transformers.trainer_callback import EarlyStoppingCallback


def load_conversation_data(filepath: str) -> Dataset:
    """加载 LLaMA-Factory 格式的 conversation 数据，转为文本序列"""
    with open(filepath, encoding="utf-8") as f:
        records = json.load(f)

    texts = []
    for r in records:
        convs = r["conversations"]
        # 用 Qwen ChatML 格式拼接
        text = ""
        for c in convs:
            role = "user" if c["from"] == "human" else "assistant"
            text += f"<|im_start|>{role}\n{c['value']}<|im_end|>\n"
        texts.append(text.strip())

    return Dataset.from_dict({"text": texts})


def tokenize(examples, tokenizer, max_length=512):
    """Tokenize 文本（batched）"""
    result = tokenizer(
        examples["text"],
        truncation=True,
        padding="max_length",
        max_length=max_length,
    )
    result["labels"] = result["input_ids"].copy()
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="QLoRA 微调 Qwen2.5-7B")
    parser.add_argument("--train", default="data/train.json", help="训练数据")
    parser.add_argument("--eval", default="data/eval.json", help="验证数据")
    parser.add_argument("--model", default="/mnt/d/models/Qwen2.5-3B-Instruct", help="基座模型")
    parser.add_argument("--output", default="finetune/output", help="输出目录")
    parser.add_argument("--epochs", type=int, default=3, help="训练轮数")
    parser.add_argument("--batch-size", type=int, default=2, help="每卡 batch size")
    parser.add_argument("--grad-accum", type=int, default=4, help="梯度累积")
    parser.add_argument("--lr", type=float, default=5e-5, help="学习率")
    parser.add_argument("--max-length", type=int, default=512, help="最大序列长度")
    parser.add_argument("--lora-r", type=int, default=8, help="LoRA rank")
    parser.add_argument("--save-steps", type=int, default=500, help="保存间隔")

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    output_dir = (project_root / args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("  AI-Companion-Local QLoRA 微调")
    print("=" * 55)
    print(f"  模型: {args.model}")
    print(f"  训练数据: {args.train}")
    print(f"  轮数: {args.epochs}")
    print(f"  Batch: {args.batch_size} × {args.grad_accum} = {args.batch_size * args.grad_accum}")
    print(f"  输出: {output_dir}")
    print()

    # ---- 加载数据 ----
    print("[1/5] 加载训练数据...")
    train_ds = load_conversation_data(args.train)
    eval_ds = load_conversation_data(args.eval)
    print(f"  训练集: {len(train_ds)} 条, 验证集: {len(eval_ds)} 条")

    # ---- 加载模型 (4-bit) ----
    print("[2/5] 加载模型 (4-bit QLoRA)...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    # ---- 配置 LoRA ----
    print("[3/5] 配置 LoRA...")
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_r * 2,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ---- Tokenize ----
    print("[4/5] Tokenize...")
    train_ds = train_ds.map(
        lambda x: tokenize(x, tokenizer, args.max_length),
        batched=True,
        remove_columns=["text"],
    )
    eval_ds = eval_ds.map(
        lambda x: tokenize(x, tokenizer, args.max_length),
        batched=True,
        remove_columns=["text"],
    )

    # ---- 训练 ----
    print("[5/5] 开始训练...")
    effective_batch = args.batch_size * args.grad_accum
    total_steps = (len(train_ds) // effective_batch) * args.epochs

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        eval_strategy="steps",
        eval_steps=args.save_steps,
        save_steps=args.save_steps,
        logging_steps=10,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        bf16=True,
        optim="paged_adamw_8bit",
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        dataloader_num_workers=0,
        gradient_checkpointing=True,
        max_grad_norm=1.0,
        remove_unused_columns=False,
        ddp_find_unused_parameters=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=5)],
    )

    trainer.train()

    # ---- 保存 ----
    final_dir = output_dir / "final"
    model.save_pretrained(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"\n✅ 训练完成，模型保存在 {final_dir}")

    # 打印下一步指引
    print("\n下一步:")
    print("  1. 合并权重: python scripts/merge_lora.py")
    print("  2. 转换为 GGUF 并注册到 Ollama")


if __name__ == "__main__":
    main()
