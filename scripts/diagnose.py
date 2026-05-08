#!/usr/bin/env python3
"""
跨平台微信/QQ 聊天数据路径探测与健康诊断工具

功能：
    自动探测用户电脑上微信/QQ 聊天数据的存储路径，
    扫描数据库文件并生成健康诊断报告。

探测策略（用户优先）：
    1. 询问用户是否知道路径
    2. 通过系统接口查询（Windows 注册表）
    3. 扫描操作系统默认路径

支持平台：
    - Windows: 微信 v3.x (WeChat Files) / v4.x (xwechat_files)，注册表探测
    - macOS: 微信 (~/Library/Containers/com.tencent.xinWeChat/)
    - Linux: 微信 (Wine/Deepin 常见路径)
    - WSL2: 通过 /mnt/c/ 读取 Windows 侧微信数据

用法：
    python scripts/diagnose.py              # 交互式诊断
    python scripts/diagnose.py --auto       # 自动探测（不询问用户）
    python scripts/diagnose.py --path /path/to/wechat  # 指定路径诊断
"""

import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================
# 平台检测
# ============================================================

def get_platform() -> str:
    """返回当前操作系统平台名称

    Returns:
        'windows', 'macos', 'linux' 之一
    """
    system = platform.system()
    if system == 'Windows':
        return 'windows'
    elif system == 'Darwin':
        return 'macos'
    else:
        return 'linux'


# ============================================================
# 默认路径策略
# ============================================================

def _get_windows_default_wechat_paths() -> List[Path]:
    """获取 Windows 上微信的默认数据目录

    Returns:
        可能的微信数据根目录列表
    """
    home = Path(os.environ.get('USERPROFILE', 'C:\\Users\\Default'))
    candidates = [
        home / 'Documents' / 'WeChat Files',      # 微信 3.x
        home / 'Documents' / 'xwechat_files',      # 微信 4.x
    ]
    return [p for p in candidates if p.exists()]


def _get_macos_default_wechat_paths() -> List[Path]:
    """获取 macOS 上微信的默认数据目录

    macOS 上微信使用沙盒容器存储数据。
    """
    home = Path.home()
    candidates = [
        home / 'Library' / 'Containers' / 'com.tencent.xinWeChat' / 'Data' / 'Library' / 'Application Support' / 'com.tencent.xinWeChat',
    ]
    return [p for p in candidates if p.exists()]


def _get_linux_default_wechat_paths() -> List[Path]:
    """获取 Linux 上微信的默认数据目录

    Linux 上的微信通常通过 Wine/Deepin 运行，路径差异很大。
    这里列出常见的几种情况。
    """
    home = Path.home()
    candidates = [
        # Deepin Wine 微信
        home / '.deepinwine' / 'Deepin-WeChat' / 'drive_c' / 'users' / home.name / 'Documents' / 'WeChat Files',
        # 通用 Wine 微信
        home / '.wine' / 'drive_c' / 'users' / home.name / 'Documents' / 'WeChat Files',
        # 统信 UOS 微信 (deepin 格式)
        home / 'Documents' / 'WeChat Files',
    ]
    return [p for p in candidates if p.exists()]


# ============================================================
# WSL2 检测与路径
# ============================================================

def _is_wsl() -> bool:
    """检测当前是否运行在 WSL (Windows Subsystem for Linux) 环境中

    通过检查 /proc/version 中是否包含 'microsoft' 或 'WSL' 关键字来判断。

    Returns:
        True 表示当前运行在 WSL1 或 WSL2 中
    """
    try:
        with open('/proc/version', 'r') as f:
            version = f.read().lower()
        return 'microsoft' in version or 'wsl' in version
    except (IOError, OSError):
        return False


def _get_wsl_default_wechat_paths() -> List[Path]:
    """在 WSL2 环境中探测 Windows 侧的微信数据目录

    WSL2 中 Windows 磁盘挂载在 /mnt/ 下（如 /mnt/c/、/mnt/d/）。
    遍历所有可见的 Windows 盘符，检查常见的微信数据路径。

    Returns:
        存在且可访问的微信数据根目录列表
    """
    if not _is_wsl():
        return []

    found: List[Path] = []

    # 遍历 /mnt/ 下的所有盘符
    mnt = Path('/mnt')
    if not mnt.exists():
        return found

    for drive in mnt.iterdir():
        if not drive.is_dir():
            continue

        # Windows 用户名目录
        users_dir = drive / 'Users'
        if not users_dir.exists():
            continue

        # 遍历每个用户目录，检查是否有微信数据
        try:
            for user_dir in users_dir.iterdir():
                if not user_dir.is_dir():
                    continue
                # 跳过系统目录
                if user_dir.name in ('Public', 'Default', 'Default User', 'All Users'):
                    continue

                # 微信 3.x 路径
                wechat3 = user_dir / 'Documents' / 'WeChat Files'
                if wechat3.exists():
                    found.append(wechat3)

                # 微信 4.x 路径
                wechat4 = user_dir / 'Documents' / 'xwechat_files'
                if wechat4.exists():
                    found.append(wechat4)
        except PermissionError:
            continue

    return found


# ============================================================
# 系统接口策略（注册表 / plist）
# ============================================================

def _get_windows_registry_wechat_path() -> Optional[Path]:
    """从 Windows 注册表读取微信数据路径

    尝试多个已知的注册表键值，返回第一个存在且有效的路径。

    Returns:
        微信数据根目录路径，若未找到则返回 None
    """
    if platform.system() != 'Windows':
        return None

    try:
        import winreg
    except ImportError:
        return None

    # 注册表探测列表：[(Hive, Subkey, ValueName)]
    probes = [
        (winreg.HKEY_CURRENT_USER, r'Software\Tencent\WeChat', 'FileSavePath'),
        (winreg.HKEY_CURRENT_USER, r'Software\Tencent\WeChat', 'BaseFolder'),
        (winreg.HKEY_CURRENT_USER, r'Software\Tencent\WeChat', 'DataPath'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Tencent\WeChat', 'InstallPath'),
    ]

    for hive, subkey, value_name in probes:
        try:
            key = winreg.OpenKey(hive, subkey)
            value, _ = winreg.QueryValueEx(key, value_name)
            winreg.CloseKey(key)
            if value:
                reg_path = Path(value)
                if reg_path.exists():
                    return reg_path
        except (FileNotFoundError, OSError, Exception):
            continue

    return None


# ============================================================
# 综合探测
# ============================================================

def get_wechat_paths(interactive: bool = True) -> List[Path]:
    """探测本机微信数据目录（用户优先策略）

    探测优先级：
        1. 如果 interactive=True，先询问用户
        2. 系统接口（注册表/plist）
        3. 默认路径扫描
        4. 可选的全盘搜索（需用户确认）

    Args:
        interactive: 是否启用交互式询问

    Returns:
        找到的微信数据根目录列表（去重后）
    """
    found_paths: List[Path] = []
    plt = get_platform()

    # 策略1：询问用户
    if interactive:
        user_path = _ask_user_for_path()
        if user_path:
            found_paths.append(user_path)

    # 策略2：系统接口
    if plt == 'windows':
        registry_path = _get_windows_registry_wechat_path()
        if registry_path and registry_path not in found_paths:
            found_paths.append(registry_path)
    # 策略3：默认路径
    if plt == 'windows':
        default_paths = _get_windows_default_wechat_paths()
    elif plt == 'macos':
        default_paths = _get_macos_default_wechat_paths()
    else:
        default_paths = _get_linux_default_wechat_paths()
        # WSL2 环境下额外检查 Windows 侧微信数据
        if _is_wsl():
            default_paths += _get_wsl_default_wechat_paths()

    for p in default_paths:
        if p not in found_paths:
            found_paths.append(p)

    if interactive and not found_paths:
        print('未找到微信数据目录。请使用 --path 手动指定路径。')

    return found_paths


def find_wechat_data_dirs(root_path: Optional[Path] = None, interactive: bool = True) -> List[Path]:
    """在给定的根目录下查找包含 Msg/ 子目录的微信账号数据目录

    如果 root_path 本身直接包含 Msg/，则将其视为一个账号目录。
    否则，遍历 root_path 的子目录，查找包含 Msg/ 的目录。

    Args:
        root_path: 微信数据根目录；为 None 时自动探测
        interactive: 是否交互式询问

    Returns:
        微信账号数据目录列表（每个都包含 Msg/ 子目录）
    """
    if root_path is None:
        root_paths = get_wechat_paths(interactive=interactive)
    else:
        root_paths = [root_path]

    account_dirs: List[Path] = []

    for root in root_paths:
        if not root.exists():
            continue

        # 如果 root 本身直接包含 Msg/，它就是一个账号目录
        if (root / 'Msg').exists():
            account_dirs.append(root)
            continue

        # 否则遍历子目录
        try:
            for subdir in root.iterdir():
                if subdir.is_dir() and (subdir / 'Msg').exists():
                    account_dirs.append(subdir)
        except PermissionError:
            continue

    return account_dirs


# ============================================================
# 用户交互函数
# ============================================================

def _ask_user_for_path() -> Optional[Path]:
    """询问用户是否知道微信数据路径"""
    print()
    print('=' * 60)
    print('  AI-Companion-Local — 微信数据路径探测')
    print('=' * 60)
    print()
    print('请选择：')
    print('  1. 我知道微信数据路径 → 手动输入')
    print('  2. 我不知道 → 自动探测')
    print()
    choice = input('请输入选项 (1/2，默认 2): ').strip()

    if choice == '1':
        user_input = input('请输入微信数据目录路径: ').strip()
        if user_input:
            p = Path(user_input).expanduser().resolve()
            if p.exists():
                return p
            else:
                print(f'[警告] 路径不存在: {p}')
    return None


# ============================================================
# Msg 目录扫描
# ============================================================

# 可疑文件后缀列表
SUSPICIOUS_EXTENSIONS = {'.FatalErr', '.corrupt', '.tmp', '.err', '.bad', '.lock', '.journal'}


def scan_msg_directory(msg_dir: Path) -> Dict:
    """扫描微信 Msg/ 目录，统计文件健康状况

    对目录下的 .db 和 .db.* 文件进行计数和大小统计，
    并标记可能损坏的文件（依据后缀名）。

    Args:
        msg_dir: Msg 目录的路径

    Returns:
        包含以下字段的字典：
            - total_files: 总文件数
            - healthy_files: 健康文件数
            - suspicious_files: 可疑文件详情列表
            - estimated_total_size_mb: 预估总大小（MB）
    """
    if not msg_dir.exists():
        return {
            'total_files': 0,
            'healthy_files': 0,
            'suspicious_files': [],
            'estimated_total_size_mb': 0.0,
        }

    total_files = 0
    healthy_files = 0
    suspicious_files: List[Dict] = []
    total_size_bytes = 0

    # 扫描 .db 和 .db.* 文件
    for f in msg_dir.iterdir():
        if not f.is_file():
            continue

        name = f.name.lower()
        # 只关注数据库相关文件
        if not (name.endswith('.db') or '.db.' in name):
            continue

        total_files += 1
        file_size = f.stat().st_size
        total_size_bytes += file_size

        # 检查是否可疑
        is_suspicious = False
        for ext in SUSPICIOUS_EXTENSIONS:
            if ext.lower() in name:
                is_suspicious = True
                suspicious_files.append({
                    'name': f.name,
                    'path': str(f),
                    'size_mb': round(file_size / (1024 * 1024), 2),
                    'reason': f'异常文件后缀 ({ext})',
                    'suggested_action': '建议使用微信自带的修复工具或手动备份后重命名',
                })
                break

        if not is_suspicious:
            healthy_files += 1

    return {
        'total_files': total_files,
        'healthy_files': healthy_files,
        'suspicious_files': suspicious_files,
        'estimated_total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
    }


# ============================================================
# 报告生成
# ============================================================

def generate_qq_report(json_path: Path, file_stats: Dict) -> str:
    """生成 QQ JSON 导出文件的验证报告"""
    lines: List[str] = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines.append('=' * 60)
    lines.append('  QQ 聊天记录导出验证报告 (QCE)')
    lines.append(f'  生成时间: {now}')
    lines.append('=' * 60)
    lines.append('')
    lines.append(f'  文件: {json_path}')
    lines.append(f'  文件大小: {file_stats["file_size_mb"]} MB')

    chat_info = file_stats.get('chat_info')
    if chat_info:
        lines.append(f'  聊天对象: {chat_info["chat_name"]}')
        lines.append(f'  聊天类型: {chat_info["chat_type"]}')

    self_name = file_stats.get('self_name')
    if self_name:
        lines.append(f'  导出者: {self_name}')

    lines.append(f'  总消息数: {file_stats["total_messages"]}')
    lines.append(f'  有效消息: {file_stats["valid_messages"]}')
    lines.append(f'  说话人数: {file_stats["unique_speakers"]}')
    lines.append('')

    if file_stats['speakers']:
        lines.append('  说话人统计:')
        for name, count in file_stats['speakers'].most_common(10):
            lines.append(f'    - {name}: {count} 条')
        lines.append('')

    date_start = file_stats.get('date_start')
    date_end = file_stats.get('date_end')
    if date_start and date_end:
        lines.append(f'  时间范围: {date_start} ~ {date_end}')
        lines.append('')

    if file_stats['errors']:
        lines.append(f'  [!] 发现 {len(file_stats["errors"])} 个问题:')
        for err in file_stats['errors']:
            lines.append(f'      - {err}')
        lines.append('')
    else:
        lines.append('  [OK] 文件格式正常，可以用于后续处理。')
        lines.append('')

    lines.append('  下一步：')
    lines.append(f'    python scripts/clean_data.py --input "{json_path}"')
    lines.append('    python scripts/wizard.py')
    lines.append('')

    return '\n'.join(lines)


def validate_qq_export(json_path: Path) -> Dict:
    """验证 QCE (QQ Chat Exporter) 导出的 JSON 文件

    检查 QCE JSON 结构、messages 数组、必要字段，统计基础信息。

    Returns:
        包含 total_messages, valid_messages, unique_speakers,
        speakers (Counter), file_size_mb, date_start, date_end, errors,
        chat_info, self_name 的字典
    """
    from collections import Counter

    stats: Dict = {
        'total_messages': 0,
        'valid_messages': 0,
        'unique_speakers': 0,
        'speakers': Counter(),
        'file_size_mb': 0,
        'date_start': None,
        'date_end': None,
        'chat_info': None,
        'self_name': None,
        'errors': [],
    }

    if not json_path.exists():
        stats['errors'].append(f'文件不存在: {json_path}')
        return stats

    file_size = json_path.stat().st_size
    stats['file_size_mb'] = round(file_size / (1024 * 1024), 2)

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        stats['errors'].append(f'JSON 解析失败: {e}')
        return stats
    except UnicodeDecodeError:
        try:
            with open(json_path, 'r', encoding='gbk') as f:
                data = json.load(f)
        except Exception as e:
            stats['errors'].append(f'编码检测失败: {e}')
            return stats

    if not isinstance(data, dict):
        stats['errors'].append('JSON 顶层不是对象（dict）')
        return stats

    # 检查 QCE 必需字段
    if 'messages' not in data:
        stats['errors'].append("缺少 'messages' 字段，请确认是 QCE 导出的 JSON 文件")
        return stats
    if 'chatInfo' not in data:
        stats['errors'].append("缺少 'chatInfo' 字段，请确认是 QCE 导出的 JSON 文件")
        return stats

    chat_info = data['chatInfo']
    stats['chat_info'] = {
        'chat_name': chat_info.get('chatName', '未知'),
        'chat_type': chat_info.get('chatType', '未知'),
    }

    export_meta = data.get('exportMetadata', {})
    stats['self_name'] = export_meta.get('selfName')

    messages = data['messages']
    if not isinstance(messages, list):
        stats['errors'].append("'messages' 不是数组")
        return stats

    stats['total_messages'] = len(messages)

    timestamps = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        sender = (msg.get('senderName') or '').strip()
        msg_type = (msg.get('msgType') or 'text').strip()

        if msg_type == 'system':
            continue

        if sender:
            stats['speakers'][sender] += 1

        time_raw = msg.get('timestamp')
        if time_raw:
            try:
                from .base import parse_datetime
                parsed = parse_datetime(str(time_raw))
                timestamps.append(parsed)
            except ValueError:
                pass

    stats['valid_messages'] = sum(stats['speakers'].values())
    stats['unique_speakers'] = len(stats['speakers'])

    if timestamps:
        stats['date_start'] = min(timestamps).isoformat()
        stats['date_end'] = max(timestamps).isoformat()

    if stats['valid_messages'] == 0:
        stats['errors'].append('没有解析到有效的文本消息')

    return stats
    """生成微信聊天数据健康诊断报告

    Args:
        wechat_dirs: 微信账号数据目录列表

    Returns:
        格式化的诊断报告字符串
    """
    lines: List[str] = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines.append('=' * 60)
    lines.append('  微信聊天记录健康诊断报告')
    lines.append(f'  生成时间: {now}')
    lines.append(f'  运行平台: {platform.system()} {platform.release()}')
    lines.append('=' * 60)
    lines.append('')

    if not wechat_dirs:
        lines.append('[!] 未找到微信数据目录。')
        lines.append('')
        lines.append('可能的原因：')
        lines.append('  1. 微信未安装或未登录过')
        lines.append('  2. 微信数据存储在非默认位置')
        lines.append('  3. 当前平台不支持自动探测')
        lines.append('')
        lines.append('建议：手动指定微信数据路径')
        lines.append('  python scripts/diagnose.py --path "你的微信数据目录"')
        return '\n'.join(lines)

    lines.append(f'[OK] 共发现 {len(wechat_dirs)} 个微信账号数据目录：')
    lines.append('')

    total_healthy = 0
    total_suspicious = 0
    grand_total_size = 0.0

    for i, data_dir in enumerate(wechat_dirs, 1):
        msg_dir = data_dir / 'Msg'
        stats = scan_msg_directory(msg_dir)

        total_healthy += stats['healthy_files']
        total_suspicious += len(stats['suspicious_files'])
        grand_total_size += stats['estimated_total_size_mb']

        lines.append(f'--- 账号 {i}: {data_dir.name} ---')
        lines.append(f'  路径: {data_dir}')
        lines.append(f'  数据文件总数: {stats["total_files"]}')
        lines.append(f'  健康文件: {stats["healthy_files"]}')
        lines.append(f'  预估总大小: {stats["estimated_total_size_mb"]} MB')

        if stats['suspicious_files']:
            lines.append(f'  [!] 发现 {len(stats["suspicious_files"])} 个可疑文件:')
            for sf in stats['suspicious_files']:
                lines.append(f'      - {sf["name"]} ({sf["size_mb"]} MB)')
                lines.append(f'        原因: {sf["reason"]}')
                lines.append(f'        建议: {sf["suggested_action"]}')
        else:
            lines.append(f'  [OK] 未发现异常文件')
        lines.append('')

    # 汇总
    lines.append('=' * 60)
    lines.append('  汇总')
    lines.append('=' * 60)
    lines.append(f'  总数据文件: {total_healthy + total_suspicious}')
    lines.append(f'  健康文件: {total_healthy}')
    lines.append(f'  可疑文件: {total_suspicious}')
    lines.append(f'  预估总大小: {grand_total_size:.2f} MB')
    lines.append('')

    if total_suspicious > 0:
        lines.append('[!] 存在可疑文件，建议处理后再进行数据分析。')
    else:
        lines.append('[OK] 所有数据文件状态正常。')

    lines.append('')
    lines.append('下一步：')
    lines.append('  1. 导出聊天记录: 微信 → 聊天记录 → 导出 → CSV')
    lines.append('  2. 运行数据清洗: python scripts/clean_data.py')
    lines.append('  3. 生成人格 Skill: python scripts/generate_skill.py（即将推出）')
    lines.append('')

    return '\n'.join(lines)


def save_report(report: str, output_path: Optional[Path] = None) -> Path:
    """保存诊断报告到文件

    Args:
        report: 报告文本内容
        output_path: 输出文件路径；默认为当前目录下的 diagnostic_report.txt

    Returns:
        报告文件的路径
    """
    if output_path is None:
        output_path = Path.cwd() / 'diagnostic_report.txt'

    output_path.write_text(report, encoding='utf-8')
    return output_path


# ============================================================
# 主入口
# ============================================================

def main():
    """命令行入口：诊断微信数据路径和文件健康状况"""
    import argparse

    parser = argparse.ArgumentParser(
        description='AI-Companion-Local 微信数据路径诊断工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python scripts/diagnose.py                    # 交互式诊断
  python scripts/diagnose.py --auto             # 自动探测
  python scripts/diagnose.py --path D:/WeChat   # 指定路径
        '''
    )
    parser.add_argument('--auto', action='store_true',
                        help='自动探测，不询问用户')
    parser.add_argument('--path', type=str, default=None,
                        help='手动指定微信数据根目录路径')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='报告输出路径（默认: diagnostic_report.txt）')
    parser.add_argument('--qq', action='store_true',
                        help='QQ 模式：验证 QCE (QQ Chat Exporter) 导出的 JSON 文件（需配合 --path）')

    args = parser.parse_args()

    # QQ 模式：验证导出的 JSON 文件
    if args.qq:
        if not args.path:
            print('[错误] QQ 模式需要 --path 指定导出的 JSON 文件路径。')
            print('  用法: python scripts/diagnose.py --qq --path export.json')
            sys.exit(1)
        json_path = Path(args.path).expanduser().resolve()
        if not json_path.exists():
            print(f'[错误] 文件不存在: {json_path}')
            sys.exit(1)
        stats = validate_qq_export(json_path)
        report = generate_qq_report(json_path, stats)
        print(report)
        output_path = Path(args.output) if args.output else Path('qq_diagnostic_report.txt')
        saved_path = save_report(report, output_path)
        print(f'报告已保存至: {saved_path}')
        return

    # 打印运行环境信息
    print(f'检测到平台: {platform.system()} {platform.release()}')
    print(f'Python 版本: {sys.version.split()[0]}')
    print()

    # 确定探测路径
    if args.path:
        root_path = Path(args.path).expanduser().resolve()
        if not root_path.exists():
            print(f'[错误] 指定的路径不存在: {root_path}')
            sys.exit(1)
        wechat_dirs = find_wechat_data_dirs(root_path=root_path, interactive=False)
    else:
        wechat_dirs = find_wechat_data_dirs(interactive=not args.auto)

    # 生成并展示报告
    report = generate_report(wechat_dirs)
    print(report)

    # 保存报告
    output_path = Path(args.output) if args.output else None
    saved_path = save_report(report, output_path)
    print(f'报告已保存至: {saved_path}')


if __name__ == '__main__':
    main()
