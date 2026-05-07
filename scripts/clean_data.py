#!/usr/bin/env python3
"""
聊天记录清洗与结构化处理

功能：
    对解析后的聊天消息进行清洗、过滤、说话人识别和对话 Session 分段，
    输出结构化数据供后续的 Skill 生成模块使用。

处理流程：
    1. 加载原始聊天文件（自动检测格式）
    2. 过滤系统消息、媒体占位符、URL
    3. 长度过滤（< 2 字符跳过）
    4. 时间字符串解析
    5. 交互式说话人识别（让用户确认"谁是你"、"谁是Ta"）
    6. 按时间间隔切分对话 Session（默认 > 30 分钟为新会话）
    7. 输出清洗后数据到 data/processed/

用法：
    python scripts/clean_data.py --input data/raw/chat.csv
    python scripts/clean_data.py --input data/raw/chat.csv --session-gap 60
    python scripts/clean_data.py --input data/raw/chat.csv --me "我的昵称" --partner "对方的昵称"
    python scripts/clean_data.py --input data/raw/chat.csv --no-interactive
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 将 scripts/ 目录加入 sys.path，以便在项目根目录运行时也能导入 parsers
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from parsers.base import Message, detect_parser


# ============================================================
# 清洗规则
# ============================================================

# 媒体占位符正则（微信/QQ 通用）
MEDIA_PLACEHOLDER_RE = re.compile(
    r'\[图片\]|\[表情\]|\[视频\]|\[语音\]|\[文件\]|'
    r'\[动画表情\]|\[链接\]|\[小程序\]|\[引用\]|'
    r'\[红包\]|\[转账\]|\[聊天记录\]|\[位置\]|'
    r'\[QQ红包\]|\[戳一戳\]|\[表情包\]|\[表情包：\S+\]',
    re.IGNORECASE,
)

# URL 正则
URL_RE = re.compile(r'https?://\S+')

# 纯符号/无意义消息正则
NOISE_RE = re.compile(r'^[\s,.。，、！？!?:;；…~·]+$')


def clean_single_message(msg: Message) -> Optional[Message]:
    """清洗单条消息

    依次执行：去除媒体占位符 → 去除 URL → 去除首尾空白 → 长度过滤 → 纯符号过滤

    Args:
        msg: 原始 Message 对象

    Returns:
        清洗后的 Message 对象；如果应被过滤，返回 None
    """
    content = msg.content

    # 去除媒体占位符
    content = MEDIA_PLACEHOLDER_RE.sub('', content)

    # 去除 URL
    content = URL_RE.sub('', content)

    # 去除首尾空白
    content = content.strip()

    # 长度过滤
    if len(content) < 2:
        return None

    # 纯符号过滤
    if NOISE_RE.match(content):
        return None

    return Message(
        sender=msg.sender,
        content=content,
        time=msg.time,
        msg_type=msg.msg_type,
    )


def clean_messages(messages: List[Message]) -> List[Message]:
    """批量清洗消息列表，保持原有顺序"""
    cleaned: List[Message] = []
    for msg in messages:
        result = clean_single_message(msg)
        if result is not None:
            cleaned.append(result)
    return cleaned


# ============================================================
# 说话人识别
# ============================================================

def get_speaker_stats(messages: List[Message]) -> Dict[str, int]:
    """统计各说话人的消息数量，按消息数降序排列

    Args:
        messages: 消息列表

    Returns:
        说话人名称 → 消息数量 的映射
    """
    counter: Counter = Counter()
    for msg in messages:
        counter[msg.sender] += 1
    return dict(counter.most_common())


def interactive_speaker_selection(
    speaker_stats: Dict[str, int],
) -> Tuple[str, str]:
    """交互式让用户选择"谁是你"和"谁是Ta"

    展示所有检测到的说话人和消息统计，
    引导用户确认身份。

    Args:
        speaker_stats: 说话人名称 → 消息数量 映射

    Returns:
        (my_name, partner_name) 元组
    """
    speakers = list(speaker_stats.keys())
    total_msgs = sum(speaker_stats.values())

    print()
    print('=' * 50)
    print('  说话人识别')
    print('=' * 50)
    print()
    print(f'  共检测到 {len(speakers)} 个说话人:')
    print()

    for i, (name, count) in enumerate(speaker_stats.items(), 1):
        pct = count / total_msgs * 100
        bar = '█' * min(int(pct / 2), 40)
        print(f'  [{i}] {name:<20s} {count:>6d} 条消息  ({pct:5.1f}%) {bar}')

    print()
    print('  请告诉我是谁和谁是对话对象：')
    print()

    # 选择"我"
    if len(speakers) == 1:
        print(f'  只有一个说话人: {speakers[0]}')
        my_name = input('  你的名字: ').strip()
        if not my_name:
            my_name = '我'
        partner_name = speakers[0]
    else:
        default_me = speakers[0]  # 发言最多的通常是用户自己
        my_choice = input(f'  你在列表中的编号（默认 {1} = {default_me}）: ').strip()
        if my_choice and my_choice.isdigit():
            idx = int(my_choice) - 1
            my_name = speakers[idx] if 0 <= idx < len(speakers) else default_me
        else:
            my_name = default_me

        # 选择"Ta"
        remaining = [s for s in speakers if s != my_name]
        if remaining:
            if len(remaining) == 1:
                partner_name = remaining[0]
                print(f'  目标对象自动选择: {partner_name}')
            else:
                for i, name in enumerate(remaining, 1):
                    print(f'  [{i}] {name}')
                partner_choice = input(f'  目标对象的编号（默认 1 = {remaining[0]}）: ').strip()
                if partner_choice and partner_choice.isdigit():
                    idx = int(partner_choice) - 1
                    partner_name = remaining[idx] if 0 <= idx < len(remaining) else remaining[0]
                else:
                    partner_name = remaining[0]
        else:
            partner_name = input('  目标对象的名字: ').strip()

    print()
    print(f'  确认: 你 = "{my_name}", Ta = "{partner_name}"')
    confirm = input('  是否正确？(Y/n): ').strip().lower()
    if confirm in ('n', 'no', '不'):
        print('  已取消，请重新运行。')
        sys.exit(0)

    return my_name, partner_name


# ============================================================
# 对话 Session 分段
# ============================================================

def segment_into_sessions(
    messages: List[Message],
    gap_minutes: int = 30,
) -> List[List[Message]]:
    """按时间间隔将消息序列切分为对话 Session

    对消息按时间排序后，相邻消息时间差 > gap_minutes 的视为新会话起始。
    至少包含 2 条消息的 Session 才会被保留。

    Args:
        messages: 已清洗并按时间排序的消息列表
        gap_minutes: 会话间隔阈值（分钟），默认 30

    Returns:
        Session 列表，每个 Session 是一个 Message 列表
    """
    if not messages:
        return []

    # 按时间排序（无时间的消息放在最后）
    def sort_key(msg: Message):
        if msg.time is None:
            return datetime.max
        return msg.time

    sorted_msgs = sorted(messages, key=sort_key)

    gap_delta = timedelta(minutes=gap_minutes)
    sessions: List[List[Message]] = []
    current_session: List[Message] = [sorted_msgs[0]]

    for i in range(1, len(sorted_msgs)):
        prev_time = sorted_msgs[i - 1].time
        curr_time = sorted_msgs[i].time

        # 前一条或当前消息无时间信息时，视为同一会话
        if prev_time is not None and curr_time is not None:
            if curr_time - prev_time > gap_delta:
                if len(current_session) >= 2:
                    sessions.append(current_session)
                current_session = [sorted_msgs[i]]
            else:
                current_session.append(sorted_msgs[i])
        else:
            current_session.append(sorted_msgs[i])

    # 最后一个 session
    if len(current_session) >= 2:
        sessions.append(current_session)

    return sessions


# ============================================================
# 输出函数
# ============================================================

def save_cleaned_messages(messages: List[Message], output_path: Path) -> None:
    """将清洗后的消息保存为 JSON"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for msg in messages:
        records.append({
            'sender': msg.sender,
            'content': msg.content,
            'time': msg.time.isoformat() if msg.time else None,
            'msg_type': msg.msg_type,
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def save_sessions(sessions: List[List[Message]], output_path: Path) -> None:
    """将对话 Session 保存为 JSON"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    session_records = []
    for i, session in enumerate(sessions):
        msgs = []
        for msg in session:
            msgs.append({
                'sender': msg.sender,
                'content': msg.content,
                'time': msg.time.isoformat() if msg.time else None,
                'msg_type': msg.msg_type,
            })
        speakers = list(set(msg.sender for msg in session))
        start_time = session[0].time.isoformat() if session[0].time else None
        end_time = session[-1].time.isoformat() if session[-1].time else None

        session_records.append({
            'session_id': i + 1,
            'participants': speakers,
            'message_count': len(session),
            'start_time': start_time,
            'end_time': end_time,
            'messages': msgs,
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(session_records, f, ensure_ascii=False, indent=2)


# ============================================================
# 主入口
# ============================================================

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description='AI-Companion-Local 聊天记录清洗工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python scripts/clean_data.py --input data/raw/wechat.csv
  python scripts/clean_data.py --input data/raw/chat.csv --session-gap 60
  python scripts/clean_data.py --input data/raw/chat.csv --me "John" --partner "Jane"
  python scripts/clean_data.py --input data/raw/chat.csv --no-interactive
        '''
    )
    parser.add_argument('--input', '-i', type=str, required=True,
                        help='原始聊天记录文件路径（CSV 或 JSON）')
    parser.add_argument('--output-dir', '-o', type=str, default='data/processed',
                        help='输出目录（默认: data/processed）')
    parser.add_argument('--session-gap', type=int, default=30,
                        help='会话间隔阈值，分钟（默认: 30）')
    parser.add_argument('--me', type=str, default=None,
                        help='你的名字（跳过交互式选择）')
    parser.add_argument('--partner', type=str, default=None,
                        help='目标对象的名字（跳过交互式选择）')
    parser.add_argument('--no-interactive', action='store_true',
                        help='禁用交互模式，自动选择前两个说话人')

    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- 步骤1：解析 ----
    print(f'[1/5] 正在解析聊天记录: {input_path}')
    parser_obj = detect_parser(input_path)
    if parser_obj is None:
        print(f'[错误] 无法识别文件格式: {input_path}')
        print('  支持的格式: 微信 CSV 导出、QQ JSON 导出')
        sys.exit(1)

    print(f'  检测到格式: {parser_obj.format_name}')
    messages = parser_obj.parse(input_path)
    print(f'  解析到 {len(messages)} 条原始消息')
    print()

    # ---- 步骤2：清洗 ----
    print(f'[2/5] 正在清洗消息...')
    cleaned = clean_messages(messages)
    removed = len(messages) - len(cleaned)
    print(f'  清洗后保留 {len(cleaned)} 条消息（过滤 {removed} 条）')
    print()

    # ---- 步骤3：说话人识别 ----
    print(f'[3/5] 说话人识别')
    if len(cleaned) == 0:
        print('[错误] 清洗后没有剩余消息，请检查输入文件。')
        sys.exit(1)

    stats = get_speaker_stats(cleaned)

    # 根据命令行参数决定交互方式
    if args.me and args.partner:
        my_name = args.me
        partner_name = args.partner
        print(f'  使用命令行参数: 你 = "{my_name}", Ta = "{partner_name}"')
    elif args.no_interactive:
        speakers = list(stats.keys())
        my_name = speakers[0] if len(speakers) > 0 else '用户'
        partner_name = speakers[1] if len(speakers) > 1 else speakers[0]
        print(f'  自动选择: 你 = "{my_name}", Ta = "{partner_name}"')
    else:
        my_name, partner_name = interactive_speaker_selection(stats)

    # 保存说话人映射
    mapping_path = output_dir / 'speaker_mapping.json'
    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump({'me': my_name, 'partner': partner_name}, f, ensure_ascii=False, indent=2)
    print(f'  说话人映射已保存: {mapping_path}')
    print()

    # ---- 步骤4：Session 分段 ----
    print(f'[4/5] 正在按 {args.session_gap} 分钟间隔切分对话 Session...')
    sessions = segment_into_sessions(cleaned, gap_minutes=args.session_gap)
    print(f'  切分为 {len(sessions)} 个对话 Session')

    if sessions:
        total_msgs_in_sessions = sum(len(s) for s in sessions)
        avg_len = total_msgs_in_sessions / len(sessions)
        print(f'  平均每个 Session {avg_len:.1f} 条消息')
    print()

    # ---- 步骤5：保存输出 ----
    print(f'[5/5] 正在保存处理结果...')

    cleaned_path = output_dir / 'cleaned_messages.json'
    save_cleaned_messages(cleaned, cleaned_path)
    print(f'  清洗后消息: {cleaned_path} ({len(cleaned)} 条)')

    sessions_path = output_dir / 'sessions.json'
    save_sessions(sessions, sessions_path)
    print(f'  对话 Session: {sessions_path} ({len(sessions)} 个)')

    # 保存简要统计信息
    stats_path = output_dir / 'stats.json'
    stats_data = {
        'raw_count': len(messages),
        'cleaned_count': len(cleaned),
        'removed_count': removed,
        'session_count': len(sessions),
        'speakers': stats,
        'me': my_name,
        'partner': partner_name,
        'session_gap_minutes': args.session_gap,
        'date_range': {
            'start': min((m.time for m in cleaned if m.time), default=None),
            'end': max((m.time for m in cleaned if m.time), default=None),
        },
    }
    # 序列化 datetime
    if stats_data['date_range']['start']:
        stats_data['date_range']['start'] = stats_data['date_range']['start'].isoformat()
    if stats_data['date_range']['end']:
        stats_data['date_range']['end'] = stats_data['date_range']['end'].isoformat()
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)
    print(f'  统计信息: {stats_path}')

    print()
    print('=' * 50)
    print('  清洗完成！')
    print('=' * 50)
    print(f'  输出目录: {output_dir}')
    print()
    print('  下一步:')
    print(f'    python scripts/wizard.py           # 运行交互式向导')
    print(f'    python scripts/generate_skill.py   # 生成人格 Skill 文件（即将推出）')


if __name__ == '__main__':
    main()
