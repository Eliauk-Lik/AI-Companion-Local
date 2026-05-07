"""
互动模式分析器集合

五个分析维度（每个是一个独立函数，签名: (collection, profile) -> None）：
    analyze_language_style   — 语言风格（句长/标点/语气词/emoji/口头禅）
    analyze_reply_pattern    — 回复模式（速度/多回复/提问率）
    analyze_emotion_dynamic  — 情感互动（情绪→回应策略/共情水平）
    analyze_relationship_role — 关系角色（主动权/照顾者/亲密标记）
    analyze_content_themes   — 话题偏好（频率/回应热图/回避话题）
"""

from .base import (
    PersonalityProfile,
    LanguageStyleProfile,
    ReplyPatternProfile,
    EmotionDynamicProfile,
    RelationshipRoleProfile,
    ContentThemesProfile,
)
from .language_style import analyze_language_style
from .reply_pattern import analyze_reply_pattern
from .emotion_dynamic import analyze_emotion_dynamic
from .relationship_role import analyze_relationship_role
from .content_themes import analyze_content_themes


def get_all_analyzers():
    """返回所有分析器 (名称, 函数) 的列表，按推荐顺序排列"""
    return [
        ("语言风格", analyze_language_style),
        ("回复模式", analyze_reply_pattern),
        ("情感互动", analyze_emotion_dynamic),
        ("关系角色", analyze_relationship_role),
        ("话题偏好", analyze_content_themes),
    ]
