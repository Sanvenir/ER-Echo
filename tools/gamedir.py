#!/usr/bin/env python3
"""ELDEN RING 游戏目录定位（Python 侧共用）。

源码搬出游戏目录后，工具不能再靠 `er-echo` 的父目录猜游戏路径。
查找顺序与 tools/gamedir.ps1 一致：

  1. 参数 / 环境变量 ER_ECHO_GAME_DIR
  2. 老布局：<Game>\\er-echo\\ 里
  3. 当前工作目录
  4. Steam 注册表 + libraryfolders.vdf
"""

from __future__ import annotations

import os
import pathlib
import re

_CACHE: dict[str, pathlib.Path | None] = {}


def _registry_steam_roots() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    try:
        import winreg
    except ImportError:
        return out
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    for hive, sub, name in keys:
        try:
            with winreg.OpenKey(hive, sub) as k:
                v = str(winreg.QueryValueEx(k, name)[0])
        except OSError:
            continue
        p = pathlib.Path(v)
        if p.is_dir():
            out.append(p)
    return out


def candidates(repo: pathlib.Path | None = None) -> list[pathlib.Path]:
    """候选游戏目录（不保证存在 eldenring.exe）。"""
    out: list[pathlib.Path] = []
    env = os.environ.get("ER_ECHO_GAME_DIR")
    if env:
        out.append(pathlib.Path(env))
    if repo is not None:
        out.append(repo.parent)          # 老布局：<Game>\er-echo\
    out.append(pathlib.Path.cwd())
    for steam in _registry_steam_roots():
        out.append(steam / "steamapps" / "common" / "ELDEN RING" / "Game")
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if not vdf.is_file():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            out.append(pathlib.Path(m.group(1).replace("\\\\", "\\"))
                       / "steamapps" / "common" / "ELDEN RING" / "Game")
    return out


def game_dir(repo: pathlib.Path | None = None, strict: bool = False) -> pathlib.Path | None:
    """返回含 eldenring.exe 的目录；找不到返回 None（strict 时抛错）。"""
    key = str(repo) if repo else ""
    if key in _CACHE:
        found = _CACHE[key]
    else:
        found = None
        for c in candidates(repo):
            try:
                if (c / "eldenring.exe").is_file():
                    found = c.resolve()
                    break
            except OSError:
                continue
        _CACHE[key] = found
    if found is None and strict:
        raise SystemExit("找不到 ELDEN RING 游戏目录（含 eldenring.exe）；设 ER_ECHO_GAME_DIR 指定")
    return found
