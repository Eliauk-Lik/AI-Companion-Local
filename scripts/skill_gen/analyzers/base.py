"""
互动模式分析器抽象基类

定义 PersonalityProfile 数据结构和 BaseAnalyzer 接口。
每个分析器负责一个维度，向 PersonalityProfile 中填充对应的分析结果。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 前向引用避免循环导入
# PairCollection 和 ConversationPair 由 pair_builder 模块提供


@dataclass
class LanguageStyleProfile:
    """语言风格分析结果"""
    avg_sentence_length: float = 0.0          # 平均句长
    sentence_length_short_pct: float = 0.0     # 短句比例 (<10字)
    sentence_length_medium_pct: float = 0.0    # 中等句长比例 (10-30字)
    sentence_length_long_pct: float = 0.0      # 长句比例 (>30字)
    top_punctuation: List[str] = field(default_factory=list)  # 高频标点
    common_tone_words: List[str] = field(default_factory=list) # 常用语气词
    top_phrases: List[str] = field(default_factory=list)       # 口头禅 (2-4字词组)
    emoji_usage_rate: float = 0.0             # emoji/颜文字使用率
    english_mix_rate: float = 0.0             # 中英混用比例
    summary: str = ""                          # 风格一句话概括


@dataclass
class ReplyPatternProfile:
    """回复模式分析结果"""
    avg_reply_time_seconds: float = 0.0        # 平均回复时间
    fast_reply_pct: float = 0.0                # 快速回复比例 (<30s)
    multi_reply_rate: float = 0.0              # 连续多发回复比例
    question_rate: float = 0.0                 # 回复中含问句的比例
    topic_initiation_rate: float = 0.0         # 主动开启话题的比例
    avg_responses_per_turn: float = 0.0        # 平均每轮回复条数
    summary: str = ""


@dataclass
class EmotionDynamicProfile:
    """情感互动分析结果"""
    emotion_response_map: Dict[str, str] = field(default_factory=dict)
    # 如 {'sad': 'comfort', 'angry': 'calm', 'happy': 'amplify'}
    comfort_tendency: float = 0.0              # 安慰倾向 (我说负面情绪时Ta安慰的比例)
    humor_tendency: float = 0.0                # 幽默化解倾向
    empathy_level: str = ""                    # 共情水平: high/medium/low
    summary: str = ""


@dataclass
class RelationshipRoleProfile:
    """关系角色分析结果"""
    initiative_balance: Dict[str, float] = field(default_factory=dict)  # 谁更主动
    caregiver_score: float = 0.0               # 照顾者得分
    intimacy_markers: List[str] = field(default_factory=list)  # 亲密标记词
    role_description: str = ""                 # 角色描述
    summary: str = ""


@dataclass
class ContentThemesProfile:
    """话题偏好分析结果"""
    top_topics: List[Dict[str, Any]] = field(default_factory=list)
    # [{'topic': '工作', 'frequency': 0.3, 'partner_responsiveness': 0.8}, ...]
    partner_active_topics: List[str] = field(default_factory=list)  # Ta主动聊的话题
    partner_avoided_topics: List[str] = field(default_factory=list) # Ta倾向于回避的话题
    summary: str = ""


@dataclass
class PersonalityProfile:
    """完整的人格画像——所有分析结果的聚合体

    由五个维度的分析器分别填充，最终传给 report_generator 生成 Markdown。
    """
    target_name: str = ""                       # 目标对象名称
    source_summary: Dict[str, Any] = field(default_factory=dict)  # 数据来源摘要
    language_style: Optional[LanguageStyleProfile] = None
    reply_pattern: Optional[ReplyPatternProfile] = None
    emotion_dynamic: Optional[EmotionDynamicProfile] = None
    relationship_role: Optional[RelationshipRoleProfile] = None
    content_themes: Optional[ContentThemesProfile] = None

    def is_empty(self) -> bool:
        """检查是否至少有一个维度被分析过"""
        return all(v is None for v in [
            self.language_style,
            self.reply_pattern,
            self.emotion_dynamic,
            self.relationship_role,
            self.content_themes,
        ])
