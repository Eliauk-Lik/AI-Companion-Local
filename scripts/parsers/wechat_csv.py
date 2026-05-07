"""
微信 Chatlog CSV 解析器

支持微信 PC 版多种导出格式（3.x 旧版 / 4.x 新版）：
    旧版列: content, sender, time, type
    新版列: msg, talker, CreateTime, type_name, is_sender
"""

import csv
from pathlib import Path
from typing import List

from .base import BaseParser, Message, parse_datetime


class WeChatCSVParser(BaseParser):
    """微信 Chatlog CSV 格式解析器"""

    format_name = "微信 CSV 导出"

    # 微信 CSV 常见的列名组合
    # 不同版本微信的导出列名可能略有差异，这里列出已知的变体
    _COLUMN_MAP = {
        'content': ['content', 'strcontent', 'msg', 'message', '内容', '消息内容'],
        'sender': ['sender', 'strtalker', 'talker', 'speaker', '发送者', '发送人'],
        'time': ['time', 'createtime', 'timestamp', 'date', '时间', '发送时间'],
        'type': ['type', 'type_name', 'msg_type', '类型', '消息类型'],
        'is_sender': ['is_sender', 'issender'],
    }

    def supports(self, input_path: Path) -> bool:
        """通过文件扩展名和表头检测是否为微信 CSV"""
        if input_path.suffix.lower() != '.csv':
            return False
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                header_line = f.readline().strip()
            # 检查表头是否包含微信 CSV 的特征列名
            header_lower = header_line.lower()
            return any(kw in header_lower for kw in ('content', 'strcontent', 'msg', 'talker'))
        except (IOError, UnicodeDecodeError):
            return False

    def parse(self, input_path: Path) -> List[Message]:
        """解析微信导出的 CSV 聊天记录

        会自动检测 CSV 的列名映射，兼容不同版本微信的导出格式。
        """
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        messages: List[Message] = []
        column_map = {}  # 实际列名 → 标准字段名

        # 尝试常见编码
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030']
        content_lines = []

        for enc in encodings:
            try:
                with open(input_path, 'r', encoding=enc) as f:
                    content_lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"无法识别文件编码，已尝试: {encodings}")

        if not content_lines:
            return messages

        # 解析 CSV
        reader = csv.DictReader(content_lines)
        if reader.fieldnames is None:
            raise ValueError("CSV 文件没有表头行")

        # 建立列名映射
        fieldnames_lower = [f.lower() if f else '' for f in reader.fieldnames]
        col = self._build_column_map(reader.fieldnames, fieldnames_lower)
        has_is_sender = 'is_sender' in col

        required = {'content'}
        if not has_is_sender:
            required.add('sender')
        missing = required - set(col.keys())
        if missing:
            raise ValueError(f"CSV 缺少必要列: {missing}。实际列名: {reader.fieldnames}")

        for row in reader:
            content = (row.get(col['content'], '') or '').strip()
            if not content:
                continue

            # 确定发送者：新版用 is_sender，旧版用 sender 列
            if has_is_sender:
                is_sender = str(row.get(col['is_sender'], '0')).strip()
                talker = row.get(col.get('sender', ''), '') if 'sender' in col else ''
                sender = '我' if is_sender == '1' else (talker or '').strip()
            else:
                sender = (row.get(col['sender'], '') or '').strip()

            # 跳过系统消息（type == '10000'）
            if 'type' in col and str(row.get(col['type'], '')) == '10000':
                continue

            # 解析时间
            msg_time = None
            time_str = (row.get(col.get('time', ''), '') or '').strip()
            if time_str:
                try:
                    msg_time = parse_datetime(time_str)
                except ValueError:
                    pass

            messages.append(Message(sender=sender, content=content, time=msg_time))

        if not messages:
            raise ValueError(f"CSV 文件中没有解析到有效消息: {input_path}")

        return messages

    def _build_column_map(self, fieldnames: List[str], fieldnames_lower: List[str]) -> dict:
        """根据实际表头建立 标准字段名 → 原始列名 的映射"""
        mapping = {}
        for std_name, variants in self._COLUMN_MAP.items():
            for variant in variants:
                if variant in fieldnames_lower:
                    idx = fieldnames_lower.index(variant)
                    mapping[std_name] = fieldnames[idx]
                    break
        return mapping

