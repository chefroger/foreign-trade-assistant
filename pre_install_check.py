"""
pre_install_check: Verify hermes-agent is installed and compatible before trade install.

This module runs BEFORE pip install of the trade package.
It checks:
  1. Is hermes-agent installed at all?
  2. Is the installed version compatible with trade's requirements?
  3. If not compatible → print instructions to install from chefroger fork first.

Exit codes:
  0  = compatible, proceed with trade install
  1  = hermes-agent not found, must install first
  2  = hermes-agent version incompatible, must upgrade/downgrade

Usage (run BEFORE pip install trade):
  python pre_install_check.py
"""

from __future__ import annotations

import sys
import urllib.request
import json as _json


# ─────────────────────────────────────────────────────────────────────────────
# Version compatibility matrix
# ─────────────────────────────────────────────────────────────────────────────

# trade requires hermes-agent from chefroger fork at or above this version.
# The chefroger fork diverged from NousResearch at v0.12.0.
MIN_COMPATIBLE_VERSION = "0.12.0"

# If hermes-agent is installed from a different source (e.g. NousResearch direct),
# it may be incompatible even if version number looks OK.
# List of known-incompatible package names (PyPI releases from other sources).
INCOMPATIBLE_SOURCES: list[str] = [
    # No PyPI release for hermes-agent exists (it's git-only), so we check
    # the installed package's install location as a proxy for source.
]


# ─────────────────────────────────────────────────────────────────────────────
# Version parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse 'X.Y.Z' into (major, minor, patch) integers.

    Falls back to (0,0,0) for unparseable strings.
    Strips 'v' prefix (e.g. 'v0.12.0' → 0.12.0).
    """
    clean = version_str.lstrip("v").strip()
    try:
        parts = clean.split(".")
        return (int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    except (ValueError, IndexError):
        return (0, 0, 0)


def _compare_versions(installed: str, required: str) -> int:
    """Compare two version strings.

    Returns:  -1 if installed < required
               0 if installed == required
              +1 if installed > required
    """
    inst = _parse_version(installed)
    req = _parse_version(required)
    if inst < req:
        return -1
    elif inst > req:
        return +1
    else:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# hermes-agent version detection
# ─────────────────────────────────────────────────────────────────────────────

def get_installed_hermes_version() -> str | None:
    """Attempt to detect the installed hermes-agent version string.

    Tries in order:
      1. `hermes --version` CLI (fast, works if CLI is on PATH)
      2. Import hermes_agent package and read __version__
      3. Search site-packages for hermes-agent's version file

    Returns None if hermes-agent is not installed at all.
    """
    import subprocess, shutil

    # Try CLI first
    hermes_bin = shutil.which("hermes")
    if hermes_bin:
        try:
            result = subprocess.run(
                [hermes_bin, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            # Output format: 'hermes X.Y.Z' or just 'X.Y.Z'
            raw = result.stdout.strip() or result.stderr.strip()
            # Extract version number
            for word in raw.split():
                if word[0].isdigit() or word.startswith("v"):
                    return word.lstrip("v")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # Try importing the package
    try:
        import hermes_agent
        return getattr(hermes_agent, "__version__", None) or _find_version_in_path()
    except ImportError:
        pass

    # Last resort: scan site-packages
    return _find_version_in_path()


def _find_version_in_path() -> str | None:
    """Scan sys.path for hermes-agent package and read its version file."""
    import os, pathlib

    for prefix in sys.path:
        p = pathlib.Path(prefix)
        if not p.is_dir():
            continue
        # Try hermes_agent package directory
        pkg = p / "hermes_agent"
        if pkg.is_dir():
            # Check for __version__ in __init__.py
            init_file = pkg / "__init__.py"
            if init_file.is_file():
                content = init_file.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("__version__"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            return parts[1].strip().strip("'\"").strip("v")
            # Check for PKG-INFO or METADATA
            for fname in ("PKG-INFO", "METADATA", "version"):
                vfile = pkg.parent / fname
                if vfile.is_file():
                    content = vfile.read_text(encoding="utf-8", errors="ignore")[:500]
                    for cline in content.splitlines():
                        cline = cline.strip()
                        if cline.startswith("Version:"):
                            return cline.split(":", 1)[1].strip().lstrip("v")
    return None


def is_hermes_from_chefroger() -> bool:
    """Check if installed hermes-agent came from chefroger/hermes-agent fork.

    Since hermes-agent has no PyPI release, we check the install location:
    - Path contains 'chefroger' → fork ✓
    - Path contains 'NousResearch' → upstream ✗
    - Anything else (homebrew, apt, etc.) → unknown, assume OK

    Returns True if confirmed from fork or if not installed at all (no fork needed).
    """
    import os, pathlib

    for prefix in sys.path:
        p = pathlib.Path(prefix)
        if not p.is_dir():
            continue
        pkg = p / "hermes_agent"
        if pkg.is_dir():
            path_str = str(pkg.resolve())
            if "chefroger" in path_str:
                return True
            if "NousResearch" in path_str:
                return False
    # Not found in site-packages → treat as not installed (caller decides)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# GitHub API — check latest chefroger release / commit
# ─────────────────────────────────────────────────────────────────────────────

def get_latest_chefroger_version() -> str | None:
    """Query GitHub API for the latest release tag on chefroger/hermes-agent."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/chefroger/hermes-agent/releases/latest",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "trade-pre-install-check/1.0"},
            timeout=10,
        )
        with urllib.request.urlopen(req) as resp:
            data = _json.loads(resp.read())
            tag = data.get("tag_name", "")
            return tag.lstrip("v") or None
    except Exception:
        return None


def get_latest_chefroger_commit() -> str | None:
    """Get the latest commit SHA on main branch of chefroger/hermes-agent."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/chefroger/hermes-agent/commits/main",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "trade-pre-install-check/1.0"},
            timeout=10,
        )
        with urllib.request.urlopen(req) as resp:
            data = _json.loads(resp.read())
            return data.get("sha", "")[:7] or None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_header():
    print("=" * 60)
    print("  Trade Pre-Install Check — Hermes Agent Compatibility")
    print("=" * 60)


def print_ok(msg: str):
    print(f"\u2705 {msg}")


def print_fail(msg: str):
    print(f"\u274c {msg}")


def print_warn(msg: str):
    print(f"\u26a0\ufe0f {msg}")


def print_info(msg: str):
    print(f"   {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Main check logic
# ─────────────────────────────────────────────────────────────────────────────

def run_check() -> int:
    """Run all checks. Returns exit code (0=ok, 1=not installed, 2=incompatible)."""
    print_header()

    installed_version = get_installed_hermes_version()

    # Case 1: not installed at all
    if installed_version is None:
        print_fail("hermes-agent is NOT installed.")
        print()
        print_warn("Hermes Agent must be installed BEFORE trade.")
        print()
        _print_install_instructions()
        return 1

    print_info(f"Installed hermes-agent version: {installed_version}")
    from_fork = is_hermes_from_chefroger()
    print_info(f"Installed from chefroger fork: {'yes' if from_fork else 'NO (NousResearch upstream)'}")

    # Case 2: installed but wrong source
    if not from_fork:
        print_fail("hermes-agent is installed from NousResearch (wrong source).")
        print_warn("Trade requires hermes-agent from: https://github.com/chefroger/hermes-agent")
        print()
        print_info("Please uninstall the current version first:")
        print_info("  pip uninstall hermes-agent")
        print_info("  # or: uv pip uninstall hermes-agent")
        print()
        _print_install_instructions()
        return 2

    # Case 3: installed from fork, check version compatibility
    cmp = _compare_versions(installed_version, MIN_COMPATIBLE_VERSION)
    if cmp < 0:
        print_fail(f"hermes-agent version {installed_version} is too old.")
        print_warn(f"Trade requires version >= {MIN_COMPATIBLE_VERSION} from chefroger fork.")
        print()
        print_info("Please upgrade:")
        print_info(f"  pip install --upgrade hermes-agent")
        print_info("  # or: cd ~/.hermes/hermes-agent && uv pip install -e . --upgrade")
        print()
        _print_install_instructions_compat()
        return 2

    print_ok(f"hermes-agent {installed_version} from chefroger fork — compatible.")
    print()
    return 0


def _print_install_instructions():
    """Print installation instructions for chefroger/hermes-agent."""
    print("=" * 60)
    print("  Install Hermes Agent (chefroger fork)")
    print("=" * 60)
    print()
    print("  Option A — One-liner (recommended):")
    print("    curl -fsSL \\")
    print("      https://raw.githubusercontent.com/chefroger/hermes-agent/main/scripts/install.sh \\")
    print("      | bash")
    print()
    print("  Option B — Manual install:")
    print("    git clone --branch main \\")
    print("      https://github.com/chefroger/hermes-agent.git \\")
    print("      ~/.hermes/hermes-agent")
    print("    cd ~/.hermes/hermes-agent")
    print("    uv pip install -e .   # or: pip install -e .")
    print()
    print("  After installation, re-run this check:")
    print("    python pre_install_check.py")
    print()


def _print_install_instructions_compat():
    """Print upgrade instructions for incompatible version."""
    print("=" * 60)
    print("  Upgrade Hermes Agent")
    print("=" * 60)
    print()
    print("  cd ~/.hermes/hermes-agent")
    print("  git pull origin main")
    print("  uv pip install -e . --upgrade")
    print()
    print("  Or re-run the official installer:")
    print("    curl -fsSL \\")
    print("      https://raw.githubusercontent.com/chefroger/hermes-agent/main/scripts/install.sh \\")
    print("      | bash")
    print()
    print("  Then verify:")
    print("    python pre_install_check.py")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    exit_code = run_check()
    sys.exit(exit_code)
