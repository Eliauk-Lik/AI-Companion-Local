"""
话题偏好分析器

分析维度：话题频率、对方回应积极性、对方主动话题、回避话题
"""

from collections import defaultdict
from typing import Any, Dict, List

from .base import ContentThemesProfile, PersonalityProfile

# 话题类别及其关键词
_TOPIC_CATEGORIES: Dict[str, List[str]] = {
    '工作': ['工作', '加班', '上班', '领导', '同事', '开会', '项目', '方案', 'deadline',
            '公司', '客户', '汇报', '任务', '跳槽', '薪资', '社畜'],
    '游戏': ['游戏', '打游戏', '玩', '联机', '操作', '装备', '副本', 'boss', '排位',
            '上分', '手残', '飞', '带飞', '补偿', '组队', '开放世界'],
    '生活日常': ['吃饭', '睡觉', '地铁', '路上', '泡面', '喝水', '起床', '天气', '周末',
              '休息', '早起', '通勤', '宅家', '出门'],
    '情感倾诉': ['难过', '伤心', '开心', '心情', '压力', '焦虑', '难堪', '烦', '想',
              '不开心', '情绪', '谢谢你', '真的'],
    '娱乐': ['视频', 'bilibili', '看', '音乐', '电影', '剧', '综艺', '播客', '书',
            '表情', '图片', '猫', '解压'],
    '关系互动': ['晚安', '你也是', '谢谢你', '对不起', '没关系', '在吗', '想你了',
              '我懂你', '我相信你', '陪你'],
}


def analyze_content_themes(collection, profile: PersonalityProfile) -> None:
    """分析话题偏好，结果写入 profile.content_themes"""
    ct = ContentThemesProfile()

    pairs_with_resp = collection.pairs_with_response
    if not pairs_with_resp:
        ct.summary = "无足够数据分析话题偏好"
        profile.content_themes = ct
        return

    topic_total_anchors: Dict[str, int] = defaultdict(int)
    topic_response_counts: Dict[str, int] = defaultdict(int)
    topic_partner_initiated: Dict[str, int] = defaultdict(int)
    total_anchors = len(collection.pairs)

    for pair in collection.pairs:
        anchor_text = pair.anchor.content

        matched_topics = set()
        for topic, keywords in _TOPIC_CATEGORIES.items():
            for kw in keywords:
                if kw in anchor_text:
                    matched_topics.add(topic)
                    break

        if not matched_topics:
            matched_topics = {'日常闲聊'}

        for topic in matched_topics:
            topic_total_anchors[topic] += 1
            if pair.has_response:
                topic_response_counts[topic] += 1

        if pair.has_response:
            for topic, keywords in _TOPIC_CATEGORIES.items():
                for kw in keywords:
                    if kw in pair.combined_response:
                        topic_partner_initiated[topic] += 1
                        break

    # 计算频率和回应率
    topic_analysis: List[Dict[str, Any]] = []
    for topic in set(list(topic_total_anchors.keys()) + list(topic_partner_initiated.keys())):
        total = topic_total_anchors.get(topic, 0)
        responses = topic_response_counts.get(topic, 0)
        topic_analysis.append({
            'topic': topic,
            'frequency': total / total_anchors * 100 if total_anchors else 0,
            'count': total,
            'partner_responsiveness': responses / total if total > 0 else 0,
            'partner_active_count': topic_partner_initiated.get(topic, 0),
        })

    topic_analysis.sort(key=lambda x: x['frequency'], reverse=True)
    ct.top_topics = topic_analysis[:8]

    responsive_topics = [t for t in topic_analysis if t['count'] >= 2]
    responsive_topics.sort(key=lambda x: x['partner_responsiveness'], reverse=True)
    ct.partner_active_topics = [t['topic'] for t in responsive_topics[:3]]

    avoided = [t for t in topic_analysis if t['count'] >= 2 and t['partner_responsiveness'] < 0.3]
    ct.partner_avoided_topics = [t['topic'] for t in avoided[:3]]

    # 生成摘要
    parts = []
    if ct.top_topics:
        top3 = [t['topic'] for t in ct.top_topics[:3]]
        parts.append(f"对话中最频繁的话题是: {', '.join(top3)}")
    if ct.partner_active_topics:
        parts.append(f"Ta最积极回应的话题: {', '.join(ct.partner_active_topics[:2])}")
    if ct.partner_avoided_topics:
        parts.append(f"相对回避的话题: {', '.join(ct.partner_avoided_topics[:2])}")

    ct.summary = '；'.join(parts) if parts else "话题偏好不显著"
    profile.content_themes = ct
