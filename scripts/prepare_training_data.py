#!/usr/bin/env python3
"""
准备 QLoRA 微调训练数据

从 Phase 2 的对话对中生成 LLaMA-Factory conversation 格式的训练集和验证集。
每对对话对 -> {"conversations": [{"from":"human","value":"..."}, {"from":"gpt","value":"..."}]}

用法:
    python scripts/prepare_training_data.py
    python scripts/prepare_training_data.py --input-dir data/processed --output-dir data
    python scripts/prepare_training_data.py --split 0.85 --min-length 4
"""

import json
import random
import re
import sys
from pathlib import Path

# 需要过滤的媒体占位符
_MEDIA_RE = re.compile(r'^\[(图片|表情|视频|语音|文件|动画表情|链接|小程序|引用|红包|转账|聊天记录|位置|QQ红包|戳一戳|表情包).*\]$')

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from skill_gen.pair_builder import build_pairs, load_sessions_and_mapping


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="准备 QLoRA 微调训练数据"
    )
    parser.add_argument("--input-dir", default="data/processed",
                        help="Phase 1 输出目录")
    parser.add_argument("--output-dir", default="data",
                        help="训练数据输出目录")
    parser.add_argument("--split", type=float, default=0.9,
                        help="训练集比例（默认 0.9）")
    parser.add_argument("--min-length", type=int, default=4,
                        help="回复最小长度（字符，默认 4）")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子")

    args = parser.parse_args()
    random.seed(args.seed)

    project_root = _SCRIPT_DIR.parent
    input_dir = (project_root / args.input_dir).resolve()
    output_dir = (project_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 加载数据
    print("[1/4] 加载 Phase 1 输出...")
    sessions, my_name, partner_name = load_sessions_and_mapping(input_dir)
    print(f"  {len(sessions)} 个会话, 我={my_name}, 对方={partner_name}")

    # 2. 构建对话对
    print("[2/4] 构建对话对...")
    collection = build_pairs(sessions, my_name, partner_name)
    pairs_with_resp = collection.pairs_with_response
    print(f"  {len(collection.pairs)} 个对话对, {len(pairs_with_resp)} 个有回复")

    # 3. 转换为 LLaMA-Factory 格式
    print("[3/4] 转换为训练格式...")
    records = []
    skipped = 0
    for pair in pairs_with_resp:
        # 跳过纯媒体占位符的锚点（如 [表情包]）
        if _MEDIA_RE.match(pair.anchor.content.strip()):
            skipped += 1
            continue
        for resp in pair.responses:
            if _MEDIA_RE.match(resp.content.strip()):
                skipped += 1
                continue
            if len(resp.content) < args.min_length:
                skipped += 1
                continue
            records.append({
                "conversations": [
                    {"from": "human", "value": pair.anchor.content},
                    {"from": "gpt", "value": resp.content},
                ]
            })

    print(f"  {len(records)} 条训练样本（跳过 {skipped} 条过短回复）")

    if len(records) < 10:
        print("[错误] 训练样本不足，请检查数据量。")
        sys.exit(1)

    # 4. 打乱并分割
    print(f"[4/4] 打乱并按 {args.split:.0%}/{1-args.split:.0%} 分割...")
    random.shuffle(records)
    split_idx = int(len(records) * args.split)
    train_records = records[:split_idx]
    eval_records = records[split_idx:]

    train_path = output_dir / "train.json"
    eval_path = output_dir / "eval.json"

    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train_records, f, ensure_ascii=False, indent=2)
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_records, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 50)
    print("  训练数据准备完成")
    print("=" * 50)
    print(f"  训练集: {train_path} ({len(train_records)} 条)")
    print(f"  验证集: {eval_path} ({len(eval_records)} 条)")
    print()
    print("  下一步:")
    print("    1. 安装 LLaMA-Factory: pip install llamafactory")
    print("    2. 更新 finetune/configs/qlora_config.yaml 中的 dataset 路径")
    print("    3. 运行训练: llamafactory-cli train finetune/configs/qlora_config.yaml")


if __name__ == "__main__":
    main()
