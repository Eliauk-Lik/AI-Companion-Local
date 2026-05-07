"""
上下文窗口对话对构建器

核心创新模块：不是简单统计"对方说过什么"，而是构建
"我说了 X → Ta 如何回应 Y" 的对话对，捕获互动模式。

采用上下文窗口模式：
    以"我"的每条消息为锚点，在后续 N 条消息或 M 分钟内，
    收集对方的所有回复，形成一对多的映射关系。

输入：Phase 1 输出的 sessions.json + speaker_mapping.json
输出：ConversationPair 列表，供分析器使用
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 复用 Phase 1 的 Message 数据结构
import sys
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from parsers.base import Message


@dataclass
class ConversationPair:
    """一个对话对：我说了什么 → Ta 如何回应

    Attributes:
        anchor: 我发出的锚点消息
        responses: 对方在窗口内的回复列表（可能多条）
        session_id: 所属会话编号
        time_to_first_reply: 到第一条回复的秒数（None 表示无回复）
        window_msg_count: 窗口内的总消息数（含其他人的消息）
    """
    anchor: Message
    responses: List[Message] = field(default_factory=list)
    session_id: int = 0
    time_to_first_reply: Optional[float] = None

    @property
    def has_response(self) -> bool:
        """是否有对方的回复"""
        return len(self.responses) > 0

    @property
    def is_multi_reply(self) -> bool:
        """对方是否连续发了多条回复"""
        return len(self.responses) > 1

    @property
    def response_texts(self) -> List[str]:
        """回复的纯文本列表"""
        return [r.content for r in self.responses]

    @property
    def combined_response(self) -> str:
        """将所有回复合并为一段文字（用于分析整体语气）"""
        return ' '.join(self.response_texts)


@dataclass
class PairCollection:
    """对话对集合，附带元数据

    Attributes:
        pairs: 所有对话对
        my_name: 我的名字
        partner_name: 对方的名字
        total_sessions: 来源会话总数
        total_messages: 原始消息总数
        pair_rate: 产生对话对的比例（pairs / my_messages）
    """
    pairs: List[ConversationPair]
    my_name: str
    partner_name: str
    total_sessions: int
    total_messages: int

    @property
    def pairs_with_response(self) -> List[ConversationPair]:
        """有回复的对话对（对方真正回应了）"""
        return [p for p in self.pairs if p.has_response]

    @property
    def multi_reply_pairs(self) -> List[ConversationPair]:
        """对方多发回复的对话对"""
        return [p for p in self.pairs if p.is_multi_reply]

    def stats(self) -> Dict:
        """返回统计摘要"""
        total = len(self.pairs)
        with_resp = len(self.pairs_with_response)
        multi = len(self.multi_reply_pairs)
        return {
            'total_pairs': total,
            'pairs_with_response': with_resp,
            'no_response_rate': f"{(1 - with_resp/total)*100:.1f}%" if total else 'N/A',
            'multi_reply_rate': f"{multi/with_resp*100:.1f}%" if with_resp else 'N/A',
            'avg_responses_per_pair': f"{sum(len(p.responses) for p in self.pairs_with_response) / with_resp:.1f}" if with_resp else 'N/A',
        }


def build_pairs(
    sessions: List[Dict],
    my_name: str,
    partner_name: str,
    window_size: int = 5,
    time_window_minutes: int = 10,
) -> PairCollection:
    """从对话 Session 中构建上下文窗口对话对

    算法流程：
        遍历每个 Session 中的每条消息。
        当遇到"我"的消息时，创建一个锚点，
        然后在后续 window_size 条消息和 time_window_minutes 分钟内，
        收集对方（partner_name）的所有回复。

    Args:
        sessions: Phase 1 输出的 sessions.json 数据
        my_name: 我的发送者名称
        partner_name: 目标对象的发送者名称
        window_size: 消息窗口大小（默认 5 条）
        time_window_minutes: 时间窗口大小（默认 10 分钟）

    Returns:
        PairCollection 包含所有对话对和元数据
    """
    pairs: List[ConversationPair] = []
    total_messages = 0

    for session_data in sessions:
        session_id = session_data.get('session_id', 0)
        raw_messages = session_data.get('messages', [])

        # 将 JSON 数据转为 Message 对象列表
        messages: List[Message] = []
        for m in raw_messages:
            time_str = m.get('time')
            msg_time = None
            if time_str:
                try:
                    msg_time = datetime.fromisoformat(time_str)
                except (ValueError, TypeError):
                    pass
            messages.append(Message(
                sender=m.get('sender', ''),
                content=m.get('content', ''),
                time=msg_time,
            ))

        total_messages += len(messages)

        # 构建对话对
        i = 0
        while i < len(messages):
            msg = messages[i]

            # 只有"我"的消息才作为锚点
            if msg.sender != my_name or not msg.content:
                i += 1
                continue

            anchor = msg
            anchor_time = msg.time
            responses: List[Message] = []
            msg_count = 0
            time_to_first = None
            time_limit = anchor_time + timedelta(minutes=time_window_minutes) if anchor_time else None

            # 在窗口中收集对方的回复
            lookahead = i + 1
            while lookahead < len(messages) and msg_count < window_size:
                next_msg = messages[lookahead]

                # 时间窗口检查
                if time_limit and next_msg.time and next_msg.time > time_limit:
                    break

                msg_count += 1

                if next_msg.sender == partner_name and next_msg.content:
                    if time_to_first is None and next_msg.time and anchor_time:
                        time_to_first = (next_msg.time - anchor_time).total_seconds()
                    responses.append(next_msg)

                # 如果遇到"我"的下一条消息，停止（避免跨说话轮）
                if next_msg.sender == my_name:
                    break

                lookahead += 1

            pairs.append(ConversationPair(
                anchor=anchor,
                responses=responses,
                session_id=session_id,
                time_to_first_reply=time_to_first,
            ))

            i = lookahead  # 跳过已处理的窗口

    return PairCollection(
        pairs=pairs,
        my_name=my_name,
        partner_name=partner_name,
        total_sessions=len(sessions),
        total_messages=total_messages,
    )


def load_sessions_and_mapping(processed_dir: Path) -> tuple:
    """从 Phase 1 输出目录加载 Session 数据和说话人映射

    Args:
        processed_dir: data/processed/ 目录路径

    Returns:
        (sessions_list, my_name, partner_name) 元组
    """
    import json

    sessions_path = processed_dir / 'sessions.json'
    mapping_path = processed_dir / 'speaker_mapping.json'

    if not sessions_path.exists():
        raise FileNotFoundError(
            f"未找到 sessions.json: {sessions_path}。"
            f"请先运行 python scripts/clean_data.py"
        )
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"未找到 speaker_mapping.json: {mapping_path}。"
            f"请先运行 python scripts/clean_data.py"
        )

    with open(sessions_path, 'r', encoding='utf-8') as f:
        sessions = json.load(f)
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    return sessions, mapping['me'], mapping['partner']
