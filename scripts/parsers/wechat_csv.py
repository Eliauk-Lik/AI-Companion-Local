"""
微信 Chatlog CSV 解析器

适用场景：用户通过微信 PC 版自带的"导出聊天记录"功能导出的 CSV 文件。
    导出路径通常为：微信窗口 → 聊天记录 → 导出 → 选择 CSV 格式。

CSV 格式特征（微信 3.x/4.x 通用）：
    - 包含列：content（消息内容）, sender（发送者）, time（时间）, type（消息类型）
    - type 为 '10000' 表示系统消息（如"XXX 加入了群聊"）
    - 消息内容中可能包含 [图片]、[表情]、[视频]、[语音] 等媒体占位符
    - 编码通常为 UTF-8
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List

from .base import BaseParser, Message


class WeChatCSVParser(BaseParser):
    """微信 Chatlog CSV 格式解析器"""

    format_name = "微信 CSV 导出"

    # 微信 CSV 常见的列名组合
    # 不同版本微信的导出列名可能略有差异，这里列出已知的变体
    _COLUMN_MAP = {
        'content': ['content', 'StrContent', '内容', '消息内容', 'message'],
        'sender': ['sender', 'StrTalker', '发送者', '发送人', 'speaker', 'talker'],
        'time': ['time', 'CreateTime', '时间', '发送时间', 'timestamp', 'date'],
        'type': ['type', 'Type', '类型', '消息类型', 'msg_type'],
    }

    def supports(self, input_path: Path) -> bool:
        """通过文件扩展名和表头检测是否为微信 CSV"""
        if input_path.suffix.lower() != '.csv':
            return False
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                header_line = f.readline().strip()
            # 检查表头是否包含微信 CSV 的特征列名
            return 'content' in header_line.lower() or 'strcontent' in header_line.lower()
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

        # 建立列名映射：将实际列名映射到标准字段名
        fieldnames_lower = [f.lower() if f else '' for f in reader.fieldnames]
        column_map = self._build_column_map(fieldnames_lower)

        required = {'content', 'sender'}
        missing = required - set(column_map.keys())
        if missing:
            raise ValueError(
                f"CSV 缺少必要列: {missing}。"
                f"实际列名: {reader.fieldnames}"
            )

        for row in reader:
            # 跳过空行
            try:
                content = row[reader.fieldnames[fieldnames_lower.index(column_map.get('content', ''))]]
                sender = row[reader.fieldnames[fieldnames_lower.index(column_map.get('sender', ''))]]
            except (IndexError, KeyError, ValueError):
                continue

            content = (content or '').strip()
            sender = (sender or '').strip()

            # 跳过系统消息类型（type == '10000'）
            if 'type' in column_map:
                try:
                    type_idx = fieldnames_lower.index(column_map['type'])
                    msg_type = row.get(reader.fieldnames[type_idx], '')
                    if str(msg_type) == '10000':
                        continue
                except (IndexError, ValueError):
                    pass

            # 解析时间
            msg_time = None
            if 'time' in column_map:
                try:
                    time_idx = fieldnames_lower.index(column_map['time'])
                    time_str = (row.get(reader.fieldnames[time_idx], '') or '').strip()
                    if time_str:
                        msg_time = self._parse_datetime(time_str)
                except (IndexError, ValueError):
                    pass

            messages.append(Message(
                sender=sender,
                content=content,
                time=msg_time,
                msg_type='text',
            ))

        if not messages:
            raise ValueError(f"CSV 文件中没有解析到有效消息: {input_path}")

        return messages

    def _build_column_map(self, fieldnames_lower: List[str]) -> dict:
        """根据实际表头建立 标准字段名 → 表头中原始名称（小写） 的映射"""
        mapping = {}
        for std_name, variants in self._COLUMN_MAP.items():
            for variant in variants:
                if variant in fieldnames_lower:
                    mapping[std_name] = variant
                    break
        return mapping

    def _parse_datetime(self, time_str: str) -> datetime:
        """尝试解析多种常见的时间格式

        微信导出常见格式：
            - 2024-01-15 18:30:00
            - 2024/01/15 18:30:00
            - 2024-01-15 18:30
            - 1705312200 (Unix 时间戳)
        """
        if not time_str:
            raise ValueError("空时间字符串")

        # 常见日期格式列表
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M',
            '%Y年%m月%d日 %H:%M:%S',
            '%Y年%m月%d日 %H:%M',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(time_str.strip(), fmt)
            except ValueError:
                continue

        # 尝试 Unix 时间戳（纯数字）
        try:
            ts = int(time_str.strip())
            # 毫秒时间戳
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000)
            # 秒时间戳
            if ts > 1e9:
                return datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            pass

        raise ValueError(f"无法解析时间字符串: {time_str}")
