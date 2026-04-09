#!/usr/bin/env python3
"""
聊天记录清洗与格式化脚本

功能：
- 支持微信（Chatlog 导出 CSV）和 QQ（消息管理器导出 JSON/TXT）
- 去除无效信息、系统消息、短链接等
- 输出为微调所需的问答对格式（JSONL）

使用方法：
    python scripts/clean_data.py --input data/raw/wechat.csv --output data/processed/train.jsonl
"""

import argparse
import csv
import json
import re
from pathlib import Path


def clean_wechat_csv(input_path: Path, output_path: Path):
    """处理微信 Chatlog 导出的 CSV 文件"""
    conversations = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 过滤系统消息、空消息、过短消息
            content = row.get('content', '').strip()
            if not content or len(content) < 2:
                continue
            if row.get('type') == '10000':  # 系统消息
                continue
            # 清洗特殊字符和表情占位
            content = re.sub(r'\[表情\]|\[图片\]|\[视频\]|\[语音\]', '', content)
            content = re.sub(r'https?://\S+', '', content)  # 去除链接
            if not content:
                continue
            conversations.append({
                'sender': row.get('sender', ''),
                'content': content,
                'time': row.get('time', '')
            })

    # 构造问答对：连续对话中，前一条作为用户输入，后一条作为助手回复
    pairs = []
    for i in range(len(conversations) - 1):
        user_msg = conversations[i]['content']
        assistant_msg = conversations[i + 1]['content']
        pairs.append({'instruction': '', 'input': user_msg, 'output': assistant_msg})

    # 写入 JSONL
    with open(output_path, 'w', encoding='utf-8') as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + '\n')

    print(f'✅ 清洗完成，共生成 {len(pairs)} 条对话对，保存至 {output_path}')


def clean_qq_json(input_path: Path, output_path: Path):
    """处理 QQ 消息管理器导出的 JSON 文件"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = data.get('messages', [])
    conversations = []
    for msg in messages:
        content = msg.get('content', '').strip()
        if not content or len(content) < 2:
            continue
        # 过滤系统提示、撤回消息等
        if msg.get('type') == 'system':
            continue
        content = re.sub(r'\[图片\]|\[表情\]|\[文件\]', '', content)
        content = re.sub(r'https?://\S+', '', content)
        if not content:
            continue
        conversations.append({
            'sender': msg.get('sender_name', ''),
            'content': content,
            'time': msg.get('time', '')
        })

    pairs = []
    for i in range(len(conversations) - 1):
        user_msg = conversations[i]['content']
        assistant_msg = conversations[i + 1]['content']
        pairs.append({'instruction': '', 'input': user_msg, 'output': assistant_msg})

    with open(output_path, 'w', encoding='utf-8') as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + '\n')

    print(f'✅ 清洗完成，共生成 {len(pairs)} 条对话对，保存至 {output_path}')


def main():
    parser = argparse.ArgumentParser(description='清洗聊天记录为微调数据')
    parser.add_argument('--input', '-i', required=True, help='输入文件路径')
    parser.add_argument('--output', '-o', required=True, help='输出文件路径')
    parser.add_argument('--format', '-f', choices=['wechat', 'qq'], default='wechat',
                        help='数据源格式（默认 wechat）')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == 'wechat':
        clean_wechat_csv(input_path, output_path)
    elif args.format == 'qq':
        clean_qq_json(input_path, output_path)


if __name__ == '__main__':
    main()