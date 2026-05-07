"""
关系角色分析器

分析维度：主动权平衡、照顾者得分、亲密标记、角色定位
"""

import re

from .base import PersonalityProfile, RelationshipRoleProfile

# 照顾者行为标记
_CAREGIVER_RE = re.compile(
    r'(多吃|多睡|休息|喝水|注意|小心|照顾好|保重)|'
    r'(别太|不要[太过]|别[难过担心])|'
    r'(加油|没事|没关系|会好的|相信我)|'
    r'(我在|有我|陪你|帮你|带你)|'
    r'(建议|试试|可以试试|要不要)'
)

# 亲密标记模式
_INTIMACY_PATTERNS = [
    (r'[你我][好坏笨傻呆懒]', '调侃式称呼'),
    (r'[你我][可爱有趣厉害聪明]', '正向评价'),
    (r'[你我]走开|[你我]滚|[你我]去死', '玩笑式攻击（亲密信号）'),
    (r'摸摸|抱抱|亲亲|么么', '亲密动作表达'),
    (r'哈哈哈[你我他她]', '共同笑点'),
    (r'我们|一起|咱[们俩]', '共同体表达'),
]


def analyze_relationship_role(collection, profile: PersonalityProfile) -> None:
    """分析关系角色，结果写入 profile.relationship_role"""
    rr = RelationshipRoleProfile()

    pairs_with_resp = collection.pairs_with_response
    if not pairs_with_resp:
        rr.summary = "无足够数据分析关系角色"
        rr.role_description = "未知"
        profile.relationship_role = rr
        return

    all_responses = [p.combined_response for p in pairs_with_resp]

    # 主动权分析
    rr.initiative_balance = {
        'user_initiates': len(collection.pairs),
        'partner_responds': len(pairs_with_resp),
        'response_rate': len(pairs_with_resp) / len(collection.pairs) * 100 if collection.pairs else 0,
    }

    # 照顾者得分
    caregiver_count = sum(1 for r in all_responses if _CAREGIVER_RE.search(r))
    rr.caregiver_score = caregiver_count / len(all_responses) * 100 if all_responses else 0

    # 亲密标记
    all_text = ' '.join(all_responses)
    for pattern, label in _INTIMACY_PATTERNS:
        matches = re.findall(pattern, all_text)
        if matches:
            rr.intimacy_markers.append(f"{label} (出现{len(matches)}次)")

    # 角色描述
    parts = []
    if rr.caregiver_score > 15:
        parts.append("照顾者/支持者")
    elif rr.caregiver_score > 5:
        parts.append("有照顾倾向的朋友")
    if rr.initiative_balance['response_rate'] > 80:
        parts.append("积极回应的倾听者")
    elif rr.initiative_balance['response_rate'] < 50:
        parts.append("选择性回应的对话者")
    if len(rr.intimacy_markers) >= 5:
        parts.insert(0, "亲密好友")
    elif len(rr.intimacy_markers) >= 2 and not any('亲密' in p for p in parts):
        parts.insert(0, "关系亲近的朋友")

    rr.role_description = '，'.join(parts) if parts else "普通朋友/聊天对象"

    # 生成摘要
    summary_parts = []
    if rr.caregiver_score > 10:
        summary_parts.append(
            f"在对话中表现出较强的照顾倾向（关心建议类回应占比{rr.caregiver_score:.0f}%），"
            f"会主动关注你的状态并给出建议"
        )
    if rr.intimacy_markers:
        summary_parts.append(f"对话中存在亲密标记: {', '.join(rr.intimacy_markers[:3])}")
    if rr.initiative_balance['response_rate'] > 90:
        summary_parts.append("几乎每次都会回应你的消息，互动意愿很强")

    rr.summary = '；'.join(summary_parts) if summary_parts else "关系较为常规，无明显特定角色模式"
    profile.relationship_role = rr
