#!/usr/bin/env python3
"""
微信聊天记录健康诊断工具

功能：
- 从 Windows 注册表自动获取微信文件保存路径（优先）
- 自动探测默认安装路径作为备选
- 扫描 Msg 文件夹中的数据库文件
- 识别异常文件（如 FatalErr、corrupt 后缀）
- 生成可读性强的诊断报告

使用方法：
    python scripts/diagnose_wechat.py
"""

import os
import sys
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


def get_wechat_path_from_registry() -> Optional[str]:
    """
    从 Windows 注册表读取微信文件保存路径
    支持多个可能的注册表键值
    """
    if sys.platform != "win32":
        return None

    try:
        import winreg
    except ImportError:
        print("⚠️ winreg 模块不可用，无法读取注册表")
        return None

    # 可能的注册表路径和键名组合
    registry_locations = [
        (winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", "FileSavePath"),
        (winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", "BaseFolder"),
        (winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", "DataPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Tencent\WeChat", "InstallPath"),
    ]

    for hkey, subkey, value_name in registry_locations:
        try:
            key = winreg.OpenKey(hkey, subkey)
            path, _ = winreg.QueryValueEx(key, value_name)
            winreg.CloseKey(key)
            if path and Path(path).exists():
                return path
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return None


def get_default_wechat_paths() -> List[Path]:
    """返回默认的微信数据存储目录列表"""
    home = Path(os.environ.get("USERPROFILE", "C:/Users/Default"))
    return [
        home / "Documents" / "WeChat Files",      # 3.x 版本
        home / "Documents" / "xwechat_files",     # 4.x 版本
    ]


def find_wechat_data_dirs() -> List[Path]:
    """
    智能探测微信数据目录
    优先级：注册表 > 默认路径
    """
    found = []

    # 1. 尝试从注册表获取
    registry_path = get_wechat_path_from_registry()
    if registry_path:
        reg_path_obj = Path(registry_path)
        # 注册表返回的可能是根目录（如 D:\WeChat Files）
        # 需要进一步探测其下的账号子目录
        if reg_path_obj.exists():
            # 如果直接就是某个账号目录（包含 Msg 文件夹）
            if (reg_path_obj / "Msg").exists():
                found.append(reg_path_obj)
            else:
                # 否则遍历其下的子目录，寻找包含 Msg 的账号目录
                for subdir in reg_path_obj.iterdir():
                    if subdir.is_dir() and (subdir / "Msg").exists():
                        found.append(subdir)

    # 2. 如果注册表没找到，再检查默认路径
    if not found:
        for base in get_default_wechat_paths():
            if base.exists():
                for subdir in base.iterdir():
                    if subdir.is_dir() and (subdir / "Msg").exists():
                        found.append(subdir)

    return found


def scan_msg_directory(msg_dir: Path) -> Dict:
    """扫描 Msg 目录，统计文件状态"""
    result = {
        "total_files": 0,
        "healthy_files": 0,
        "suspicious_files": [],
        "estimated_total_size_mb": 0.0,
    }

    # 收集所有 .db 和 .db.* 文件
    db_files = list(msg_dir.glob("*.db")) + list(msg_dir.glob("*.db.*"))
    for file in db_files:
        size_mb = file.stat().st_size / (1024 * 1024)
        result["estimated_total_size_mb"] += size_mb
        result["total_files"] += 1

        # 检查异常后缀
        suspicious_extensions = [".FatalErr", ".corrupt", ".tmp", ".err", ".bad"]
        is_suspicious = False
        for ext in suspicious_extensions:
            if file.name.endswith(ext):
                is_suspicious = True
                break

        if is_suspicious:
            result["suspicious_files"].append({
                "name": file.name,
                "path": str(file),
                "size_mb": round(size_mb, 2),
                "reason": "异常后缀",
                "suggested_action": "尝试微信自带修复或手动重命名（见文档）"
            })
        else:
            result["healthy_files"] += 1

    result["estimated_total_size_mb"] = round(result["estimated_total_size_mb"], 2)
    return result


def generate_report(wechat_dirs: List[Path]) -> str:
    """生成人类可读的诊断报告"""
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("微信聊天记录健康诊断报告")
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 60)

    # 显示路径来源
    registry_path = get_wechat_path_from_registry()
    if registry_path:
        report_lines.append(f"\n📌 从注册表获取到微信数据根目录: {registry_path}")
    else:
        report_lines.append("\n📌 未从注册表获取到路径，使用默认位置扫描。")

    if not wechat_dirs:
        report_lines.append("\n❌ 未检测到任何微信账号数据目录。")
        report_lines.append("可能的原因：")
        report_lines.append("1. 微信尚未登录过电脑版。")
        report_lines.append("2. 自定义了存储路径且无法通过注册表获取。")
        report_lines.append("3. 数据目录权限不足。")
        return "\n".join(report_lines)

    report_lines.append(f"\n🔍 共发现 {len(wechat_dirs)} 个微信账号数据目录：")

    for wechat_dir in wechat_dirs:
        msg_dir = wechat_dir / "Msg"
        report_lines.append(f"\n📁 账号目录: {wechat_dir.name}")
        report_lines.append(f"   路径: {wechat_dir}")

        if not msg_dir.exists():
            report_lines.append("   ⚠️ Msg 文件夹不存在，可能尚未登录或数据已迁移。")
            continue

        scan_result = scan_msg_directory(msg_dir)
        report_lines.append(f"   📊 文件总数: {scan_result['total_files']}")
        report_lines.append(f"   ✅ 健康文件: {scan_result['healthy_files']}")
        report_lines.append(f"   💾 预估总大小: {scan_result['estimated_total_size_mb']} MB")

        if scan_result["suspicious_files"]:
            report_lines.append(f"   ⚠️ 发现 {len(scan_result['suspicious_files'])} 个可疑文件:")
            for sus in scan_result["suspicious_files"]:
                report_lines.append(f"      - {sus['name']} ({sus['size_mb']} MB)")
                report_lines.append(f"        原因: {sus['reason']}")
                report_lines.append(f"        建议: {sus['suggested_action']}")
        else:
            report_lines.append("   🎉 未发现明显异常文件。")

    report_lines.append("\n" + "=" * 60)
    report_lines.append("📌 下一步建议:")
    report_lines.append("1. 如果存在可疑文件，可尝试微信 PC 端自带的「设置 - 通用设置 - 存储空间管理 - 聊天记录管理」进行修复。")
    report_lines.append("2. 或参考项目文档中的「手动修复数据库文件」章节。")
    report_lines.append("3. 健康数据可继续使用 clean_data.py 进行清洗。")
    report_lines.append("=" * 60)

    return "\n".join(report_lines)


def main():
    # 环境检查
    if sys.platform != "win32":
        print("⚠️ 本工具目前仅支持 Windows 原生 Python 环境。")
        print("如果在 WSL2 中运行，请改用 Windows 版本的 Python 解释器。")
        sys.exit(1)

    wechat_dirs = find_wechat_data_dirs()
    report = generate_report(wechat_dirs)
    print(report)

    # 保存报告到文件
    report_path = Path("wechat_diagnostic_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n📄 报告已保存至: {report_path}")


if __name__ == "__main__":
    main()