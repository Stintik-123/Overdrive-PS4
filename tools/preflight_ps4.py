# Copyright (C) 2026 half144 and PS5 React contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# Additional attribution term: see LICENSE-ATTRIBUTION.
"""Environment preflight for the PS4 port, to run on the PC before the first build.

Read-only: verifies the base tools, the Open Orbis toolchain and the ported libraries
that npm run build:ps4 needs, without compiling anything. What is missing is listed with
the exact step of docs/PS4.md it belongs to, so the environment can be completed before
the first (honest) compile attempt. Exits 1 on anything critical.
"""
import shutil
import subprocess
import sys
from pathlib import Path

TOOLCHAIN_ENV = "OO_PS4_TOOLCHAIN"

# (command, version flag, critical, docs step) — from docs/PS4.md, "Build environment",
# step 1: the base tools; ninja is only needed by the PS5 pipeline and the preview build.
BASE_TOOLS = [
    ("git", "--version", True, "1. Base tools"),
    ("cmake", "--version", True, "1. Base tools"),
    ("node", "--version", True, "1. Base tools"),
    ("npm", "--version", True, "1. Base tools"),
    ("python3", "--version", True, "1. Base tools"),
    ("clang++", "--version", True, "1. Base tools (npm run preview compiles with clang)"),
    ("ninja", "--version", False, "1. Base tools (cmake -G Ninja builds go faster with it)"),
]

# Ports the PS4 host links against (docs/PS4.md, step 3). cmake config file names for
# find_package under CMAKE_FIND_ROOT_PATH; found anywhere under the toolchain root.
PORTED_LIBS = {
    "SDL2": "SDL2Config.cmake",
    "libcurl": ("CURLConfig.cmake", "curl-config.cmake"),
    "libarchive": "LibArchiveConfig.cmake",
    "OpenSSL": "OpenSSLConfig.cmake",
    "zlib": ("ZLIBConfig.cmake", "zlib-config.cmake"),
}

# Tree facts a port newcomer must not discover the hard way; all checked against the docs.
REPO_FACTS = [
    ("ps5-react/native/ps4/host_platform.cpp", "the PS4 host"),
    ("ps5-react/native/ps4/CMakeLists.txt", "the PS4 CMake target"),
    ("ps5-react/native/ps4/toolchain-openorbis.cmake", "the Open Orbis toolchain file"),
    ("ps5-react/tools/build_ps4.py", "the PS4 build driver"),
    ("packaging/build-ps4.sh", "the npm run build:ps4 wrapper"),
    ("docs/PS4.md", "the plan and bring-up checklist"),
]


def check(name, ok, critical, detail=""):
    mark = "PASS" if ok else ("FAIL" if critical else "WARN")
    suffix = f" — {detail}" if detail else ""
    print(f"[{mark}] {name}{suffix}")
    return ok or not critical


def tool_version(command, flag):
    try:
        result = subprocess.run([command, flag], capture_output=True, text=True, timeout=20)
        line = (result.stdout or result.stderr).splitlines()
        return line[0].strip() if line else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def toolchain_root():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if root is None:
        from os import environ
        value = environ.get(TOOLCHAIN_ENV, "")
        root = Path(value) if value else None
    return root


def find_port(root, names):
    if root is None or not root.is_dir():
        return False
    for name in names if isinstance(names, tuple) else (names,):
        if any(root.rglob(name)):
            return True
    return False


def main():
    print(f"Overdrive PS4 preflight — environment checks only, nothing is compiled\n")
    failed = []

    def critical_check(name, ok, detail=""):
        if not check(name, ok, True, detail):
            failed.append(name)
        return ok

    for command, flag, critical, step in BASE_TOOLS:
        version = tool_version(command, flag)
        if critical:
            critical_check(f"{command}: {version or 'not found'}", bool(version),
                           f"docs/PS4.md build-environment step: {step}")
        else:
            check(f"{command}: {version or 'not found'}", bool(version), False,
                  f"docs/PS4.md build-environment step: {step}")

    root = toolchain_root()
    if not critical_check(f"{TOOLCHAIN_ENV}", root is not None and root.is_dir(),
                 f"export {TOOLCHAIN_ENV}=/path/to/OpenOrbis-PS4-Toolchain "
                 "(docs/PS4.md step 2)"):
        print("\nResult: environment incomplete — set the toolchain root first.")
        return 1

    check(f"toolchain bin/ directory", (root / "bin").is_dir(), True,
          "the Open Orbis compilers live in <toolchain>/bin")
    if not (root / "bin").is_dir():
        failed.append(f"{TOOLCHAIN_ENV}/bin")

    for lib, configs in PORTED_LIBS.items():
        check(f"port of {lib}", find_port(root, configs), False,
              "find_package needs its cmake config under the toolchain root "
              "(docs/PS4.md step 3; verify names against your toolchain release)")

    for relative, what in REPO_FACTS:
        path = Path(__file__).resolve().parent.parent / relative
        critical_check(f"{relative}", path.is_file(), f"needed for {what}")

    ps5 = Path(__file__).resolve().parent.parent / "ps5-react"
    if not check("ps5-react/node_modules", (ps5 / "node_modules").is_dir(), True,
                 "cd ps5-react && npm install"):
        failed.append("ps5-react/node_modules")
        return 1
    check("embedded-react checkout (.deps/embeddedReact)",
          (ps5 / ".deps/embeddedReact").is_dir(), False,
          "docs/PS4.md build-environment step 5 pulls it; npm run setup fetches it too")

    if failed:
        print(f"\nResult: environment incomplete — missing: {', '.join(failed)}")
        return 1
    print("\nResult: the toolchain-free part of the setup is given by the checks above;")
    print("npm run preview is the sanity gate before npm run build:ps4 (docs/PS4.md step 4).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
