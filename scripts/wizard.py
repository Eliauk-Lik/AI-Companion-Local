#!/usr/bin/env python3
"""
AI-Companion-Local 交互式 CLI 向导

为零基础用户提供一步到位的交互式引导，降低首次使用门槛。

功能流程：
    1. 欢迎页 → 询问要"复活"谁
    2. 选择聊天平台（微信/QQ）
    3. 选择聊天范围（私聊/群聊/全部）
    4. 调用 diagnose 探测路径，让用户选择
    5. 确认参数 → 串联执行解析 → 清洗 → 保存
    6. 完成提示 + 下一步指引

运行配置会保存到 data/processed/wizard_config.json，供后续模块复用。

用法：
    python scripts/wizard.py              # 交互式引导
    python scripts/wizard.py --config config.json  # 使用已有配置
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# 交互式问题
# ============================================================

def ask_name() -> str:
    """询问要分析的目标对象"""
    print()
    print('─' * 50)
    print()
    name = input('  你想"复活"谁的聊天风格？请输入 TA 的名字或昵称: ').strip()
    while not name:
        print('  名字不能为空，请输入。')
        name = input('  TA 的名字或昵称: ').strip()
    return name


def ask_platform() -> str:
    """询问聊天平台"""
    print()
    print('─' * 50)
    print()
    print('  请选择聊天平台:')
    print('    [1] 微信')
    print('    [2] QQ')
    print()
    choice = input('  请输入选项 (1/2，默认 1): ').strip()

    if choice == '2':
        return 'qq'
    return 'wechat'


def ask_chat_scope() -> str:
    """询问聊天范围"""
    print()
    print('─' * 50)
    print()
    print('  请选择聊天范围:')
    print('    [1] 仅私聊（推荐，分析最准确）')
    print('    [2] 仅群聊（分析 TA 在群里的表现）')
    print('    [3] 全部（私聊 + 群聊都包含）')
    print()
    choice = input('  请输入选项 (1/2/3，默认 1): ').strip()

    if choice == '2':
        return 'group_only'
    elif choice == '3':
        return 'all'
    return 'private_only'


def ask_chat_file() -> Optional[Path]:
    """询问聊天记录文件路径"""
    print()
    print('─' * 50)
    print()
    print('  请提供聊天记录文件:')
    print('   （微信：通过聊天窗口 → 导出聊天记录 → CSV 格式导出）')
    print('   （QQ：通过消息管理器 → 导出消息记录 → JSON 格式导出）')
    print()
    print('  你可以直接把文件拖到终端窗口，或输入文件路径。')
    print()

    while True:
        path_str = input('  聊天记录文件路径（回车跳过，稍后手动处理）: ').strip()
        if not path_str:
            return None

        p = Path(path_str).expanduser().resolve()
        if p.exists() and p.is_file():
            return p
        else:
            print(f'  [警告] 文件不存在: {p}')
            retry = input('  重新输入？(Y/n): ').strip().lower()
            if retry in ('n', 'no', '不'):
                return None


def ask_time_range() -> Optional[str]:
    """询问数据时间范围（可选）"""
    print()
    print('─' * 50)
    print()
    print('  数据时间范围（可选，用于过滤过旧的聊天记录）:')
    print('   [1] 全部数据')
    print('   [2] 最近一年')
    print('   [3] 最近半年')
    print('   [4] 自定义范围')
    print()
    choice = input('  请输入选项 (1/2/3/4，默认 1): ').strip()

    if choice == '2':
        return 'last_year'
    elif choice == '3':
        return 'last_6_months'
    elif choice == '4':
        start = input('  起始日期 (格式: 2024-01-01): ').strip()
        end = input('  结束日期 (格式: 2024-12-31，回车=至今): ').strip()
        if start:
            return f'{start}/{end if end else "now"}'
    return 'all'


# ============================================================
# 参数确认
# ============================================================

def confirm_params(params: Dict[str, Any]) -> bool:
    """展示所有收集的参数，让用户确认"""
    print()
    print('=' * 50)
    print('  参数确认')
    print('=' * 50)
    print()
    print(f'  目标对象:     {params["target_name"]}')
    print(f'  聊天平台:     {params["platform"]}')
    print(f'  聊天范围:     {params["chat_scope"]}')
    if params.get('chat_file'):
        print(f'  聊天文件:     {params["chat_file"]}')
    else:
        print(f'  聊天文件:     (稍后手动处理)')
    print(f'  时间范围:     {params["time_range"]}')
    print()

    answer = input('  以上信息是否正确？(Y/n): ').strip().lower()
    return answer not in ('n', 'no', '不')


# ============================================================
# 数据处理
# ============================================================



def run_clean_data(chat_file: Path, params: Dict[str, Any]) -> bool:
    """运行 clean_data.py 处理聊天记录

    Args:
        chat_file: 聊天记录文件路径
        params: 用户配置参数

    Returns:
        处理是否成功
    """
    print()
    print('─' * 50)
    print()
    print(f'  开始处理聊天记录: {chat_file.name}')
    print(f'  目标对象: {params["target_name"]}')
    print()

    clean_script = _PROJECT_ROOT / 'scripts' / 'clean_data.py'
    output_dir = _PROJECT_ROOT / 'data' / 'processed'

    cmd = [
        sys.executable, str(clean_script),
        '--input', str(chat_file),
        '--output-dir', str(output_dir),
        '--partner', params['target_name'],
        '--no-interactive',
    ]

    print(f'  正在运行: {" ".join(cmd[2:])}')
    print()
    print('  ' + '-' * 40)

    try:
        result = subprocess.run(
            cmd,
            text=True,
            timeout=120,
            cwd=str(_PROJECT_ROOT),
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print('  [错误] 数据处理超时。')
        print('  提示：如果文件较大，可以先用 --no-interactive 模式独立运行 clean_data.py。')
        return False
    except FileNotFoundError:
        print('  [错误] clean_data.py 未找到。')
        return False


# ============================================================
# 配置保存
# ============================================================

def save_wizard_config(params: Dict[str, Any]) -> Path:
    """保存向导配置供后续模块使用"""
    config_dir = _PROJECT_ROOT / 'data' / 'processed'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'wizard_config.json'

    config = {
        **params,
        'created_at': datetime.now().isoformat(),
        'version': '1.0',
    }

    # 将 Path 对象转为字符串
    if config.get('chat_file') and isinstance(config['chat_file'], Path):
        config['chat_file'] = str(config['chat_file'])

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    return config_path


# ============================================================
# 完成提示
# ============================================================

def print_completion(params: Dict[str, Any], output_dir: Path):
    """打印完成提示和下一步引导"""
    print()
    print('=' * 55)
    print('   🎉 数据准备完成！')
    print('=' * 55)
    print()
    print(f'  目标对象 "{params["target_name"]}" 的聊天数据已处理完毕。')
    print(f'  输出目录: {output_dir}')
    print()
    print('  ┌─────────────────────────────────────────┐')
    print('  │  下一步:                                 │')
    print('  │                                          │')
    print('  │  1. 生成人格 Skill 文件                   │')
    print('  │     python scripts/generate_skill.py      │')
    print('  │     （即将推出，敬请期待）                  │')
    print('  │                                          │')
    print('  │  2. 启动本地 AI 对话伴侣                    │')
    print('  │     python bot/main.py                    │')
    print('  │     （请先确保 Ollama 已启动并加载模型）       │')
    print('  │                                          │')
    print('  │  3. 微调专属模型（硬核用户）                  │')
    print('  │     参考 finetune/configs/qlora_config.yaml │')
    print('  └─────────────────────────────────────────┘')
    print()
    print('  感谢使用 AI-Companion-Local ！')
    print('  所有数据处理均在本地完成，你的隐私是安全的。')
    print()


# ============================================================
# 主入口
# ============================================================

def main():
    """交互式向导主入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description='AI-Companion-Local 交互式引导向导',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--config', type=str, default=None,
                        help='使用已有的配置文件跳过交互')
    args = parser.parse_args()

    # 使用已有配置
    if args.config:
        config_path = Path(args.config).expanduser().resolve()
        if not config_path.exists():
            print(f'[错误] 配置文件不存在: {config_path}')
            sys.exit(1)
        with open(config_path, 'r', encoding='utf-8') as f:
            params = json.load(f)
        print(f'已加载配置: {config_path}')
    else:
        # ---- 欢迎页 ----
        print()
        print('=' * 55)
        print('    AI-Companion-Local')
        print('    让你的 AI 伴侣真正"像 TA"')
        print('=' * 55)
        print()
        print('  本向导将引导你完成以下步骤：')
        print('    1. 指定要分析的对象')
        print('    2. 提供聊天记录文件')
        print('    3. 自动清洗和结构化处理')
        print()
        print('  [隐私提示] 所有处理在你本机完成，不上传任何数据。')
        print()

        input('  按 Enter 开始...')

        # ---- 收集参数 ----
        target_name = ask_name()
        platform = ask_platform()
        chat_scope = ask_chat_scope()
        chat_file = ask_chat_file()
        time_range = ask_time_range()

        params = {
            'target_name': target_name,
            'platform': platform,
            'chat_scope': chat_scope,
            'chat_file': chat_file,
            'time_range': time_range,
        }

        # ---- 确认参数 ----
        if not confirm_params(params):
            print()
            print('  已取消。请重新运行: python scripts/wizard.py')
            sys.exit(0)

    # ---- 保存配置 ----
    config_path = save_wizard_config(params)
    print(f'  配置已保存: {config_path}')

    # ---- 执行数据处理 ----
    chat_file = params.get('chat_file')
    if chat_file:
        chat_file = Path(chat_file)
        if chat_file.exists():
            success = run_clean_data(chat_file, params)
            if not success:
                print()
                print('  [警告] 数据处理未完全成功。')
                print('  你可以尝试手动运行:')
                print(f'    python scripts/clean_data.py --input "{chat_file}"')
        else:
            print()
            print(f'  [警告] 聊天文件不存在: {chat_file}')
            print('  请确保文件路径正确，然后手动运行:')
            print(f'    python scripts/clean_data.py --input "你的文件路径"')
    else:
        print()
        print('  你选择了跳过文件处理。')
        print('  准备好后，请使用以下命令处理聊天记录:')
        print('    python scripts/clean_data.py --input "你的聊天记录文件"')

    # ---- 完成 ----
    print_completion(params, _PROJECT_ROOT / 'data' / 'processed')


if __name__ == '__main__':
    main()
