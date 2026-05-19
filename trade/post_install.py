"""
post_install: 将 Trade B2B skills 安装到 Hermes skills 目录。

调用方式：
  - `pip install -e .` 或 `pip install .`（setuptools 安装后自动执行）
  - 手动执行：`install-trade-skills`（声明为项目 console script）

本模块在包导入图之外运行——只使用标准库，
避免包与 hermes-agent 之间的版本/导入冲突。

它从以下位置复制 skills：
  {package_location}/skills/b2b-*/
  → ~/.hermes/skills/b2b-*/

Hermes 从 ~/.hermes/skills/ 发现 skills（通过 get_all_skills_dirs()）。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _get_hermes_home() -> Path:
    """镜像 hermes_constants.get_hermes_home()，无导入依赖。"""
    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        # 如果设置了 HERMES_HOME 环境变量，优先使用
        return Path(val)
    return Path.home() / ".hermes"


def _get_trade_home() -> Path:
    """返回用户 Trade 数据目录（与 database.py / company.py / prompts.py 统一）。

    Priority: TRADE_HOME env var → platform default.
    macOS/Linux: ~/.trade/, Windows: %LOCALAPPDATA%\trade\
    """
    val = os.environ.get("TRADE_HOME", "").strip()
    if val:
        # 如果设置了 TRADE_HOME 环境变量，优先使用
        return Path(val)
    if os.name == "nt":
        # Windows 系统下使用 %LOCALAPPDATA%\trade\
        local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(local_appdata) / "trade"
    # macOS/Linux 默认路径
    return Path.home() / ".trade"


def _get_package_skills_dir() -> Path | None:
    """查找已安装包的 skills 目录。

    通过 `pip install -e .` 或 `pip install .` 从仓库安装时，
    包根目录可以通过 __main__ 或 trade 包的 __file__ 发现。
    如果找不到则回退到搜索 sys.path。
    """
    # 尝试通过 trade 包的 __file__ 定位（例如 .../site-packages/trade/__init__.py）
    for prefix in list(sys.path):
        p = Path(prefix)
        if not p.is_dir():
            # 跳过非目录路径
            continue
        candidate = p / "trade" / "__init__.py"
        if candidate.exists():
            skills_dir = candidate.parent.parent / "skills"
            if skills_dir.is_dir():
                return skills_dir

    # 回退：在本脚本所在目录的父级查找 skills 目录（开发模式安装）
    self_dir = Path(__file__).parent.parent  # 项目根目录
    dev_skills = self_dir / "skills"
    if dev_skills.is_dir():
        return dev_skills

    return None


def _copy_skills(src: Path, dst_base: Path) -> list[str]:
    """将 b2b-* skill 目录从 src 复制到 dst_base。

    为每个找到的 skill 创建 dst_base/b2b-{skill-name}/SKILL.md。
    返回已安装的 skill 名称列表。
    """
    installed = []
    for skill_dir in sorted(src.iterdir()):
        if not skill_dir.is_dir():
            # 跳过非目录条目
            continue
        if not skill_dir.name.startswith("b2b-"):
            # 只处理 b2b 前缀的 skill 目录
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            # 跳过没有 SKILL.md 的目录
            continue

        dest = dst_base / skill_dir.name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_file, dest)
        installed.append(skill_dir.name)

    return installed


def _copy_trade_template(src: Path, dst: Path) -> None:
    """将 .trade-template/ 目录复制到 Trade 运行时目录。

    只复制骨架（空模板文件），不复制运行时数据。
    创建 dst/.trade-template/ 作为运行时副本。

    同时植入 prompts 目录，让用户从第一天起就有可编辑的文件（prompts/system.md）。
    """
    if src.is_dir():
        dest = dst / ".trade-template"
        if not dest.exists():
            # 只在目标不存在时才复制，避免覆盖用户数据
            shutil.copytree(src, dest, dirs_exist_ok=False)
            for f in dest.rglob("*"):
                if f.is_file():
                    f.chmod(0o644)

    # 从模板植入 ~/.trade/prompts/system.md（仅当尚未存在时）
    prompts_src = src / "prompts" / "system.md"
    prompts_dir = dst / "prompts"
    prompts_dst = prompts_dir / "system.md"
    if prompts_src.is_file() and not prompts_dst.is_file():
        # 如果用户已有 prompts 文件则跳过，避免覆盖用户自定义内容
        prompts_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prompts_src, prompts_dst)
        prompts_dst.chmod(0o644)


def install_skills() -> None:
    """主入口：将 Trade skills 安装到 Hermes 并设置 Trade 数据目录。"""
    hermes_home = _get_hermes_home()
    trade_home = _get_trade_home()

    hermes_skills_dir = hermes_home / "skills"

    # 查找包中的 skills 目录
    package_skills = _get_package_skills_dir()
    if package_skills is None:
        # 找不到 skills 目录时报告错误并退出
        print("[post_install] ERROR: Could not find skills directory.", file=sys.stderr)
        print("[post_install] Expected: <package-root>/skills/b2b-*/SKILL.md", file=sys.stderr)
        sys.exit(1)

    # 查找 .trade-template — 与 skills 同级的模板目录
    # 优先从 package_skills 的父目录查找（pip install . 场景）
    # 其次从本脚本所在目录查找（pip install -e . 开发模式）
    template_dir = package_skills.parent / ".trade-template"
    if not template_dir.is_dir():
        # 在 package_skills 旁边找不到，回退到项目根目录
        self_dir = Path(__file__).parent.parent  # 项目根目录（开发模式回退）
        template_dir = self_dir / ".trade-template"

    # 将 skills 复制到 Hermes 目录
    print(f"[post_install] Hermes home:   {hermes_home}")
    print(f"[post_install] Package skills: {package_skills}")
    print(f"[post_install] Hermes skills: {hermes_skills_dir}")

    installed = _copy_skills(package_skills, hermes_skills_dir)

    if installed:
        # 打印成功安装的 skill 列表
        print(f"[post_install] Installed {len(installed)} skills to Hermes:")
        for name in installed:
            print(f"  ✓ {name}")
    else:
        # 没有找到任何 b2b-* skill 时发出警告
        print("[post_install] WARNING: No b2b-* skills found to install.", file=sys.stderr)

    # 在 Trade 运行时目录中设置 .trade-template
    if template_dir.is_dir():
        # 只有模板目录存在时才执行复制
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
    import urllib.error
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
            # 只处理 b2b 前缀的目录，跳过非 skill 条目
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
                # 如果本地文件存在，比较 hash 判断是否有更新
                local_hash = hashlib.sha256(dest_file.read_bytes()).hexdigest()
                if local_hash == remote_hash:
                    # hash 相同，无需更新
                    print(f"  ✓ {skill_name} (already up-to-date)")
                    skipped += 1
                    continue

            # hash 不同或本地文件不存在，写入新内容
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(remote_content, encoding="utf-8")
            print(f"  ↻ {skill_name} (updated)")
            updated += 1

        except urllib.error.HTTPError as e:
            # HTTP 错误（如 404 表示 GitHub 上不存在该 skill）
            print(f"  ✗ {skill_name} (HTTP {e.code}: {raw_url})", file=sys.stderr)
            failed += 1
        except Exception as e:
            # 其他网络或 IO 错误
            print(f"  ✗ {skill_name} (error: {e})", file=sys.stderr)
            failed += 1

    print(f"\n[update_skills] Done. {updated} updated, {skipped} skipped, {failed} failed.")
    if updated > 0:
        # 有更新时提示需要重启
        print("Hermes will pick up the updated skills on the next request.")


def update_trade() -> None:
    """一键更新 Foreign Trade Assistant 系统。

    执行步骤：
      1. git pull（拉取最新代码）
      2. pip install -e . --no-deps（更新包注册）
      3. update_skills()（同步最新 B2B skills）
      4. 数据库迁移检查

    用法：trade-update（或 trade update）
    """
    import subprocess

    trade_dir = _get_trade_home() / "foreign-trade-assistant"
    if not trade_dir.is_dir():
        # 找不到 Trade 安装目录时报告错误并退出
        print("[update_trade] ERROR: Trade install directory not found.", file=sys.stderr)
        print(f"  Expected: {trade_dir}", file=sys.stderr)
        sys.exit(1)

    ok = True

    # 1. git pull — 拉取最新代码
    print("→ Step 1/4: git pull ...")
    result = subprocess.run(
        ["git", "pull", "--ff-only", "origin", "main"],
        cwd=str(trade_dir), capture_output=True, text=True,
    )
    if result.returncode != 0:
        # git pull 失败（如网络问题或冲突），继续后续步骤
        print(f"  ⚠ git pull failed: {result.stderr.strip()}")
        print("  (继续后续步骤...)")
        ok = False
    else:
        print(f"  ✓ {result.stdout.strip().split(chr(10))[-1] if result.stdout.strip() else 'Already up-to-date.'}")

    # 2. pip install — 更新包注册
    print("→ Step 2/4: pip install ...")
    pip_args = [sys.executable, "-m", "pip", "install", "-e", str(trade_dir), "--no-deps", "--quiet"]
    result = subprocess.run(pip_args, capture_output=True, text=True)
    if result.returncode != 0:
        # pip 安装失败时标记错误但不退出
        print(f"  ⚠ pip install failed: {result.stderr.strip()}")
        ok = False
    else:
        print("  ✓ Package updated")

    # 3. skills — 同步最新 B2B skills
    print("→ Step 3/4: skills update ...")
    try:
        update_skills()
    except SystemExit:
        # update_skills 内部可能调用 sys.exit(1)，捕获以继续执行
        ok = False

    # 4. db migration (幂等操作)
    print("→ Step 4/4: database check ...")
    try:
        from trade.database import init_db
        db_path = init_db()
        print(f"  ✓ Database OK ({db_path})")
    except Exception as e:
        # 数据库检查失败不影响后续步骤
        print(f"  ⚠ Database check failed: {e}")
        ok = False

    if ok:
        # 所有步骤成功完成
        print("\n✅ Trade update complete. Restart the server to apply changes.")
    else:
        # 部分步骤失败，提示用户检查输出
        print("\n⚠️  Trade update completed with warnings. Check the output above.")


def backup_trade(output_dir: str | None = None) -> str:
    """备份 Trade 系统数据为 tar.gz 压缩包。

    包含：
      - ~/.trade/data/trade.db（SQLite 数据库）
      - ~/.trade/companies/{slug}/（公司数据）
      - ~/.trade/prompts/（系统 prompts）
      - ~/.hermes/memories/（Hermes 记忆）
      - ~/.hermes/skills/b2b-*/（B2B skills）

    Args:
        output_dir: 输出目录（默认桌面）

    Returns:
        生成的 tar.gz 文件路径

    用法：trade-backup [output_dir]（或 trade backup）
    """
    import datetime
    import tarfile

    if output_dir is None:
        # 未指定输出目录时默认使用桌面
        desktop = Path.home() / "Desktop"
        if not desktop.is_dir():
            # 英文桌面路径不存在时尝试中文桌面路径
            desktop = Path.home() / "桌面"
        if not desktop.is_dir():
            # 两个桌面路径都不存在时回退到家目录
            desktop = Path.home()
        output_dir = str(desktop)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = f"trade-backup-{timestamp}.tar.gz"
    out_path = Path(output_dir) / filename

    trade_home = _get_trade_home()
    hermes_home = _get_hermes_home()

    # 需要打包的路径列表
    sources: list[tuple[Path, str]] = []  # (absolute_path, arcname_in_tar)

    # SQLite 数据库文件
    db_path = trade_home / "data" / "trade.db"
    if db_path.is_file():
        sources.append((db_path, ".trade/data/trade.db"))

    # 公司数据目录（每个公司一个子目录）
    companies_dir = trade_home / "companies"
    if companies_dir.is_dir():
        # 遍历所有公司目录，递归添加所有文件
        for company_dir in companies_dir.iterdir():
            if company_dir.is_dir():
                for f in company_dir.rglob("*"):
                    if f.is_file():
                        rel = str(f.relative_to(trade_home))
                        sources.append((f, f".trade/{rel}"))

    # prompts 目录（系统提示词文件）
    prompts_dir = trade_home / "prompts"
    if prompts_dir.is_dir():
        for f in prompts_dir.rglob("*"):
            if f.is_file():
                sources.append((f, f".trade/{f.relative_to(trade_home)}"))

    # Hermes 记忆文件
    memories_dir = hermes_home / "memories"
    if memories_dir.is_dir():
        for f in memories_dir.rglob("*"):
            # 只备份 markdown、json、txt 格式的记忆文件
            if f.is_file() and f.suffix in (".md", ".json", ".txt"):
                sources.append((f, f".hermes/memories/{f.relative_to(memories_dir)}"))

    # B2B skills 定义
    skills_dir = hermes_home / "skills"
    if skills_dir.is_dir():
        for skill_dir in skills_dir.iterdir():
            # 只备份 b2b 前缀的 skill 的 SKILL.md 文件
            if skill_dir.is_dir() and skill_dir.name.startswith("b2b-"):
                skill_md = skill_dir / "SKILL.md"
                if skill_md.is_file():
                    sources.append((skill_md, f".hermes/skills/{skill_dir.name}/SKILL.md"))

    if not sources:
        # 没有找到任何可备份的数据
        print("[backup] WARNING: No data found to backup.")
        return ""

    print(f"[backup] Packaging {len(sources)} files ...")
    with tarfile.open(out_path, "w:gz") as tar:
        for abs_path, arcname in sources:
            tar.add(str(abs_path), arcname=arcname)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"[backup] Done: {out_path} ({size_mb:.1f} MB)")
    return str(out_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trade Skills Manager")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("install", help="Install skills from local package")
    sub.add_parser("update", help="Update skills from GitHub")
    p_up = sub.add_parser("update-trade", help="Update entire Trade system")
    p_backup = sub.add_parser("backup", help="Backup Trade data")
    p_backup.add_argument("--output", "-o", default=None, help="Output directory (default: Desktop)")

    args = parser.parse_args()
    if args.command == "update":
        # 从 GitHub 更新 skills
        update_skills()
    elif args.command == "update-trade":
        # 一键更新整个 Trade 系统
        update_trade()
    elif args.command == "backup":
        # 备份 Trade 数据到 tar.gz
        backup_trade(args.output)
    else:
        # 默认：从本地包安装 skills
        install_skills()
