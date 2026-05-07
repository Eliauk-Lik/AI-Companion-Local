"""
QQ 消息管理器 JSON 导出解析器

适用场景：用户通过 QQ 消息管理器导出的 JSON 格式聊天记录。
    QQ 消息管理器路径：QQ 设置 → 安全设置 → 消息管理 → 导出消息记录。

JSON 格式特征：
    {
        "messages": [
            {
                "content": "消息内容",
                "sender_name": "发送者昵称",
                "time": "2024-01-15 18:30:00",
                "type": "text" / "system" / "image"
            },
            ...
        ]
    }
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .base import BaseParser, Message


class QQJSONParser(BaseParser):
    """QQ 消息管理器 JSON 格式解析器"""

    format_name = "QQ JSON 导出"

    def supports(self, input_path: Path) -> bool:
        """检测是否为 QQ 消息管理器导出的 JSON 文件"""
        if input_path.suffix.lower() != '.json':
            return False
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # QQ 导出的 JSON 包含 'messages' 数组
            return isinstance(data, dict) and 'messages' in data
        except (json.JSONDecodeError, IOError, UnicodeDecodeError):
            return False

    def parse(self, input_path: Path) -> List[Message]:
        """解析 QQ 消息管理器导出的 JSON 聊天记录"""
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        messages: List[Message] = []

        # 尝试读取 JSON
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败: {e}")
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(input_path, 'r', encoding='gbk') as f:
                data = json.load(f)

        raw_messages = data.get('messages', [])
        if not raw_messages:
            raise ValueError(f"JSON 文件中未找到 messages 数组: {input_path}")

        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue

            content = (msg.get('content') or '').strip()
            sender = (msg.get('sender_name') or msg.get('sender') or '').strip()
            msg_type = (msg.get('type') or 'text').strip()

            # 跳过系统消息
            if msg_type == 'system':
                continue

            # 跳过纯媒体消息（无文本内容）
            if msg_type in ('image', 'video', 'file', 'audio') and not content:
                continue

            # 解析时间
            msg_time = None
            time_raw = msg.get('time') or msg.get('timestamp') or msg.get('send_time')
            if time_raw:
                try:
                    msg_time = self._parse_datetime(str(time_raw))
                except ValueError:
                    pass

            messages.append(Message(
                sender=sender,
                content=content,
                time=msg_time,
                msg_type=msg_type,
            ))

        if not messages:
            raise ValueError(f"JSON 文件中没有解析到有效消息: {input_path}")

        return messages

    def _parse_datetime(self, time_str: str) -> datetime:
        """尝试解析 QQ 导出的多种时间格式

        QQ 导出常见格式：
            - 2024-01-15 18:30:00
            - 2024-01-15 18:30
            - 1705312200 (Unix 时间戳，秒)
            - 1705312200000 (Unix 时间戳，毫秒)
        """
        if not time_str:
            raise ValueError("空时间字符串")

        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(time_str.strip(), fmt)
            except ValueError:
                continue

        # Unix 时间戳
        try:
            ts = int(time_str.strip())
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000)
            if ts > 1e9:
                return datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            pass

        raise ValueError(f"无法解析时间字符串: {time_str}")
