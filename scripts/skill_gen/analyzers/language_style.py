"""
语言风格分析器

分析维度：句长分布、标点习惯、语气词、口头禅、emoji使用率、中英混用
"""

import re
from collections import Counter

from .base import LanguageStyleProfile, PersonalityProfile

# 常见语气词
_TONE_WORDS = set('吧呢嘛啊哦哈呀啦哇唉嘿哟咯哒呐嘻')

# 常见标点模式
_PUNCTUATION_PATTERNS = [
    ('～～', r'～～+'),
    ('！！！', r'！！！+'),
    ('……', r'……+'),
    ('？？？', r'？？？+'),
    ('。。。', r'。。。+'),
    ('！！!', r'！！!+'),
    ('~~~', r'~~~+'),
]

# 常见颜文字/emoji 模式
_EMOJI_RE = re.compile(
    r'[\U0001F300-\U0001F9FF]|'
    r'[\U0001FA00-\U0001FA6F]|'
    r'[☀-➿]|'
    r'[\(（][一-鿿\w]{1,4}[\)）]|'
    r'[一-鿿]{1,2}脸|'
    r'[～~]+[\.。]?|'
    r'o[\(（][\w一-鿿]*[\)）]'
)


def analyze_language_style(collection, profile: PersonalityProfile) -> None:
    """分析语言风格，结果写入 profile.language_style"""
    lp = LanguageStyleProfile()

    all_responses = []
    for pair in collection.pairs_with_response:
        all_responses.extend(pair.response_texts)

    if not all_responses:
        lp.summary = "无足够数据分析语言风格"
        profile.language_style = lp
        return

    # 句长分析
    lengths = [len(r) for r in all_responses]
    lp.avg_sentence_length = sum(lengths) / len(lengths)
    lp.sentence_length_short_pct = sum(1 for l in lengths if l < 10) / len(lengths) * 100
    lp.sentence_length_medium_pct = sum(1 for l in lengths if 10 <= l <= 30) / len(lengths) * 100
    lp.sentence_length_long_pct = sum(1 for l in lengths if l > 30) / len(lengths) * 100

    # 标点习惯
    all_text = ' '.join(all_responses)
    punct_counts = {}
    for name, pattern in _PUNCTUATION_PATTERNS:
        matches = re.findall(pattern, all_text)
        if matches:
            punct_counts[name] = len(matches)
    lp.top_punctuation = [k for k, _ in Counter(punct_counts).most_common(5)]

    # 语气词
    tone_counter = Counter()
    for char in all_text:
        if char in _TONE_WORDS:
            tone_counter[char] += 1
    lp.common_tone_words = [w for w, _ in tone_counter.most_common(8)]

    # 口头禅（2字高频词组，仅统计纯中文 bigram）
    _han = re.compile(r'^[一-鿿]{2}$')
    phrase_counter = Counter()
    for text in all_responses:
        for i in range(len(text) - 1):
            bigram = text[i:i+2]
            if _han.match(bigram):
                phrase_counter[bigram] += 1
    min_count = max(3, len(all_responses) * 0.01)
    lp.top_phrases = [p for p, c in phrase_counter.most_common(15) if c >= min_count][:8]

    # Emoji 使用率
    emoji_count = sum(len(_EMOJI_RE.findall(r)) for r in all_responses)
    lp.emoji_usage_rate = emoji_count / len(all_responses) * 100

    # 中英混用比例
    english_char_count = sum(1 for c in all_text if 'a' <= c.lower() <= 'z')
    total_chars = len(all_text.replace(' ', ''))
    lp.english_mix_rate = english_char_count / total_chars * 100 if total_chars else 0

    # 生成摘要
    parts = []
    if lp.sentence_length_short_pct > 50:
        parts.append(f"偏好短句（{lp.sentence_length_short_pct:.0f}%消息<10字），简洁明快")
    elif lp.sentence_length_long_pct > 30:
        parts.append(f"习惯长句表达（{lp.sentence_length_long_pct:.0f}%消息>30字），善于展开叙述")
    if lp.emoji_usage_rate > 10:
        parts.append(f"善用emoji/颜文字（使用率{lp.emoji_usage_rate:.0f}%）")
    if lp.top_phrases:
        parts.append(f"口头禅: {', '.join(lp.top_phrases[:3])}")
    if lp.common_tone_words:
        parts.append(f"常用语气词: {', '.join(lp.common_tone_words[:3])}")

    lp.summary = '；'.join(parts) if parts else '语言风格偏中性，无明显特征模式'
    profile.language_style = lp
