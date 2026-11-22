#!/usr/bin/env python3
"""ER Echo 一键安装/配置核心（Me2 原版 · Me3 / Convergence）。

设计目标（2026-11-21 需求）：
  * 用户只输入一个「游戏路径」，剩下的全部自动完成：
      - 识别目标类型（Mod Engine 2 原版 / Mod Engine 3 的 Convergence）
      - 把 mod 文件装到正确位置（不再要求把 exe 放进 Game 目录）
      - 自动导出存档角色并写好 profiles=
      - 自动改好加载器配置（config_eldenring.toml / *.me3），全部带备份
  * 可卸载：恢复备份 + 删掉装进去的目录。

两类目标：

  1) me2 —— Steam 正版游戏目录（含 eldenring.exe）
       <Game>\\mods\\ER-Echo\\...             mod 本体 + ESD（赐福菜单必需）
       <Game>\\config-er-echo.toml            自带的 ME2 配置
       <Game>\\config_eldenring.toml          自动追加 external_dlls / mod_loader（备份）

  2) me3 —— Convergence 3.x 目录（含 me3\\Windows\\me3.exe、mod\\regulation.bin）
       <Conv>\\er-echo\\...                   mod 本体 + ini + profiles
       <Conv>\\me3\\convergence.me3           自动追加 [[natives]]（备份）
       （Convergence 的 talk ESD 会覆盖 m00_00_00_00，本工具默认**不动它**：
         运行时 EzState 注入只需要 ESD 被挂载，Convergence 自己就挂载了。）

命令行：
    er_echo_setup.py --detect  [PATH]          列出检测结果
    er_echo_setup.py --install PATH [--save S] [--force-kind me2|me3]
    er_echo_setup.py --uninstall PATH
    er_echo_setup.py --selftest OUT            检测 + 报告 payload 是否完整
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

KIND_ME2 = "me2"
KIND_ME3 = "me3"
KIND_UNKNOWN = "unknown"

KIND_LABEL = {
    KIND_ME2: "Mod Engine 2 (原版 / vanilla)",
    KIND_ME3: "Mod Engine 3 (Convergence 3.x)",
    KIND_UNKNOWN: "未识别",
}

ME2_PLUGIN_DIR = pathlib.Path("mods") / "ER-Echo"
ME3_PLUGIN_DIR = pathlib.Path("er-echo")

#: 会被写进配置、文件头部注释里出现的标记，用来判断「是否已经装过 / 改过」
MARKER = "er-echo"


# ---------------------------------------------------------------- payload

def payload_dir() -> pathlib.Path:
    """返回随 exe 一起发布的 payload 目录（不依赖游戏目录）。"""
    cands: list[pathlib.Path] = []
    mei = getattr(sys, "_MEIPASS", None)
    if mei:
        cands.append(pathlib.Path(mei) / "payload")
    if getattr(sys, "frozen", False):
        exe_dir = pathlib.Path(sys.executable).resolve().parent
        cands += [exe_dir / "payload", exe_dir / "_internal" / "payload"]
    # 源码树里跑：er-echo/build/payload（由 tools/package_payload.ps1 生成）
    cands.append(_HERE.parent / "build" / "payload")
    for c in cands:
        if c.is_dir():
            return c
    raise SystemExit(
        "找不到 payload 目录（安装包不完整）。找过：\n  "
        + "\n  ".join(str(c) for c in cands))


# ---------------------------------------------------------------- target

@dataclass
class Target:
    kind: str
    root: pathlib.Path                 # 游戏根目录（me2）或 Convergence 根目录（me3）
    game_dir: pathlib.Path | None = None
    me3: pathlib.Path | None = None
    profiles: list[pathlib.Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def plugin_dir(self) -> pathlib.Path:
        return self.root / (ME2_PLUGIN_DIR if self.kind == KIND_ME2 else ME3_PLUGIN_DIR)

    @property
    def ini_path(self) -> pathlib.Path:
        return self.plugin_dir / "er_echo.ini"

    def describe(self) -> str:
        if self.kind == KIND_ME2:
            s = f"Mod Engine 2 · 游戏目录 {self.root}"
        elif self.kind == KIND_ME3:
            s = f"Mod Engine 3 · Convergence {self.root}"
        else:
            return "未识别：这里既不是游戏目录，也不是 Convergence 目录"
        if self.notes:
            s += "\n  " + "\n  ".join(self.notes)
        return s


# ---------------------------------------------------------------- 检测

def _reg_paths() -> list[pathlib.Path]:
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
                v = winreg.QueryValueEx(k, name)[0]
            p = pathlib.Path(str(v))
            if p.is_dir():
                out.append(p)
        except OSError:
            continue
    return out


def steam_libraries() -> list[pathlib.Path]:
    """Steam 库根目录（含 steamapps 的目录）。"""
    libs: list[pathlib.Path] = []
    for steam in _reg_paths():
        libs.append(steam)
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if not vdf.is_file():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            p = pathlib.Path(m.group(1).replace("\\\\", "\\"))
            if p.is_dir():
                libs.append(p)
    seen: set[str] = set()
    uniq: list[pathlib.Path] = []
    for p in libs:
        k = str(p).lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    return uniq


def find_game_dirs() -> list[pathlib.Path]:
    """所有已安装的 ELDEN RING Game 目录。"""
    out: list[pathlib.Path] = []
    for lib in steam_libraries():
        g = lib / "steamapps" / "common" / "ELDEN RING" / "Game"
        if (g / "eldenring.exe").is_file():
            out.append(g)
    return out


def me3_exe(root: pathlib.Path) -> pathlib.Path | None:
    for cand in (root / "me3" / "Windows" / "me3.exe", root / "me3" / "me3.exe"):
        if cand.is_file():
            return cand
    return None


def _conv_root_of(p: pathlib.Path) -> pathlib.Path | None:
    """p 本身或其 1~2 层子目录是不是 Convergence 根目录。"""
    if me3_exe(p) and (p / "mod").is_dir():
        return p
    try:
        kids = list(p.iterdir())
    except OSError:
        return None
    for kid in kids:
        if kid.is_dir() and me3_exe(kid) and (kid / "mod").is_dir():
            return kid
        if kid.is_dir():
            for gk in kid.iterdir() if _safe_list(kid) else []:
                if gk.is_dir() and me3_exe(gk) and (gk / "mod").is_dir():
                    return gk
    return None


def _safe_list(p: pathlib.Path) -> bool:
    try:
        next(p.iterdir(), None)
        return True
    except OSError:
        return False


def find_convergence_dirs(extra_roots: list[pathlib.Path] | None = None) -> list[pathlib.Path]:
    """常见位置里找 Convergence 根目录（me3\\Windows\\me3.exe + mod\\）。"""
    roots: list[pathlib.Path] = list(extra_roots or [])
    # 已记录的安装（ini / 注册表样式的小文件）
    for lib in steam_libraries():
        roots.append(lib / "steamapps" / "common")
    for drive in ("D:", "E:", "F:", "C:"):
        for sub in ("Games", "Game", "Mods", "ELDEN RING"):
            p = pathlib.Path(drive + "\\" + sub)
            if p.is_dir():
                roots.append(p)
    out: list[pathlib.Path] = []
    seen: set[str] = set()
    for r in roots:
        if not r.is_dir():
            continue
        found = _conv_root_of(r)
        if found is not None:
            k = str(found).lower()
            if k not in seen:
                seen.add(k)
                out.append(found)
    return out


def me3_profiles(conv: pathlib.Path) -> list[pathlib.Path]:
    d = conv / "me3"
    if not d.is_dir():
        return []
    return sorted([p for p in d.glob("*.me3") if p.is_file()])


def probe(path: str | pathlib.Path) -> Target:
    """把一个用户输入的路径分类成 me2 / me3 目标。"""
    raw = pathlib.Path(str(path).strip().strip('"')).expanduser()
    notes: list[str] = []
    if not raw.exists():
        return Target(KIND_UNKNOWN, raw, notes=["路径不存在"])

    if (raw / "eldenring.exe").is_file():
        kind = KIND_ME2
        game = raw
        if not (raw / "modengine2_launcher.exe").is_file():
            notes.append("没找到 modengine2_launcher.exe：需要先装 Mod Engine 2")
        if (raw / "me3").is_dir():
            notes.append("这个目录里也有 me3\\，是不是想装到 Convergence？")
        return Target(kind, game, game_dir=game, notes=notes)

    conv = _conv_root_of(raw)
    if conv is not None:
        notes.append(f"me3: {me3_exe(conv)}")
        game = _steam_game_for(conv)
        if game is not None:
            notes.append(f"游戏本体: {game}")
        return Target(KIND_ME3, conv, game_dir=game, me3=me3_exe(conv), notes=notes)

    notes.append("看不到 eldenring.exe，也看不到 me3\\Windows\\me3.exe + mod\\")
    return Target(KIND_UNKNOWN, raw, notes=notes)


def _steam_game_for(conv: pathlib.Path) -> pathlib.Path | None:
    games = find_game_dirs()
    return games[0] if games else None


# ---------------------------------------------------------------- 存档

def find_saves() -> list[pathlib.Path]:
    """所有存档主文件，最近的在前。

    原版是 `ER0000.sl2`；Convergence 用 me3 的 `savefile = "ER0000.cnv"`，
    文件名没有 `.sl2` 后缀（内容还是同一个 SL2 格式），所以不能只找 `*.sl2`。
    """
    base = pathlib.Path(os.environ.get("APPDATA", str(pathlib.Path.home()))) / "EldenRing"
    out: list[pathlib.Path] = []
    if not base.is_dir():
        return out
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if not name.startswith("er0000"):
            continue
        if name.endswith((".bak", ".co2", ".tmp", ".vdf")) or ".bak" in name:
            continue
        out.append(p)
    out.sort(key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)
    return out


def pick_save(kind: str, override: str | None = None) -> tuple[pathlib.Path | None, str]:
    """按目标类型挑存档，返回 (路径, 说明)。

    Convergence 用 me3 的 `savefile = "ER0000.cnv"`，存档名多一段 `.cnv`，
    所以优先它；没有就退回最新的 ER0000*.sl2 并给出提醒。
    """
    if override:
        p = pathlib.Path(override)
        return (p if p.is_file() else None), ("指定存档" if p.is_file() else "指定存档不存在")
    saves = find_saves()
    if not saves:
        return None, "没有找到存档（%APPDATA%\\EldenRing）"
    if kind == KIND_ME3:
        cnv = [p for p in saves if ".cnv" in p.name.lower()]
        if cnv:
            return cnv[0], "Convergence 存档（*.cnv）"
        return saves[0], "没找到 *.cnv 存档，暂用最新的原版存档（装备 id 可能与 Convergence 不同）"
    plain = [p for p in saves if ".cnv" not in p.name.lower()]
    return (plain[0] if plain else saves[0]), "原版存档"


# ---------------------------------------------------------------- 文件操作

def _copy_tree(src: pathlib.Path, dst: pathlib.Path, log) -> list[str]:
    """递归复制；单个文件被占用（比如游戏正开着、DLL 被映射）只警告不中断。"""
    skipped: list[str] = []
    if not src.is_dir():
        return skipped
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item, target)
        except OSError as exc:
            skipped.append(str(target))
            log(f"[!] 跳过 {target.name}（{exc.__class__.__name__}: {exc}）——"
                f"游戏正在运行的话，退出后重跑一次安装即可")
    return skipped


def _write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\r\n")


def _backup(path: pathlib.Path, log) -> pathlib.Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(path.name + ".bak-er-echo-" + stamp)
    shutil.copy2(path, bak)
    log(f"[i] 备份 {path.name} -> {bak.name}")
    return bak


def _latest_backup(path: pathlib.Path) -> pathlib.Path | None:
    cands = sorted(path.parent.glob(path.name + ".bak-er-echo-*"))
    return cands[-1] if cands else None


def _rel(path: pathlib.Path, root: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


# ---------------------------------------------------------------- ini

INI_TEMPLATE = """; ============================================================
; ER Echo —— 由安装器自动生成的配置（DLL 会优先读自己同目录的这份）
; profiles 由安装器/导出工具写入；卸载 = 删掉本目录
; ============================================================

[ipc]
addr=127.0.0.1:7811
token=change-me

[clone]
; 逗号分隔的 profile 列表；相对路径以**游戏根目录**（进程 CWD）为基准，
; 安装器写的是绝对路径，放在哪个盘都能用。
profiles={{PROFILES}}
auto_apply=true
apply_stats=true
; 队友使用和玩家一致的伤害修正（摘掉灵体 296000/20297000 削弱）
player_damage=true
; 玩家升级时队友跟随升级，并写回 profile JSON
auto_level=true

[combat]
; 赐福菜单里也可以开关；这里只是第一次安装的默认值
friendly_fire=false
; 友伤倍率：0.2 = 只有 20% 伤害（菜单打开友伤后生效）
friendly_fire_rate=0.2

[summon]
buddy_rows=23200000,23200001,23200002
buddy_npc=100000010
buddy_think=100000010
buddy_init=26050
buddy_follow=0
buddy_copy_from=20700001
summon_anywhere=true
stone_range=9999
no_spirit_glow=true
glow_speffects=295000,295200,295190
multi_summon=true
summon_events=true

[tuning]
follow_distance=35.0
auto_recall=false
lost_resummon=true
lost_distance=150
lost_seconds=15

[ai]
infinite_fp=true
think_row=100000010
behavior_row=0
npc_row=0
; 「队友 AI」给 1/2/3 号位各借一行 NpcThinkParam（拟态泪滴家族；
; 运行时先从 think_row 整行复制，再只改该号位的 aggression/guard/target_switch）
teammate_think_rows=100000020,100000030,100000040

[debug]
safe_mode=false
auto_status=true

[ui]
nested_menu=true

[i18n]
; 默认英文；要跟随系统语言改成 auto（也支持 zh-CN / zh-TW / ja / 自定义）
language=en
"""


def write_ini(ini: pathlib.Path, profiles: list[pathlib.Path], log) -> None:
    value = ",".join(str(p.resolve()) for p in profiles) if profiles else ""
    if ini.is_file():
        text = ini.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?m)^\s*profiles\s*=", text):
            # 用 lambda 当替换：Windows 路径里的反斜杠不能被当成转义
            text = re.sub(r"(?m)^\s*profiles\s*=.*$", lambda _m: "profiles=" + value,
                          text, count=1)
        else:
            text = text.replace("[clone]\n", "[clone]\nprofiles=" + value + "\n", 1)
    else:
        text = INI_TEMPLATE.replace("{{PROFILES}}", value)
    _write_text(ini, text)
    log(f"[ok] 写入 {ini}：profiles={value or '(空)'}")


# ---------------------------------------------------------------- ME2

ME2_CONFIG = """# ============================================================
# ER Echo - 自带的 Mod Engine 2 配置（可插拔，不改 config_eldenring.toml 也能用）
# 用法：双击 mods\\ER-Echo\\launch-er-echo.bat
# 卸载：删掉 mods\\ER-Echo\\ 和本文件。
# ============================================================
[modengine]
debug = false
external_dlls = ["mods/ER-Echo/er_echo.dll"]

[extension.mod_loader]
enabled = true
loose_params = false
mods = [ { enabled = true, name = "er-echo", path = "mods/ER-Echo/mod" } ]
"""


def _patch_config_eldenring(text: str) -> tuple[str, list[str]]:
    """在 ME2 主配置里追加 er_echo.dll + mod_loader 条目。"""
    changes: list[str] = []
    if "er_echo.dll" not in text:
        m = re.search(r"(?ms)^\s*external_dlls\s*=\s*\[(.*?)\]", text)
        if m:
            body = m.group(1).strip()
            body = (body + ", " if body else "") + '"mods/ER-Echo/er_echo.dll"'
            text = text[:m.start()] + "external_dlls = [ " + body + " ]" + text[m.end():]
            changes.append("external_dlls += mods/ER-Echo/er_echo.dll")
        else:
            text = text.rstrip() + '\n\n[modengine]\nexternal_dlls = ["mods/ER-Echo/er_echo.dll"]\n'
            changes.append("新加 [modengine] external_dlls")

    if 'name = "er-echo"' not in text and "name='er-echo'" not in text:
        entry = '{ enabled = true, name = "er-echo", path = "mods/ER-Echo/mod" }'
        m = re.search(r"(?ms)^\s*mods\s*=\s*\[", text)
        if m:
            # 找到这个数组的收尾 ]（条目里只有 { }，不会有 ]）
            close = text.find("]", m.end())
            if close > 0:
                head = text[:close].rstrip()
                sep = ", " if head.rstrip().endswith("}") else ""
                text = head + sep + entry + " ]" + text[close + 1:]
                changes.append("mod_loader.mods += er-echo")
        else:
            if re.search(r"(?m)^\s*\[extension\.mod_loader\]\s*$", text):
                text = re.sub(r"(?m)^(\s*\[extension\.mod_loader\]\s*)$",
                              r"\1\n" + entry.replace('{ enabled = true, ', 'mods = [ { enabled = true, ') + " ]",
                              text, count=1)
                changes.append("mod_loader.mods = er-echo")
            else:
                text = text.rstrip() + (
                    "\n\n[extension.mod_loader]\nenabled = true\nloose_params = false\n"
                    "mods = [ " + entry + " ]\n")
                changes.append("新加 [extension.mod_loader] mods")
    return text, changes


def install_me2(t: Target, save: pathlib.Path | None, payload: pathlib.Path, log) -> dict:
    game = t.root
    plugin = game / ME2_PLUGIN_DIR
    result: dict = {"kind": KIND_ME2, "root": str(game), "plugin": str(plugin), "changes": []}

    log(f"[..] 安装到 {plugin}")
    _copy_tree(payload / "shared", plugin, log)
    _copy_tree(payload / "me2" / "plugin", plugin, log)
    result["changes"].append(f"拷贝 payload -> {plugin}")

    # 自带 ME2 配置（不动 config_eldenring.toml 也能启动）
    cfg = game / "config-er-echo.toml"
    src = payload / "me2" / "config-er-echo.toml"
    if not cfg.is_file():
        if src.is_file():
            shutil.copy2(src, cfg)
        else:
            _write_text(cfg, ME2_CONFIG)
        result["changes"].append("写出 config-er-echo.toml")

    main = game / "config_eldenring.toml"
    if main.is_file():
        text = main.read_text(encoding="utf-8", errors="replace")
        new, changes = _patch_config_eldenring(text)
        if changes:
            _backup(main, log)
            _write_text(main, new)
            result["changes"] += [f"config_eldenring.toml: {c}" for c in changes]
        else:
            log("[i] config_eldenring.toml 已经有 er-echo 条目，跳过")
    else:
        log("[!] 没找到 config_eldenring.toml（Mod Engine 2 没装？）")

    profiles = _install_profiles(plugin / "profiles", save, log, relative_to=game,
                                 table_dir=payload / "tables" / "vanilla")
    write_ini(game / ME2_PLUGIN_DIR / "er_echo.ini", profiles, log)
    result["profiles"] = [str(p) for p in profiles]
    result["launch"] = str(plugin / "launch-er-echo.bat")
    return result


# ---------------------------------------------------------------- ME3 / Convergence

def _me3_block(dll_rel: str) -> str:
    return "\n# --- ER Echo (added by installer) ---\n[[natives]]\npath = '" + dll_rel + "'\n"


def install_me3(t: Target, save: pathlib.Path | None, payload: pathlib.Path, log) -> dict:
    conv = t.root
    plugin = conv / ME3_PLUGIN_DIR
    result: dict = {"kind": KIND_ME3, "root": str(conv), "plugin": str(plugin), "changes": []}

    log(f"[..] 安装到 {plugin}")
    _copy_tree(payload / "shared", plugin, log)
    result["changes"].append(f"拷贝 payload -> {plugin}")

    # 赐福菜单：默认不覆盖 Convergence 的 talk ESD（它会覆盖 m00_00_00_00），
    # 只有 payload/me3/mod 存在时才挂载我们自己的包。
    esd_src = payload / "me3" / "mod"
    esd_pkg = None
    if esd_src.is_dir():
        _copy_tree(esd_src, plugin / "mod", log)
        esd_pkg = plugin / "mod"
        result["changes"].append("挂载自带 ESD 包")

    dll = plugin / "er_echo.dll"
    if not dll.is_file():
        raise SystemExit(f"payload 不完整：缺少 {dll}")

    dll_rel = "./../er-echo/er_echo.dll"
    for prof in me3_profiles(conv):
        text = prof.read_text(encoding="utf-8", errors="replace")
        if "er_echo.dll" in text:
            log(f"[i] {prof.name} 已经有 er_echo.dll，跳过")
            continue
        _backup(prof, log)
        block = _me3_block(dll_rel)
        if esd_pkg is not None:
            block = ("\n# --- ER Echo (added by installer) ---\n[[package]]\n"
                     "id = \"er-echo\"\npath = './../er-echo/mod'\n") + block
        prof.write_text(text.rstrip() + "\n" + block, encoding="utf-8", newline="\r\n")
        result["changes"].append(f"{prof.name}: + [[natives]] er_echo.dll")
        log(f"[ok] 已改 {prof}")

    if not me3_profiles(conv):
        log("[!] me3\\ 下没有 *.me3 配置，Convergence 装得不对？")

    profiles = _install_profiles(plugin / "profiles", save, log, relative_to=None,
                                 table_dir=payload / "tables" / "convergence",
                                 merge_existing=False)
    write_ini(plugin / "er_echo.ini", profiles, log)
    result["profiles"] = [str(p) for p in profiles]
    result["launch"] = str(conv / "Start_Convergence.bat")
    return result


# ---------------------------------------------------------------- 共用

def _install_profiles(dirpath: pathlib.Path, save: pathlib.Path | None, log,
                      relative_to: pathlib.Path | None,
                      table_dir: pathlib.Path | None = None,
                      merge_existing: bool = True) -> list[pathlib.Path]:
    """导出存档角色；失败就留着示例档案。"""
    dirpath.mkdir(parents=True, exist_ok=True)
    example = payload_dir() / "shared" / "profiles" / "profile.example.json"
    if example.is_file() and not (dirpath / example.name).is_file():
        shutil.copy2(example, dirpath / example.name)

    if save is None:
        log("[!] 没有存档，先用示例档案（进游戏后可在导出页换成本人角色）")
        return [dirpath / example.name] if (dirpath / example.name).is_file() else []

    log(f"[..] 解析存档 {save}")
    try:
        written = _export_via_core_import(save, dirpath, log, table_dir)
    except Exception as exc:  # noqa: BLE001 - 导出失败不该让安装失败
        log(f"[!] 导出失败：{exc}")
        written = []
    if not written:
        log("[!] 存档里没有可解析的完整角色，先用示例档案")
        written = [dirpath / example.name] if (dirpath / example.name).is_file() else []
    # 目录里已有的 slot*.json（以前导出的、含脸/装备的完整档案）一起留在名单里。
    # Convergence 例外：它的物品 id 和原版不同，旧档案（原版存档导出的）会穿错装备，
    # 所以 me3 目标只保留本次导出的。
    if not merge_existing:
        keep = {p for p in written}
        for stale in dirpath.glob("slot*.json"):
            if stale not in keep:
                stale.unlink(missing_ok=True)
                log(f"[i] 删除过时档案 {stale.name}（Convergence 的 id 和原版不同）")
        return list(written)
    existing = [p for p in sorted(dirpath.glob("slot*.json"))]
    merged: list[pathlib.Path] = []
    for p in existing + written:
        if p not in merged:
            merged.append(p)
    return merged


def _export_via_core_import(save: pathlib.Path, outdir: pathlib.Path, log,
                            table_dir: pathlib.Path | None = None) -> list[pathlib.Path]:
    import export_profile_from_save as core
    import profile_export_gui as gui

    # 装备/法术 id 表决定「完整」判定：优先用随包发布的对应版本（Convergence 的 id
    # 和原版不同，所以按目标分开），没有再退回自动查找 / 弱校验。
    loaded = False
    if table_dir is not None:
        eq = table_dir / "er_echo_equip.json"
        mg = table_dir / "er_echo_magic.json"
        if eq.is_file() and core.load_equip_tables(eq):
            loaded = True
            log(f"[i] 装备表：{eq.name}")
        if mg.is_file() and core.load_magic_table(mg):
            log(f"[i] 法术表：{mg.name}")
    if not loaded:
        tables = gui.lookup_tables()   # 退回到「游戏根目录 / tools 旁边」找
        log(f"[i] 装备表：{tables.get('equip') or '缺失（弱校验，部分角色会判不完整）'}")
        log(f"[i] 法术表：{tables.get('magic') or '缺失（区间校验）'}")

    rows = gui.scan_save(save, on_slot=lambda slot, ch: log(
        f"  slot {slot}: {ch.get('name')} lv{ch.get('level')}"
        + ("" if ch.get("complete") else "  (缺脸/装备)")))

    good = [r for r in rows if r["ch"].get("complete")]
    if good:
        return gui.export_profiles(save, good, outdir)

    # 一个都不「完整」时不要空手而归：全部导出，但在 ini 里能用就行
    if rows:
        log("[!] 没有通过完整性校验的角色，改为全部导出（外观可能不完整）")
        written: list[pathlib.Path] = []
        outdir.mkdir(parents=True, exist_ok=True)
        for r in rows:
            ch = r["ch"]
            prof = core.build_profile(r["slot"], ch, r["payload"], source=save.parent.name)
            out = outdir / f"slot{r['slot']}_{core.sanitize(ch['name'])}.json"
            out.write_text(json.dumps(prof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            written.append(out)
        return written
    return []


# ---------------------------------------------------------------- IPC（导出参数表）

IPC_HOST = "127.0.0.1"
IPC_PORT = 7811
IPC_TOKEN = "change-me"

#: 参数表 dump：命令 → 落盘文件名（DLL 写在它自己的 CWD，也就是游戏根目录）
DUMP_TABLES = (
    ("dump_equip", "er_echo_equip.json"),
    ("dump_magic", "er_echo_magic.json"),
)


def _ipc_line(obj: dict) -> bytes:
    obj = dict(obj)
    obj.setdefault("v", 1)
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return raw + b"\n"


def _ipc_read(conn, timeout: float) -> dict | None:
    conn.settimeout(timeout)
    buf = b""
    while b"\n" not in buf:
        chunk = conn.recv(65536)
        if not chunk:
            return None
        buf += chunk
        if len(buf) > 1 << 20:
            return None
    line = buf.split(b"\n", 1)[0]
    try:
        msg = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return msg if isinstance(msg, dict) else None


def ipc_command(cmd: str, args: dict | None = None, wait: float = 25.0,
                host: str = IPC_HOST, port: int = IPC_PORT,
                token: str = IPC_TOKEN, log=print) -> dict:
    """给游戏内 DLL 发一条命令，返回 DLL 的 ack。

    DLL 是 **client**（每 ~2 秒主动拨 127.0.0.1:7811），所以这里要先当 server
    等它上门，再发 hello→welcome 握手，然后发命令。—— 用 dump 前别让
    `bridge/director.py` 占着这个端口。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError as exc:
        raise SystemExit(f"端口 {port} 被占用（是不是 bridge/director.py 在跑？）：{exc}")
    sock.listen(1)
    sock.settimeout(wait)
    log(f"[..] 等游戏里的 DLL 连上来（{host}:{port}，最多 {wait:.0f} 秒）")
    try:
        conn, _ = sock.accept()
    except socket.timeout:
        sock.close()
        raise SystemExit("游戏没有连上来：确认游戏正在运行、且 er_echo.dll 已加载")
    finally:
        try:
            sock.close()
        except OSError:
            pass

    with conn:
        hello = _ipc_read(conn, 10.0) or {}
        if hello.get("type") != "hello":
            raise SystemExit(f"DLL 握手失败：{hello!r}")
        log(f"[ok] DLL 已连接：{hello.get('client')} v{hello.get('version')}")
        conn.sendall(_ipc_line({"type": "welcome", "token": token,
                                "pid": 0, "server": "er-echo-setup"}))
        conn.sendall(_ipc_line({"type": "command", "cmd": cmd,
                                "args": args or {}, "token": token}))
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                msg = _ipc_read(conn, 5.0)
            except (socket.timeout, OSError):
                continue
            if msg is None:
                break
            if msg.get("type") in ("ack", "error"):
                return msg
        raise SystemExit(f"{cmd} 没有回执（超时）")


def dump_tables(game_dir: pathlib.Path | None, log=print,
                cmds=DUMP_TABLES) -> dict:
    """进游戏后导出 `er_echo_equip.json` / `er_echo_magic.json` 到游戏根目录。

    这两个表是「装备 id 是否真实存在」的硬校验依据；没有表时导出器只能做弱校验，
    像混搭套装的角色会被误判成「缺装备」而跳过。表跟着当前 `regulation.bin` 走，
    所以 Convergence 存档要在 Convergence 里 dump。
    """
    result: dict = {"files": [], "errors": []}
    for cmd, name in cmds:
        target = (game_dir / name) if game_dir else None
        before = target.stat().st_mtime if target and target.is_file() else 0.0
        log(f"[..] {cmd}")
        ack = ipc_command(cmd, log=log)
        if ack.get("type") == "error" or ack.get("ok") is False:
            msg = str(ack.get("error") or ack.get("message") or ack)
            result["errors"].append(f"{cmd}: {msg}")
            log(f"[!] {cmd} 失败：{msg}")
            continue
        log(f"[ok] {cmd} -> {ack.get('result') or ack}")
        if target is None:
            continue
        for _ in range(20):                      # DLL 是异步写盘，等它落盘
            if target.is_file() and target.stat().st_mtime >= before:
                break
            time.sleep(0.25)
        if target.is_file():
            size = target.stat().st_size
            result["files"].append({"cmd": cmd, "path": str(target), "size": size})
            log(f"[ok] {target} ({size} 字节)")
        else:
            result["errors"].append(f"{cmd}: 没看到 {name} 落盘")
            log(f"[!] 没看到 {name} 落盘（DLL 的 CWD 可能不在游戏根目录）")
    return result


# ---------------------------------------------------------------- 入口

def install(path: str, save_override: str | None = None, log=print,
            force_kind: str | None = None) -> dict:
    payload = payload_dir()
    for need in ("shared/er_echo.dll", "me2/config-er-echo.toml"):
        if not (payload / need).is_file():
            raise SystemExit(f"payload 不完整，缺少 {payload / need}")
    t = probe(path)
    if force_kind:
        t.kind = force_kind
    if t.kind == KIND_UNKNOWN:
        raise SystemExit(f"无法识别目标：{path}\n{t.describe()}")

    save, why = pick_save(t.kind, save_override)
    log(f"[i] 存档：{save if save else '(无)'}  ({why})")

    if t.kind == KIND_ME2:
        if not (t.root / "eldenring.exe").is_file():
            raise SystemExit(f"不是游戏目录（没有 eldenring.exe）：{t.root}")
        res = install_me2(t, save, payload, log)
    else:
        res = install_me3(t, save, payload, log)

    res["kind_label"] = KIND_LABEL[t.kind]
    res["ini"] = str(t.ini_path)
    res["save"] = str(save) if save else None
    res["save_note"] = why
    log("[done] 安装完成")
    return res


def uninstall(path: str, log=print) -> dict:
    t = probe(path)
    if t.kind == KIND_UNKNOWN:
        raise SystemExit(f"无法识别目标：{path}")
    res: dict = {"kind": t.kind, "removed": [], "restored": []}

    if t.kind == KIND_ME2:
        main = t.root / "config_eldenring.toml"
        bak = _latest_backup(main)
        if bak is not None:
            shutil.copy2(bak, main)
            res["restored"].append(f"{main} <- {bak.name}")
        cfg = t.root / "config-er-echo.toml"
        if cfg.is_file():
            cfg.unlink()
            res["removed"].append(str(cfg))
    else:
        for prof in me3_profiles(t.root):
            bak = _latest_backup(prof)
            if bak is not None:
                shutil.copy2(bak, prof)
                res["restored"].append(f"{prof} <- {bak.name}")

    plugin = t.plugin_dir
    if plugin.is_dir() and plugin.parent in (t.root, t.root / "mods"):
        shutil.rmtree(plugin)
        res["removed"].append(str(plugin))
        log(f"[ok] 删除 {plugin}")
    for r in res["restored"]:
        log(f"[ok] 恢复 {r}")
    return res


def selftest(out_path: str) -> int:
    info: dict = {"payload": None, "targets": [], "saves": [], "errors": []}
    try:
        p = payload_dir()
        info["payload"] = str(p)
        files = sorted(str(x.relative_to(p)).replace("\\", "/") for x in p.rglob("*") if x.is_file())
        info["payload_files"] = files
        for need in ("shared/er_echo.dll", "shared/profiles/profile.example.json",
                     "me2/config-er-echo.toml", "me2/plugin/launch-er-echo.bat",
                     "me2/plugin/mod/script/talk/m00_00_00_00.talkesdbnd.dcx"):
            if need not in files:
                info["errors"].append(f"payload 缺少 {need}")
    except SystemExit as exc:
        info["errors"].append(str(exc))
    for g in find_game_dirs():
        info["targets"].append({"kind": KIND_ME2, "path": str(g)})
    for c in find_convergence_dirs():
        info["targets"].append({"kind": KIND_ME3, "path": str(c), "profiles": [p.name for p in me3_profiles(c)]})
    info["saves"] = [str(s) for s in find_saves()[:5]]
    pathlib.Path(out_path).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not info["errors"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ER Echo installer core")
    ap.add_argument("--detect", nargs="?", const="", metavar="PATH")
    ap.add_argument("--install", metavar="PATH")
    ap.add_argument("--uninstall", metavar="PATH")
    ap.add_argument("--dump-tables", nargs="?", const="", metavar="PATH",
                    help="给运行中的游戏发 dump_equip/dump_magic（PATH 可选，用来定位游戏根目录）")
    ap.add_argument("--save")
    ap.add_argument("--force-kind", choices=[KIND_ME2, KIND_ME3])
    ap.add_argument("--selftest", metavar="OUT")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(args.selftest)
    if args.detect is not None:
        if args.detect:
            t = probe(args.detect)
            print(t.describe())
            print(json.dumps({"kind": t.kind, "root": str(t.root)}, ensure_ascii=False))
        games = find_game_dirs()
        convs = find_convergence_dirs()
        print("Steam 游戏目录：")
        for g in games:
            print("  ", g)
        print("Convergence：")
        for c in convs:
            print("  ", c, [p.name for p in me3_profiles(c)])
        return 0
    if args.install:
        res = install(args.install, args.save, log=print, force_kind=args.force_kind)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.uninstall:
        res = uninstall(args.uninstall, log=print)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.dump_tables is not None:
        game = None
        if args.dump_tables:
            t = probe(args.dump_tables)
            game = t.game_dir or (t.root if t.kind == KIND_ME2 else None)
        if game is None:
            games = find_game_dirs()
            game = games[0] if games else None
        res = dump_tables(game, log=print)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if not res["errors"] else 1
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
