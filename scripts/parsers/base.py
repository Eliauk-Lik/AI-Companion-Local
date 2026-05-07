"""
聊天记录解析器抽象基类

定义统一的 Message 数据结构和 Parser 接口。
所有聊天格式（微信 CSV、QQ JSON、TXT 等）的解析器都继承 BaseParser，
实现 parse() 方法返回 Message 列表。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Message:
    """统一的聊天消息数据结构

    Attributes:
        sender: 发送者名称/ID
        content: 消息文本内容
        time: 消息发送时间（解析后的 datetime 对象；无法解析则为 None）
        msg_type: 消息类型标记（如 'text', 'system', 'image', 'video' 等）
    """
    sender: str
    content: str
    time: Optional[datetime] = None
    msg_type: str = 'text'

    def __repr__(self) -> str:
        time_str = self.time.strftime('%Y-%m-%d %H:%M') if self.time else '未知时间'
        return f"[{time_str}] {self.sender}: {self.content[:50]}"


class BaseParser(ABC):
    """聊天记录解析器抽象基类

    每个子类实现 parse() 方法，将特定格式的聊天导出文件
    转换为统一的 Message 对象列表。
    """

    # 子类应覆盖此属性，说明支持的格式名称
    format_name: str = "未知格式"

    @abstractmethod
    def parse(self, input_path: Path) -> List[Message]:
        """解析聊天记录文件，返回 Message 列表

        Args:
            input_path: 聊天记录文件的路径

        Returns:
            按时间顺序排列的 Message 对象列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不匹配或内容不可解析
        """
        ...

    def supports(self, input_path: Path) -> bool:
        """检测此解析器是否支持给定的文件

        默认通过文件扩展名判断，子类可覆盖以实现更细粒度的检测。

        Args:
            input_path: 待检查的文件路径

        Returns:
            True 表示此解析器可以处理该文件
        """
        return False


def detect_parser(input_path: Path) -> Optional[BaseParser]:
    """自动检测适合该文件的解析器

    按优先级依次尝试已注册的解析器，返回第一个 supports() 返回 True 的。

    Args:
        input_path: 聊天记录文件路径

    Returns:
        匹配的解析器实例，若无匹配则返回 None
    """
    # 延迟导入避免循环依赖
    from .wechat_csv import WeChatCSVParser
    from .qq_json import QQJSONParser

    parsers: List[BaseParser] = [
        WeChatCSVParser(),
        QQJSONParser(),
    ]

    for parser in parsers:
        if parser.supports(input_path):
            return parser
    return None


def parse_datetime(time_str: str) -> datetime:
    """解析聊天记录中常见的时间格式（微信/QQ 共用）

    支持的格式：
        - 2024-01-15 18:30:00
        - 2024-01-15 18:30
        - 2024/01/15 18:30:00
        - Unix 时间戳（秒/毫秒）

    Raises:
        ValueError: 无法解析
    """
    if not time_str:
        raise ValueError("空时间字符串")

    # 剥离毫秒和时区后缀（如 .000Z, +08:00）
    cleaned = time_str.strip()
    if '.' in cleaned and cleaned.endswith('Z'):
        cleaned = cleaned.split('.')[0] + 'Z'
    # 尝试 Z 结尾的 ISO 格式
    if cleaned.endswith('Z'):
        cleaned = cleaned[:-1]

    for fmt in [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M',
    ]:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    try:
        ts = int(cleaned)
        if ts > 1e12:
            return datetime.fromtimestamp(ts / 1000)
        if ts > 1e9:
            return datetime.fromtimestamp(ts)
    except (ValueError, OSError):
        pass

    raise ValueError(f"无法解析时间字符串: {time_str}")
