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
    """Mirror Trade's get_trade_home(), no import dependency."""
    val = os.environ.get("TRADE_HOME", "").strip()
    if val:
        return Path(val)
    return _get_hermes_home().parent / ".trade"


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

    # Find .trade-template in package root
    self_dir = Path(__file__).parent.parent  # project root
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


if __name__ == "__main__":
    install_skills()
