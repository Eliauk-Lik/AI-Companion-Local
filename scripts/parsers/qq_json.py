"""
QQ Chat Exporter (QCE) JSON 导出解析器

适用场景：通过 QQ Chat Exporter (https://github.com/shuakami/qq-chat-exporter)
    导出的 JSON 格式聊天记录。QCE 是目前 QQNT 架构下唯一可用的聊天记录导出工具。

JSON 格式特征：
    {
        "chatInfo": {
            "chatName": "好友昵称或群名",
            "chatUid": "...",
            "chatType": "friend" | "group"
        },
        "messages": [
            {
                "senderName": "发送者昵称",
                "senderUid": "...",
                "senderUin": "QQ号",
                "timestamp": "2024-01-15 18:30:00",
                "msgType": "text" | "image" | "video" | ...,
                "content": "消息正文",
                "elements": [...]
            }
        ],
        "exportMetadata": {
            "selfName": "导出者昵称",
            "selfUin": "导出者QQ号"
        },
        "resources": {...}
    }
"""

import json
from pathlib import Path
from typing import List, Optional

from .base import BaseParser, Message, parse_datetime


class QQJSONParser(BaseParser):
    """QQ Chat Exporter (QCE) JSON 格式解析器"""

    format_name = "QQ JSON 导出 (QCE)"

    def supports(self, input_path: Path) -> bool:
        """检测是否为 QCE 导出的 JSON 文件"""
        if input_path.suffix.lower() != '.json':
            return False
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return (
                isinstance(data, dict)
                and 'messages' in data
                and 'chatInfo' in data
            )
        except (json.JSONDecodeError, IOError, UnicodeDecodeError):
            return False

    def parse(self, input_path: Path) -> List[Message]:
        """解析 QCE 导出的 JSON 聊天记录"""
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败: {e}")
        except UnicodeDecodeError:
            with open(input_path, 'r', encoding='gbk') as f:
                data = json.load(f)

        raw_messages = data.get('messages', [])
        if not raw_messages:
            raise ValueError(f"JSON 文件中未找到 messages 数组: {input_path}")

        # 提取导出者身份（QCE 特有字段）
        export_meta = data.get('exportMetadata', {})
        self.self_name: Optional[str] = export_meta.get('selfName')
        self.self_uin: Optional[str] = export_meta.get('selfUin')
        self.chat_info = data.get('chatInfo', {})

        messages: List[Message] = []

        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue

            content = (msg.get('content') or '').strip()
            sender = (msg.get('senderName') or msg.get('senderUin') or '').strip()
            msg_type = (msg.get('msgType') or 'text').strip()

            # 跳过系统消息
            if msg_type == 'system':
                continue

            # 跳过纯媒体消息（无文本内容）
            if msg_type in ('image', 'video', 'file', 'audio') and not content:
                continue

            # 解析时间（QCE 输出可能是 ISO 8601 或常见格式）
            msg_time = None
            time_raw = msg.get('timestamp') or msg.get('time')
            if time_raw:
                try:
                    msg_time = parse_datetime(str(time_raw))
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
