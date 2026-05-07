"""
回复模式分析器

分析维度：回复速度、连续多发率、提问频率、话题主动率、每轮回复条数
"""

import re

from .base import PersonalityProfile, ReplyPatternProfile

# 问句检测模式
_QUESTION_RE = re.compile(
    r'[吗呢啊]？*$|[？?]|怎么|什么|哪[个些]|为什么|是不是|能不能|可不可以|要不要|想不想|会不会|行不行'
)


def analyze_reply_pattern(collection, profile: PersonalityProfile) -> None:
    """分析回复模式，结果写入 profile.reply_pattern"""
    rp = ReplyPatternProfile()

    pairs_with_resp = collection.pairs_with_response
    if not pairs_with_resp:
        rp.summary = "无足够数据分析回复模式"
        profile.reply_pattern = rp
        return

    # 回复速度
    reply_times = [p.time_to_first_reply for p in pairs_with_resp if p.time_to_first_reply is not None]
    if reply_times:
        rp.avg_reply_time_seconds = sum(reply_times) / len(reply_times)
        rp.fast_reply_pct = sum(1 for t in reply_times if t < 30) / len(reply_times) * 100

    # 连续多发回复率
    rp.multi_reply_rate = len(collection.multi_reply_pairs) / len(pairs_with_resp) * 100

    # 提问频率
    question_count = sum(1 for p in pairs_with_resp if _QUESTION_RE.search(p.combined_response))
    rp.question_rate = question_count / len(pairs_with_resp) * 100

    # 每轮平均回复条数
    rp.avg_responses_per_turn = sum(len(p.responses) for p in pairs_with_resp) / len(pairs_with_resp)

    # 生成摘要
    parts = []
    if rp.avg_reply_time_seconds and rp.avg_reply_time_seconds < 60:
        parts.append(f"回复迅速（平均{rp.avg_reply_time_seconds:.0f}秒），通常在看到消息后立即回应")
    elif rp.avg_reply_time_seconds and rp.avg_reply_time_seconds > 300:
        parts.append(f"回复较慢（平均{rp.avg_reply_time_seconds/60:.0f}分钟），可能有思考或忙碌的习惯")
    if rp.multi_reply_rate > 30:
        parts.append(f"喜欢分多条连续回复（{rp.multi_reply_rate:.0f}%的对话中Ta会连发多条），表达欲较强")
    if rp.question_rate > 40:
        parts.append(f"善于通过提问延续对话（{rp.question_rate:.0f}%的回复中包含疑问），关心对方想法")
    elif rp.question_rate < 15:
        parts.append(f"较少提问（{rp.question_rate:.0f}%），更多是陈述或回应而非追问")

    rp.summary = '；'.join(parts) if parts else "回复模式较为常规，无明显特征"
    profile.reply_pattern = rp
