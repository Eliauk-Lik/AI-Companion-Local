"""
情感互动分析器

分析维度：情绪→回应策略映射、安慰倾向、幽默倾向、共情水平
"""

from collections import defaultdict
from typing import Dict, List

from .base import EmotionDynamicProfile, PersonalityProfile

# 用户情绪关键词 → 情绪类别
_EMOTION_KEYWORDS: Dict[str, List[str]] = {
    'sad': ['难过', '伤心', '哭', '悲伤', '郁闷', '失落', '累', '疲惫', '压力', '焦虑',
            '难堪', '不开心', '烦', '好惨', '社畜', '赶deadline', '喘不过气'],
    'angry': ['生气', '愤怒', '可恶', '恼火', '滚', '吵架', '吵', '过分', '好气'],
    'happy': ['开心', '快乐', '高兴', '嘻嘻', '嘿嘿', '哈哈', '笑死', '好开心', '超级好'],
    'confused': ['不懂', '不明白', '啥意思', '懵逼', '疑惑', '怎么回事'],
    'love': ['爱你', '喜欢', '想你', '抱抱', '亲亲', '么么哒'],
}

# 回应策略检测模式
_RESPONSE_STRATEGIES: Dict[str, List[str]] = {
    'comfort': ['别难过', '没事', '我在', '没关系', '懂你', '我懂', '你说得对',
               '不要', '别太', '相信我', '相信你', '抱抱', '摸摸'],
    'empathy': ['我也是', '我理解', '确实', '真的', '就是', '我懂你', '我也'],
    'distract': ['给你看', '看这个', '周末', '出来', '玩游戏', '打游戏', '带你',
               '喝一杯', '你看'],
    'humor': ['哈哈哈', '笑死', '哈哈', '😂', '233', '噗'],
    'advice': ['你应该', '可以试', '建议', '其实就', '最重要的就是', '下班了就',
             '多做', '别把', '不用管'],
    'question_followup': ['怎么了', '是不是', '啊？', '？', '怎么回事'],
}


def analyze_emotion_dynamic(collection, profile: PersonalityProfile) -> None:
    """分析情感互动模式，结果写入 profile.emotion_dynamic"""
    ed = EmotionDynamicProfile()

    pairs_with_resp = collection.pairs_with_response
    if not pairs_with_resp:
        ed.summary = "无足够数据分析情感互动"
        ed.empathy_level = "unknown"
        profile.emotion_dynamic = ed
        return

    strategy_by_emotion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    emotion_counts: Dict[str, int] = defaultdict(int)

    for pair in pairs_with_resp:
        anchor_text = pair.anchor.content
        response_text = pair.combined_response

        detected_emotion = None
        for emotion, keywords in _EMOTION_KEYWORDS.items():
            for kw in keywords:
                if kw in anchor_text:
                    detected_emotion = emotion
                    break
            if detected_emotion:
                break

        if not detected_emotion:
            continue

        emotion_counts[detected_emotion] += 1

        for strategy, patterns in _RESPONSE_STRATEGIES.items():
            for pattern in patterns:
                if pattern in response_text:
                    strategy_by_emotion[detected_emotion][strategy] += 1
                    break

    # 情绪→回应映射
    for emotion in emotion_counts:
        strategies = strategy_by_emotion.get(emotion, {})
        ed.emotion_response_map[emotion] = max(strategies, key=strategies.get) if strategies else 'neutral'

    # 安慰倾向
    comfort_total = sum(s.get('comfort', 0) + s.get('empathy', 0) for s in strategy_by_emotion.values())
    negative_total = emotion_counts.get('sad', 0) + emotion_counts.get('angry', 0)
    ed.comfort_tendency = comfort_total / negative_total if negative_total else 0

    # 幽默倾向
    humor_total = sum(s.get('humor', 0) for s in strategy_by_emotion.values())
    total_strategy = sum(sum(s.values()) for s in strategy_by_emotion.values())
    ed.humor_tendency = humor_total / total_strategy if total_strategy else 0

    # 共情水平
    empathy_count = sum(s.get('empathy', 0) for s in strategy_by_emotion.values())
    comfort_count = sum(s.get('comfort', 0) for s in strategy_by_emotion.values())
    if empathy_count + comfort_count > total_strategy * 0.5:
        ed.empathy_level = "high"
    elif empathy_count + comfort_count > total_strategy * 0.2:
        ed.empathy_level = "medium"
    else:
        ed.empathy_level = "low"

    # 生成摘要
    parts = []
    if ed.emotion_response_map.get('sad') == 'comfort':
        parts.append("面对你的负面情绪时倾向于安慰和共情，会认真倾听你的倾诉")
    elif ed.emotion_response_map.get('sad') == 'distract':
        parts.append("面对你的负面情绪时倾向于通过转移注意力来帮你缓解")
    if ed.emotion_response_map.get('happy') == 'humor':
        parts.append("当你在开心时Ta会用幽默回应，放大快乐情绪")
    if ed.empathy_level == 'high':
        parts.append("共情能力很强，经常使用'我也是''我懂你'等认同式表达")
    elif ed.empathy_level == 'low':
        parts.append("偏向理性解决而非情绪共情，更习惯给建议而不是'就只是听着'")

    ed.summary = '；'.join(parts) if parts else "情感互动模式较为常规"
    profile.emotion_dynamic = ed
