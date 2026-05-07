#!/usr/bin/env python3
"""
人格 Skill 文件生成器 — 一键端到端入口

从 Phase 1 输出的清洗数据中，自动生成完整的人格 Skill Markdown 文件。

流程：
    1. 加载 sessions.json + speaker_mapping.json
    2. 构建上下文窗口对话对
    3. 运行 5 维度互动模式分析
    4. 生成双版本 Skill Markdown 报告

用法：
    python scripts/generate_skill.py                          # 默认输入 data/processed/
    python scripts/generate_skill.py --input-dir data/processed/
    python scripts/generate_skill.py --target "小明" --output-dir output/
    python scripts/generate_skill.py --window 8 --time-window 15
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# 项目路径设置
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from skill_gen.pair_builder import build_pairs, load_sessions_and_mapping
from skill_gen.analyzers import get_all_analyzers, PersonalityProfile
from skill_gen.report_generator import generate_skill_markdown


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='AI-Companion-Local 人格 Skill 文件生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python scripts/generate_skill.py
  python scripts/generate_skill.py --input-dir data/processed/
  python scripts/generate_skill.py --window 8 --time-window 15
        '''
    )
    parser.add_argument('--input-dir', '-i', type=str, default='data/processed',
                        help='Phase 1 输出目录（默认: data/processed）')
    parser.add_argument('--output-dir', '-o', type=str, default='data/processed',
                        help='Skill 文件输出目录（默认: data/processed）')
    parser.add_argument('--window', '-w', type=int, default=5,
                        help='上下文消息窗口大小（默认: 5）')
    parser.add_argument('--time-window', '-t', type=int, default=10,
                        help='上下文时间窗口，分钟（默认: 10）')
    parser.add_argument('--target', type=str, default=None,
                        help='目标对象名称（覆盖 speaker_mapping.json 中的设置）')
    parser.add_argument('--cloud-only', action='store_true',
                        help='仅生成 cloud-safe 版本')
    parser.add_argument('--local-only', action='store_true',
                        help='仅生成 local-full 版本')

    args = parser.parse_args()

    input_dir = (_PROJECT_ROOT / args.input_dir).resolve()
    output_dir = (_PROJECT_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print('=' * 55)
    print('  AI-Companion-Local 人格 Skill 生成器')
    print('=' * 55)
    print()

    # ---- 步骤1：加载数据 ----
    print('[1/5] 加载 Phase 1 输出数据...')
    try:
        sessions, my_name, partner_name = load_sessions_and_mapping(input_dir)
    except FileNotFoundError as e:
        print(f'[错误] {e}')
        sys.exit(1)

    if args.target:
        partner_name = args.target

    # 加载统计信息
    stats_path = input_dir / 'stats.json'
    source_summary = {}
    if stats_path.exists():
        with open(stats_path, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        source_summary = {
            'message_count': stats.get('cleaned_count', len(sessions)),
            'session_count': stats.get('session_count', len(sessions)),
            'date_range': stats.get('date_range', {}),
            'my_name': my_name,
            'partner_name': partner_name,
        }

    print(f'  数据来源: {len(sessions)} 个会话')
    print(f'  我: "{my_name}" → Ta: "{partner_name}"')
    print()

    # ---- 步骤2：构建对话对 ----
    print(f'[2/5] 构建对话对（窗口: {args.window}条/{args.time_window}分钟）...')
    collection = build_pairs(
        sessions,
        my_name=my_name,
        partner_name=partner_name,
        window_size=args.window,
        time_window_minutes=args.time_window,
    )

    pair_stats = collection.stats()
    print(f'  生成 {pair_stats["total_pairs"]} 个对话对')
    print(f'  有回复: {pair_stats["pairs_with_response"]} 个')
    print(f'  多回复率: {pair_stats["multi_reply_rate"]}')
    print(f'  平均回复数: {pair_stats["avg_responses_per_pair"]}')
    print()

    # ---- 步骤3：运行分析器 ----
    print('[3/5] 运行互动模式分析...')
    profile = PersonalityProfile(
        target_name=partner_name,
        source_summary=source_summary,
    )

    analyzers = get_all_analyzers()
    for name, analyze_fn in analyzers:
        print(f'  - {name}分析中...')
        analyze_fn(collection, profile)

    if profile.is_empty():
        print('[错误] 所有分析器均未产生结果，请检查数据量是否足够。')
        sys.exit(1)
    print()

    # ---- 步骤4：生成报告 ----
    print('[4/5] 生成 Skill Markdown 文件...')

    generated_files: List[Path] = []

    if not args.local_only:
        cloud_path = output_dir / f'skill_{partner_name}_cloud_safe.md'
        generate_skill_markdown(profile, cloud_path, include_examples=False)
        generated_files.append(cloud_path)
        print(f'  [Cloud-Safe] {cloud_path}')
        print(f'    → 可安全粘贴到 ChatGPT/DeepSeek 等云端服务')

    if not args.cloud_only:
        sample_pairs = _select_sample_pairs(collection, max_count=15)
        local_path = output_dir / f'skill_{partner_name}_local_full.md'
        generate_skill_markdown(profile, local_path, include_examples=True, sample_pairs=sample_pairs)
        generated_files.append(local_path)
        print(f'  [Local-Full] {local_path}')
        print(f'    → 包含 {len(sample_pairs)} 个对话片段示例，仅供本地使用')

    print()

    # ---- 步骤5：保存分析结果 JSON ----
    print('[5/5] 保存分析中间结果...')
    analysis_json_path = output_dir / f'analysis_{partner_name}.json'
    _save_analysis_json(profile, collection, analysis_json_path)
    print(f'  分析数据: {analysis_json_path}')
    print()

    # ---- 完成 ----
    print('=' * 55)
    print('  生成完成！')
    print('=' * 55)
    print()
    for f in generated_files:
        print(f'  📄 {f}')
    print()
    print('  使用方式:')
    print('    1. 将 cloud_safe.md 的内容粘贴到 ChatGPT/DeepSeek 的自定义指令中')
    print('    2. 将 local_full.md 的内容用于本地 Ollama 模型的 System Prompt')
    print('    3. 分析中间结果可用于后续微调数据筛选')
    print()


def _select_sample_pairs(collection, max_count: int = 15) -> list:
    """选取有代表性的对话对作为 few-shot 示例

    优先选择：多回复的 > 有情感内容的 > 随机补充
    """
    candidates = list(collection.pairs_with_response)

    # 按优先级排序：多回复优先
    multi = [p for p in candidates if p.is_multi_reply]
    single = [p for p in candidates if not p.is_multi_reply]

    selected = multi[:max_count]
    remaining = max_count - len(selected)
    if remaining > 0:
        selected += single[:remaining]

    return selected


def _save_analysis_json(profile: PersonalityProfile, collection, output_path: Path):
    """将分析结果序列化为 JSON（供调试和后续使用）"""
    # 将 profile 转为可序列化的字典
    data: Dict[str, Any] = {
        'target_name': profile.target_name,
        'source_summary': profile.source_summary,
        'pair_stats': collection.stats(),
        'generated_at': datetime.now().isoformat(),
    }

    if profile.language_style:
        ls = profile.language_style
        data['language_style'] = {
            'avg_sentence_length': ls.avg_sentence_length,
            'sentence_distribution': {
                'short': f'{ls.sentence_length_short_pct:.1f}%',
                'medium': f'{ls.sentence_length_medium_pct:.1f}%',
                'long': f'{ls.sentence_length_long_pct:.1f}%',
            },
            'top_punctuation': ls.top_punctuation,
            'common_tone_words': ls.common_tone_words,
            'top_phrases': ls.top_phrases,
            'emoji_usage_rate': f'{ls.emoji_usage_rate:.1f}%',
            'english_mix_rate': f'{ls.english_mix_rate:.1f}%',
            'summary': ls.summary,
        }

    if profile.reply_pattern:
        rp = profile.reply_pattern
        data['reply_pattern'] = {
            'avg_reply_time_seconds': rp.avg_reply_time_seconds,
            'fast_reply_pct': f'{rp.fast_reply_pct:.1f}%',
            'multi_reply_rate': f'{rp.multi_reply_rate:.1f}%',
            'question_rate': f'{rp.question_rate:.1f}%',
            'avg_responses_per_turn': f'{rp.avg_responses_per_turn:.1f}',
            'summary': rp.summary,
        }

    if profile.emotion_dynamic:
        ed = profile.emotion_dynamic
        data['emotion_dynamic'] = {
            'emotion_response_map': ed.emotion_response_map,
            'empathy_level': ed.empathy_level,
            'comfort_tendency': f'{ed.comfort_tendency:.2f}',
            'humor_tendency': f'{ed.humor_tendency:.2f}',
            'summary': ed.summary,
        }

    if profile.relationship_role:
        rr = profile.relationship_role
        data['relationship_role'] = {
            'role_description': rr.role_description,
            'caregiver_score': f'{rr.caregiver_score:.1f}',
            'intimacy_markers': rr.intimacy_markers,
            'response_rate': f'{rr.initiative_balance.get("response_rate", 0):.1f}%',
            'summary': rr.summary,
        }

    if profile.content_themes:
        ct = profile.content_themes
        data['content_themes'] = {
            'top_topics': ct.top_topics,
            'partner_active_topics': ct.partner_active_topics,
            'partner_avoided_topics': ct.partner_avoided_topics,
            'summary': ct.summary,
        }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
