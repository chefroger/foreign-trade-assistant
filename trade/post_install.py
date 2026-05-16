"""
post_install: Install Trade B2B skills into Hermes skills directory.

Called via:
  - `pip install -e .` or `pip install .` (setuptools post-installation)
  - Or manually: `install-trade-skills` (declared as project console script)

This module runs OUTSIDE the package import graph — it uses only stdlib
to avoid version/import conflicts between the package and hermes-agent.

It copies skills from:
  {package_location}/skills/b2b-*/
  → ~/.hermes/skills/b2b-*/

Hermes discovers skills from ~/.hermes/skills/ (via get_all_skills_dirs()).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _get_hermes_home() -> Path:
    """Mirror hermes_constants.get_hermes_home(), no import dependency."""
    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        return Path(val)
    return Path.home() / ".hermes"


def _get_trade_home() -> Path:
    """返回用户 Trade 数据目录（与 database.py / company.py / prompts.py 统一）。

    Priority: TRADE_HOME env var → platform default.
    macOS/Linux: ~/.trade/, Windows: %LOCALAPPDATA%\trade\
    """
    val = os.environ.get("TRADE_HOME", "").strip()
    if val:
        return Path(val)
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_appdata) / "trade"
    return Path.home() / ".trade"


def _get_package_skills_dir() -> Path | None:
    """Find the installed package's skills directory.

    When installed via `pip install -e .` or `pip install .` from the repo,
    the package root is discoverable via __main__ or the trade package __file__.
    Falls back to searching sys.path.
    """
    # Try to find trade package __file__ (e.g. .../site-packages/trade/__init__.py)
    for prefix in list(sys.path):
        p = Path(prefix)
        if not p.is_dir():
            continue
        candidate = p / "trade" / "__init__.py"
        if candidate.exists():
            skills_dir = candidate.parent.parent / "skills"
            if skills_dir.is_dir():
                return skills_dir

    # Fallback: look for skills next to this script (development install)
    self_dir = Path(__file__).parent.parent  # project root
    dev_skills = self_dir / "skills"
    if dev_skills.is_dir():
        return dev_skills

    return None


def _copy_skills(src: Path, dst_base: Path) -> list[str]:
    """Copy b2b-* skill directories from src to dst_base.

    Creates dst_base/b2b-{skill-name}/SKILL.md for each skill found.
    Returns list of installed skill names.
    """
    installed = []
    for skill_dir in sorted(src.iterdir()):
        if not skill_dir.is_dir():
            continue
        if not skill_dir.name.startswith("b2b-"):
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue

        dest = dst_base / skill_dir.name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_file, dest)
        installed.append(skill_dir.name)

    return installed


def _copy_trade_template(src: Path, dst: Path) -> None:
    """Copy .trade-template/ directory to Trade runtime directory.

    Copies only the skeleton (empty template files), not runtime data.
    Creates dst/.trade-template/ as the runtime copy.

    Also seeds the actual prompts directory so the user has editable files
    from day one (prompts/system.md).
    """
    if src.is_dir():
        dest = dst / ".trade-template"
        if not dest.exists():
            shutil.copytree(src, dest, dirs_exist_ok=False)
            for f in dest.rglob("*"):
                if f.is_file():
                    f.chmod(0o644)

    # Seed ~/.trade/prompts/system.md from template (only if not already present)
    prompts_src = src / "prompts" / "system.md"
    prompts_dir = dst / "prompts"
    prompts_dst = prompts_dir / "system.md"
    if prompts_src.is_file() and not prompts_dst.is_file():
        prompts_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prompts_src, prompts_dst)
        prompts_dst.chmod(0o644)


def install_skills() -> None:
    """Main entry point: install Trade skills into Hermes and set up Trade data dir."""
    hermes_home = _get_hermes_home()
    trade_home = _get_trade_home()

    hermes_skills_dir = hermes_home / "skills"

    # Find package skills
    package_skills = _get_package_skills_dir()
    if package_skills is None:
        print("[post_install] ERROR: Could not find skills directory.", file=sys.stderr)
        print("[post_install] Expected: <package-root>/skills/b2b-*/SKILL.md", file=sys.stderr)
        sys.exit(1)

    # 查找 .trade-template — 与 skills 同级的模板目录
    # 优先从 package_skills 的父目录查找（pip install . 场景）
    # 其次从本脚本所在目录查找（pip install -e . 开发模式）
    template_dir = package_skills.parent / ".trade-template"
    if not template_dir.is_dir():
        self_dir = Path(__file__).parent.parent  # project root (dev install fallback)
        template_dir = self_dir / ".trade-template"

    # Copy skills to Hermes
    print(f"[post_install] Hermes home:   {hermes_home}")
    print(f"[post_install] Package skills: {package_skills}")
    print(f"[post_install] Hermes skills: {hermes_skills_dir}")

    installed = _copy_skills(package_skills, hermes_skills_dir)

    if installed:
        print(f"[post_install] Installed {len(installed)} skills to Hermes:")
        for name in installed:
            print(f"  ✓ {name}")
    else:
        print("[post_install] WARNING: No b2b-* skills found to install.", file=sys.stderr)

    # Set up .trade-template in Trade runtime dir
    if template_dir.is_dir():
        print(f"[post_install] Trade home:    {trade_home}")
        trade_home.mkdir(parents=True, exist_ok=True)
        _copy_trade_template(template_dir, trade_home)
        print(f"[post_install] Trade data template installed to: {trade_home}/.trade-template")

    print("[post_install] Done.")


def update_skills() -> None:
    """从 GitHub 拉取最新 B2B skill 定义并更新到本地 Hermes 目录。

    和 install_skills 的区别：
      - install_skills: 从本地 pip 安装包中复制 skills（安装时用）
      - update_skills:  从 GitHub main 分支下载最新 SKILL.md（更新时用）

    用法：trade-skills-update（或 python -m trade.post_install update）
    """
    import hashlib
    import urllib.request

    hermes_home = _get_hermes_home()
    hermes_skills_dir = hermes_home / "skills"

    # 本地包中的 skills 目录（用于列出需要更新哪些 skill）
    package_skills = _get_package_skills_dir()
    if package_skills is None:
        print("[update_skills] ERROR: Cannot find local skills directory.", file=sys.stderr)
        sys.exit(1)

    # GitHub raw URL 前缀
    RAW_BASE = "https://raw.githubusercontent.com/chefroger/foreign-trade-assistant/main/skills"

    updated = 0
    skipped = 0
    failed = 0

    for skill_dir in sorted(package_skills.iterdir()):
        if not skill_dir.is_dir() or not skill_dir.name.startswith("b2b-"):
            continue

        skill_name = skill_dir.name
        raw_url = f"{RAW_BASE}/{skill_name}/SKILL.md"
        dest_dir = hermes_skills_dir / skill_name
        dest_file = dest_dir / "SKILL.md"

        try:
            # 下载 GitHub 上的最新 SKILL.md
            req = urllib.request.Request(
                raw_url,
                headers={"User-Agent": "Trade-Skills-Updater/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                remote_content = resp.read().decode("utf-8")

            # 比较 hash，相同则跳过
            remote_hash = hashlib.sha256(remote_content.encode()).hexdigest()
            if dest_file.is_file():
                local_hash = hashlib.sha256(dest_file.read_bytes()).hexdigest()
                if local_hash == remote_hash:
                    print(f"  ✓ {skill_name} (already up-to-date)")
                    skipped += 1
                    continue

            # 写入新内容
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(remote_content, encoding="utf-8")
            print(f"  ↻ {skill_name} (updated)")
            updated += 1

        except urllib.error.HTTPError as e:
            print(f"  ✗ {skill_name} (HTTP {e.code}: {raw_url})", file=sys.stderr)
            failed += 1
        except Exception as e:
            print(f"  ✗ {skill_name} (error: {e})", file=sys.stderr)
            failed += 1

    print(f"\n[update_skills] Done. {updated} updated, {skipped} skipped, {failed} failed.")
    if updated > 0:
        print("Hermes will pick up the updated skills on the next request.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trade Skills Manager")
    parser.add_argument("action", nargs="?", default="install",
                        choices=["install", "update"],
                        help="install: copy from local package (default), update: fetch from GitHub")
    args = parser.parse_args()
    if args.action == "update":
        update_skills()
    else:
        install_skills()
