"""
人格 Skill Markdown 报告生成器

基于 PersonalityProfile 生成两个版本的 Skill 文件：
    - skill_cloud_safe.md: 仅统计描述 + 行为规则，不含真实对话原文，可安全粘贴到云端 LLM
    - skill_local_full.md: 包含精选对话片段 + 完整画像，仅用于本地 Ollama 使用

两个文件均包含伦理声明头部。
"""

from datetime import datetime
from pathlib import Path

from .analyzers.base import PersonalityProfile


def generate_skill_markdown(
    profile: PersonalityProfile,
    output_path: Path,
    *,
    include_examples: bool = False,
    sample_pairs: list = None,
) -> Path:
    """生成人格 Skill Markdown 文件

    Args:
        profile: 人格画像
        output_path: 输出路径
        include_examples: 是否包含真实对话片段（cloud_safe=False, local_full=True）
        sample_pairs: 对话对列表（仅 include_examples=True 时需要）
    """
    version = 'local_full' if include_examples else 'cloud_safe'
    lines = _build_header(profile, version=version)
    lines.append('')

    if include_examples:
        lines.append('> **Local-Full 版本说明**')
        lines.append('> 此文件包含真实对话片段作为参考示例，')
        lines.append('> **请勿将此文件内容粘贴到任何云端 AI 服务**，仅供本地 Ollama 使用。')
    else:
        lines.append('> **Cloud-Safe 版本说明**')
        lines.append('> 此文件仅包含统计描述和行为规则，不包含任何原始对话原文，')
        lines.append('> 可安全粘贴到云端 AI 服务（ChatGPT/DeepSeek 等）使用。')
    lines.append('')

    cloud_safe = not include_examples

    lines.extend(_build_character_sketch(profile))
    lines.append('')

    if profile.language_style:
        lines.extend(_build_language_style_section(profile, cloud_safe))
        lines.append('')
    if profile.reply_pattern:
        lines.extend(_build_reply_pattern_section(profile, cloud_safe))
        lines.append('')
    if profile.emotion_dynamic:
        lines.extend(_build_emotion_dynamic_section(profile, cloud_safe))
        lines.append('')
    if profile.relationship_role:
        lines.extend(_build_relationship_role_section(profile, cloud_safe))
        lines.append('')
    if profile.content_themes:
        lines.extend(_build_content_themes_section(profile, cloud_safe))
        lines.append('')

    if include_examples and sample_pairs:
        lines.extend(_build_dialogue_examples(sample_pairs))
        lines.append('')

    lines.extend(_build_behavior_guide(profile))
    lines.append('')

    content = '\n'.join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding='utf-8')
    return output_path


# ============================================================
# 章节构建函数
# ============================================================

def _build_header(profile: PersonalityProfile, version: str) -> list:
    """构建伦理声明头部"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    info = profile.source_summary
    return [
        f'# {profile.target_name} — AI 人格 Skill 文件',
        '',
        f'> ⚠️ **隐私与伦理声明**',
        f'> 此人格文件由 AI-Companion-Local 基于本地聊天记录自动生成。',
        f'> 所有数据处理在本地完成，开发者无法访问您的聊天数据。',
        f'> ',
        f'> **使用边界：**',
        f'> ✅ 个人纪念、心理陪伴、创意写作参考',
        f'> ❌ 冒充他人身份、欺诈、骚扰、诽谤',
        f'> {"❌ 将包含原文对话的片段上传至云端 AI 服务" if version == "local_full" else "✅ 此 Cloud-Safe 版本可安全用于云端 AI 服务"}',
        f'> ',
        f'> 版本: {version} | 生成时间: {now}',
        f'> 数据来源: {info.get("message_count", "N/A")} 条消息 | {info.get("session_count", "N/A")} 个会话',
        f'> 目标对象: {profile.target_name}',
        '',
        '---',
    ]


def _build_character_sketch(profile: PersonalityProfile) -> list:
    """构建角色速写部分"""
    lines = ['## 角色速写', '']
    lines.append(f'你正在与 **{profile.target_name}** 对话。以下是基于真实聊天记录分析得出的人格画像。')
    lines.append('')

    # 收集各维度的摘要，形成一个自然的描述段落
    summaries = []
    if profile.language_style and profile.language_style.summary:
        summaries.append(profile.language_style.summary)
    if profile.reply_pattern and profile.reply_pattern.summary:
        summaries.append(profile.reply_pattern.summary)
    if profile.emotion_dynamic and profile.emotion_dynamic.summary:
        summaries.append(profile.emotion_dynamic.summary)
    if profile.relationship_role and profile.relationship_role.role_description:
        summaries.append(f'在关系中，Ta扮演着 "{profile.relationship_role.role_description}" 的角色。')
    if profile.relationship_role and profile.relationship_role.summary:
        summaries.append(profile.relationship_role.summary)
    if profile.content_themes and profile.content_themes.summary:
        summaries.append(profile.content_themes.summary)

    if summaries:
        lines.append('### 整体印象')
        lines.append('')
        for s in summaries:
            if s.strip():
                lines.append(f'- {s}')
        lines.append('')

    return lines


def _build_language_style_section(profile: PersonalityProfile, cloud_safe: bool) -> list:
    """构建语言风格章节"""
    lp = profile.language_style
    lines = ['## 语言风格', '']

    lines.append('### 基础特征')
    lines.append('')
    lines.append(f'- **平均句长**: {lp.avg_sentence_length:.1f} 字')
    lines.append(f'- **短句比例**: {lp.sentence_length_short_pct:.0f}% (<10字)')
    lines.append(f'- **中等句长**: {lp.sentence_length_medium_pct:.0f}% (10-30字)')
    lines.append(f'- **长句比例**: {lp.sentence_length_long_pct:.0f}% (>30字)')
    lines.append('')

    if lp.top_punctuation:
        lines.append(f'- **高频标点**: {", ".join(lp.top_punctuation)}')
    if lp.common_tone_words:
        lines.append(f'- **常用语气词**: {", ".join(lp.common_tone_words)}')
    if lp.top_phrases:
        lines.append(f'- **口头禅**: {", ".join(lp.top_phrases)}')
    if lp.emoji_usage_rate > 1:
        lines.append(f'- **Emoji/颜文字使用率**: {lp.emoji_usage_rate:.1f}%')
    if lp.english_mix_rate > 1:
        lines.append(f'- **中英混用比例**: {lp.english_mix_rate:.1f}%')

    lines.append('')
    lines.append('### 风格总结')
    lines.append('')
    lines.append(lp.summary)

    # 在 local_full 版本中添加风格指导
    if not cloud_safe:
        lines.append('')
        lines.append('### 模拟指南')
        lines.append('')
        style_rules = []
        if lp.sentence_length_short_pct > 50:
            style_rules.append('- 多用短句，简洁表达，不要写长段落')
        if lp.top_punctuation:
            style_rules.append(f'- 适当使用标点: {", ".join(lp.top_punctuation[:3])}')
        if lp.common_tone_words:
            style_rules.append(f'- 句末或句中自然加入语气词: {", ".join(lp.common_tone_words[:3])}')
        if lp.top_phrases:
            style_rules.append(f'- 偶尔使用口头禅: {", ".join(lp.top_phrases[:3])}')
        lines.extend(style_rules)

    return lines


def _build_reply_pattern_section(profile: PersonalityProfile, cloud_safe: bool) -> list:
    """构建回复模式章节"""
    rp = profile.reply_pattern
    lines = ['## 回复习惯', '']

    if rp.avg_reply_time_seconds:
        avg_sec = rp.avg_reply_time_seconds
        if avg_sec < 60:
            time_desc = f'{avg_sec:.0f} 秒'
        elif avg_sec < 3600:
            time_desc = f'{avg_sec/60:.1f} 分钟'
        else:
            time_desc = f'{avg_sec/3600:.1f} 小时'
        lines.append(f'- **平均回复速度**: {time_desc}')
    lines.append(f'- **快速回复率**: {rp.fast_reply_pct:.0f}% (<30秒内回复)')
    lines.append(f'- **连续多发率**: {rp.multi_reply_rate:.0f}%（喜欢一次发多条消息）')
    lines.append(f'- **提问频率**: {rp.question_rate:.0f}%（回复中带有疑问句的比例）')
    lines.append(f'- **每轮平均回复条数**: {rp.avg_responses_per_turn:.1f}')

    lines.append('')
    lines.append('### 回复模式总结')
    lines.append('')
    lines.append(rp.summary)

    if not cloud_safe:
        lines.append('')
        lines.append('### 模拟指南')
        behavior = []
        if rp.multi_reply_rate > 25:
            behavior.append(f'- 可以分多条短消息连续发送，模拟Ta的真实习惯（每轮{rp.avg_responses_per_turn:.0f}条）')
        if rp.question_rate > 30:
            behavior.append('- 回复中适当加入反问或追问，延续对话')
        if rp.avg_reply_time_seconds and rp.avg_reply_time_seconds < 60:
            behavior.append('- 对方发消息后快速回应，不要长时间延迟')
        lines.extend(behavior)

    return lines


def _build_emotion_dynamic_section(profile: PersonalityProfile, cloud_safe: bool) -> list:
    """构建情感互动章节"""
    ed = profile.emotion_dynamic
    lines = ['## 情感互动模式', '']

    if ed.emotion_response_map:
        lines.append('### 情绪 → 回应策略映射')
        lines.append('')
        emotion_labels = {'sad': '😢 负面/疲惫', 'angry': '😠 愤怒/不满',
                         'happy': '😊 开心/兴奋', 'confused': '🤔 困惑',
                         'love': '💕 亲密/喜欢'}
        strategy_labels = {
            'comfort': '安慰和共情', 'empathy': '认同和理解',
            'distract': '转移注意力', 'humor': '幽默化解',
            'advice': '给建议', 'question_followup': '追问详情',
            'neutral': '中性回应',
        }
        for emotion, strategy in ed.emotion_response_map.items():
            emo_label = emotion_labels.get(emotion, emotion)
            strat_label = strategy_labels.get(strategy, strategy)
            lines.append(f'- 当你表达 **{emo_label}** 时，Ta 倾向于 **{strat_label}**')
        lines.append('')

    lines.append(f'- **共情水平**: {"高" if ed.empathy_level == "high" else "中等" if ed.empathy_level == "medium" else "较低"}')

    lines.append('')
    lines.append('### 情感互动总结')
    lines.append('')
    lines.append(ed.summary)

    if not cloud_safe:
        lines.append('')
        lines.append('### 模拟指南')
        if ed.emotion_response_map.get('sad') == 'comfort':
            lines.append('- 当对方表达负面情绪时，优先给予共情和安慰，而不是急于给建议')
        if ed.emotion_response_map.get('sad') == 'distract':
            lines.append('- 当对方情绪低落时，尝试转移注意力（分享有趣内容、提议活动等）')

    return lines


def _build_relationship_role_section(profile: PersonalityProfile, cloud_safe: bool) -> list:
    """构建关系角色章节"""
    rr = profile.relationship_role
    lines = ['## 关系角色', '']

    lines.append(f'- **角色定位**: {rr.role_description}')
    if rr.initiative_balance:
        lines.append(f'- **回应率**: {rr.initiative_balance.get("response_rate", 0):.0f}%')
    if rr.caregiver_score > 1:
        lines.append(f'- **照顾倾向**: {rr.caregiver_score:.0f}分（关心/建议/安抚类消息占比）')
    if rr.intimacy_markers:
        lines.append(f'- **亲密标记**:')
        for marker in rr.intimacy_markers[:5]:
            lines.append(f'  - {marker}')

    lines.append('')
    lines.append('### 角色描述')
    lines.append('')
    lines.append(rr.summary)

    return lines


def _build_content_themes_section(profile: PersonalityProfile, cloud_safe: bool) -> list:
    """构建话题偏好章节"""
    ct = profile.content_themes
    lines = ['## 话题偏好', '']

    if ct.top_topics:
        lines.append('### 话题热度')
        lines.append('')
        lines.append('| 话题 | 频率 | 对方回应积极性 |')
        lines.append('|------|------|----------------|')
        for t in ct.top_topics[:8]:
            resp_bar = '█' * min(int(t['partner_responsiveness'] * 10), 10)
            lines.append(f'| {t["topic"]} | {t["frequency"]:.0f}% | {resp_bar} {t["partner_responsiveness"]:.0%} |')
        lines.append('')

    if ct.partner_active_topics:
        lines.append(f'- **Ta最积极回应的话题**: {", ".join(ct.partner_active_topics)}')
    if ct.partner_avoided_topics:
        lines.append(f'- **相对回避的话题**: {", ".join(ct.partner_avoided_topics)}')

    lines.append('')
    lines.append('### 话题偏好总结')
    lines.append('')
    lines.append(ct.summary)

    return lines


def _build_dialogue_examples(sample_pairs: list) -> list:
    """构建对话片段示例（仅 local_full 版本）

    选取最多 15 个有代表性（多回复、多种情绪）的对话对作为 few-shot 示例。
    """
    lines = ['## 对话片段示例（精选）', '']
    lines.append('> 以下为真实对话片段，供理解 Ta 的互动风格。请勿外传。')
    lines.append('')

    # 最多展示 15 个
    selected = sample_pairs[:15]
    if not selected:
        lines.append('（无可用对话示例）')
        return lines

    for i, pair in enumerate(selected, 1):
        if not pair.has_response:
            continue
        lines.append(f'### 示例 {i}')
        lines.append('')
        lines.append(f'**你说:** {pair.anchor.content}')
        lines.append('')
        for resp in pair.responses:
            lines.append(f'**Ta 回复:** {resp.content}')
        lines.append('')
        # 注释互动特征
        tags = []
        if pair.is_multi_reply:
            tags.append('连续回复')
        if pair.time_to_first_reply is not None and pair.time_to_first_reply < 30:
            tags.append('秒回')
        if tags:
            lines.append(f'> 互动特征: {", ".join(tags)}')
        lines.append('')

    return lines


def _build_behavior_guide(profile: PersonalityProfile) -> list:
    """构建行为指南（包含在 Skill 提示词中的角色扮演规则）"""
    lines = ['## 角色扮演指南', '']
    lines.append('当使用此 Skill 文件驱动 AI 扮演该角色时，请遵循以下原则：')
    lines.append('')

    rules = ['1. **保持一致性**: 始终按照上述语言风格和互动模式回应，不要跳出角色',
             '2. **隐私边界**: 不要主动提及或猜测"你是通过聊天记录分析得到的"，保持自然对话感']

    if profile.relationship_role and profile.relationship_role.caregiver_score > 10:
        rules.append('3. **照顾者角色**: 自然地在对话中表现出关心和照顾倾向，适时给建议和安慰')

    if profile.reply_pattern and profile.reply_pattern.multi_reply_rate > 25:
        rules.append('4. **碎片化表达**: 可以分多条短消息回复，模拟真人聊天的自然节奏')

    rules.append(f'5. **语气一致**: 使用上述分析中提取的语气词、口头禅和标点习惯')

    if profile.emotion_dynamic:
        sad_strategy = profile.emotion_dynamic.emotion_response_map.get('sad', '')
        if sad_strategy:
            rules.append(f'6. **情绪回应**: 当对方表达负面情绪时，优先使用"{sad_strategy}"策略回应')

    lines.extend(rules)
    return lines
