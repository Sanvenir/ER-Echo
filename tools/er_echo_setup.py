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
    er_echo_setup.py --install PATH [--save S] [--force-kind me2|me3] [--loader auto|me2|me3] [--me3 PATH]
    er_echo_setup.py --uninstall PATH
    er_echo_setup.py --launch [PATH] [--launch-admin] [--dry-run] [--me3 PATH]
                                               一键启动（原版 ME2/me3、Convergence me3）
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
KIND_LABEL_EN = {
    KIND_ME2: "Mod Engine 2 (vanilla)",
    KIND_ME3: "me3 (Convergence 3.x)",
    KIND_UNKNOWN: "Unrecognised",
}

#: 安装器界面语言（`zh` / `en`）。GUI 启动和切换语言时调用；setup_core 自己产出的
#: 日志、状态、错误都跟着切，避免英文界面里冒出中文。CLI 默认中文。
_UI_LANG = "zh"


def set_ui_lang(lang: str) -> None:
    global _UI_LANG
    _UI_LANG = "en" if str(lang or "").lower().startswith("en") else "zh"


def ui_lang() -> str:
    return _UI_LANG


def tr(zh: str, en: str) -> str:
    """按当前界面语言二选一（日志 / 状态 / 错误用）。"""
    return en if _UI_LANG == "en" else zh


def kind_label(kind: str) -> str:
    return (KIND_LABEL_EN if _UI_LANG == "en" else KIND_LABEL).get(kind, kind)

#: 官方发布页 / 文档（安装器只跳转，不打包、不再分发这些第三方加载器）
URL_ME2_RELEASES = "https://github.com/soulsmods/ModEngine2/releases"
URL_ME3_RELEASES = "https://github.com/garyttierney/me3/releases"
URL_ME3_DOCS = "https://github.com/garyttierney/me3"
URL_ME3_PROFILES = ("https://github.com/garyttierney/me3/blob/main/"
                    "docs/user-guide/creating-mod-profiles.md")
URL_CONVERGENCE = "https://www.nexusmods.com/eldenring/mods/3419"

ME2_PLUGIN_DIR = pathlib.Path("mods") / "ER-Echo"
ME3_PLUGIN_DIR = pathlib.Path("er-echo")

#: 安装器在插件目录里记录「这次用哪个加载器 + me3.exe 在哪」，启动时照着走
LOADER_MARKER = "er_echo_loader.json"
#: 原版 + me3 时写在游戏根目录的 me3 profile（相对路径）
ME3_VANILLA_PROFILE = "er-echo.me3"

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
        tr("找不到 payload 目录（安装包不完整）。找过：\n  ",
           "Payload folder not found (incomplete installer). Looked in:\n  ")
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
            s = tr(f"Mod Engine 2 · 游戏目录 {self.root}",
                   f"Mod Engine 2 · game folder {self.root}")
        elif self.kind == KIND_ME3:
            s = tr(f"Mod Engine 3 · Convergence {self.root}",
                   f"me3 · Convergence {self.root}")
        else:
            return tr("未识别：这里既不是游戏目录，也不是 Convergence 目录",
                      "Unrecognised: neither a game folder nor a Convergence folder")
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


_ME3_REGISTRY_CACHE: dict = {"at": 0.0, "dirs": []}


def _me3_registry_install_dirs() -> list[pathlib.Path]:
    """从「卸载」注册表项找 me3 的 InstallLocation（官方 installer 会写）。"""
    now = time.time()
    if now - _ME3_REGISTRY_CACHE["at"] < 3.0:
        return list(_ME3_REGISTRY_CACHE["dirs"])
    out: list[pathlib.Path] = []
    try:
        import winreg
    except ImportError:
        return out
    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, sub in roots:
        try:
            with winreg.OpenKey(hive, sub) as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        child = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, child) as k:
                            try:
                                display = str(winreg.QueryValueEx(k, "DisplayName")[0])
                            except OSError:
                                continue
                            low = display.lower()
                            if "me3" not in low and "mod engine 3" not in low:
                                continue
                            try:
                                loc = str(winreg.QueryValueEx(k, "InstallLocation")[0]).strip()
                            except OSError:
                                continue
                            if loc:
                                out.append(pathlib.Path(loc))
                    except OSError:
                        continue
        except OSError:
            continue
    _ME3_REGISTRY_CACHE["at"] = now
    _ME3_REGISTRY_CACHE["dirs"] = list(out)
    return out


def _registry_path_dirs() -> list[str]:
    """用户/机器 PATH。当前进程可能是在 me3 安装前启动的，进程 PATH 是旧的。"""
    out: list[str] = []
    try:
        import winreg
    except ImportError:
        return out
    for hive, sub, name in (
        (winreg.HKEY_CURRENT_USER, r"Environment", "Path"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "Path"),
    ):
        try:
            with winreg.OpenKey(hive, sub) as k:
                value = str(winreg.QueryValueEx(k, name)[0])
        except OSError:
            continue
        out += [p for p in value.split(";") if p.strip()]
    return out


def _find_filename_in_dirs(dirs: list[str], filename: str) -> pathlib.Path | None:
    seen: set[str] = set()
    for raw in dirs:
        raw = os.path.expandvars(raw.strip().strip('"'))
        if not raw or raw.lower() in seen:
            continue
        seen.add(raw.lower())
        for cand in (pathlib.Path(raw) / filename,
                     pathlib.Path(raw) / (filename + ".exe")):
            try:
                if cand.is_file():
                    return cand
            except OSError:
                continue
    return None


def find_me3_exe(root: pathlib.Path | None = None,
                 explicit: str | pathlib.Path | None = None) -> pathlib.Path | None:
    """me3.exe 可能在哪：显式路径 / ME3_PATH / 目标目录 / PATH / 注册表安装目录。"""
    cands: list[pathlib.Path] = []

    def add_candidate(value: str | pathlib.Path | None) -> None:
        if value is None:
            return
        p = pathlib.Path(str(value).strip().strip('"'))
        cands.append(p)
        # 允许用户选安装目录而不是 exe
        if p.is_dir():
            cands.extend([p / "bin" / "me3.exe", p / "me3.exe"])

    add_candidate(explicit)
    add_candidate(os.environ.get("ME3_PATH"))
    if root is not None:
        cands += [root / "me3" / "Windows" / "me3.exe",
                  root / "me3" / "me3.exe",
                  root / "me3.exe",
                  root / "bin" / "me3.exe"]
    try:
        which = shutil.which("me3") or shutil.which("me3.exe")
    except OSError:
        which = None
    if which:
        cands.append(pathlib.Path(which))
    for install_dir in _me3_registry_install_dirs():
        cands += [install_dir / "bin" / "me3.exe", install_dir / "me3.exe"]
    for env in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(env)
        if not base:
            continue
        cands += [pathlib.Path(base) / "Programs" / "me3" / "bin" / "me3.exe",
                  pathlib.Path(base) / "Programs" / "me3" / "me3.exe",
                  pathlib.Path(base) / "me3" / "bin" / "me3.exe",
                  pathlib.Path(base) / "me3" / "me3.exe"]
    # 旧进程 PATH 里没有新装的 me3 时，补查用户/机器注册表 PATH
    from_path = _find_filename_in_dirs(
        list(os.environ.get("PATH", "").split(os.pathsep)) + _registry_path_dirs(), "me3.exe")
    if from_path is not None:
        cands.append(from_path)

    seen: set[str] = set()
    for cand in cands:
        key = str(cand).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
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
        return Target(KIND_UNKNOWN, raw, notes=[
            tr("路径不存在", "Path does not exist")])

    if (raw / "eldenring.exe").is_file():
        kind = KIND_ME2
        game = raw
        if not (raw / "modengine2_launcher.exe").is_file():
            notes.append(tr("没找到 modengine2_launcher.exe：需要先装 Mod Engine 2",
                    "modengine2_launcher.exe not found: install Mod Engine 2 first"))
        if (raw / "me3").is_dir():
            notes.append(tr("这个目录里也有 me3\\，是不是想装到 Convergence？",
                    "This folder also has me3\\. Install into Convergence instead?"))
        return Target(kind, game, game_dir=game, notes=notes)

    conv = _conv_root_of(raw)
    if conv is not None:
        notes.append(f"me3: {me3_exe(conv)}")
        game = _steam_game_for(conv)
        if game is not None:
            notes.append(tr(f"游戏本体: {game}", f"Game install: {game}"))
        return Target(KIND_ME3, conv, game_dir=game, me3=me3_exe(conv), notes=notes)

    notes.append(tr("看不到 eldenring.exe，也看不到 me3\\Windows\\me3.exe + mod\\",
                    "Neither eldenring.exe nor me3\\Windows\\me3.exe + mod\\ found"))
    return Target(KIND_UNKNOWN, raw, notes=notes)


def _steam_game_for(conv: pathlib.Path) -> pathlib.Path | None:
    games = find_game_dirs()
    return games[0] if games else None


def read_loader_marker(plugin: pathlib.Path) -> dict:
    path = plugin / LOADER_MARKER
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_loader_marker(plugin: pathlib.Path, loader: str,
                        me3_path: pathlib.Path | None = None) -> None:
    plugin.mkdir(parents=True, exist_ok=True)
    data: dict = {"loader": loader}
    if me3_path is not None:
        data["me3_path"] = str(me3_path)
    (plugin / LOADER_MARKER).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def loader_status(path: str | pathlib.Path, loader: str = "auto",
                  me3_path: str | pathlib.Path | None = None) -> dict:
    """目标需要/已有哪些加载器（给安装器做选择、状态和下载引导；只检测，不安装）。

    * 原版（me2）可选 Mod Engine 2 或独立 me3；`preferred` 是当前选择/记录。
    * Convergence（me3）固定用自带 me3；`find_me3_exe` 也会找 PATH / 注册表里的独立 me3。
    """
    t = probe(path)
    out: dict = {
        "kind": t.kind,
        "kind_label": kind_label(t.kind),
        "root": str(t.root),
        "me2": False,
        "me3": False,
        "me3_path": None,
        "mode": None,
        "installed": False,
        "preferred": None,
        "missing": None,
    }
    if t.kind == KIND_UNKNOWN:
        return out

    plugin = t.plugin_dir
    marker = read_loader_marker(plugin)
    out["mode"] = marker.get("loader")
    out["installed"] = (plugin / "er_echo.dll").is_file()
    if t.kind == KIND_ME2:
        out["me2"] = (t.root / "modengine2_launcher.exe").is_file()

    exe = find_me3_exe(t.root, explicit=me3_path or marker.get("me3_path"))
    out["me3"] = exe is not None
    out["me3_path"] = str(exe) if exe is not None else None

    if t.kind == KIND_ME3:
        out["mode"] = "me3"
        out["preferred"] = "me3"
        return out

    want = (loader or "auto").lower()
    if want not in ("auto", "me2", "me3"):
        want = "auto"
    if want == "auto":
        installed_mode = out["mode"] if out["installed"] else None
        if installed_mode == "me3":
            # 按记录走 me3；只有 me3 没了但 ME2 还在时才退回 ME2
            preferred = "me3" if (out["me3"] or not out["me2"]) else "me2"
        elif installed_mode == "me2":
            preferred = "me2" if (out["me2"] or not out["me3"]) else "me3"
        elif out["me2"]:
            preferred = "me2"
        elif out["me3"]:
            preferred = "me3"
        else:
            preferred = "me2"
    else:
        preferred = want
    out["preferred"] = preferred
    if preferred == "me2" and not out["me2"]:
        out["missing"] = "me2"
    if preferred == "me3" and not out["me3"]:
        out["missing"] = "me3"
    return out


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
        return (p if p.is_file() else None), (
        tr("指定存档", "given save file") if p.is_file()
        else tr("指定存档不存在", "given save file does not exist"))
    saves = find_saves()
    if not saves:
        return None, tr("没有找到存档（%APPDATA%\\EldenRing）",
                        "no save found (%APPDATA%\\EldenRing)")
    if kind == KIND_ME3:
        cnv = [p for p in saves if ".cnv" in p.name.lower()]
        if cnv:
            return cnv[0], tr("Convergence 存档（*.cnv）",
                          "Convergence save (*.cnv)")
        return saves[0], tr(
            "没找到 *.cnv 存档，暂用最新的原版存档（装备 id 可能与 Convergence 不同）",
            "no *.cnv save found; using the newest vanilla save "
            "(item ids may differ from Convergence)")
    plain = [p for p in saves if ".cnv" not in p.name.lower()]
    return ((plain[0] if plain else saves[0]),
            tr("原版存档", "vanilla save"))


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
            log(tr(f"[!] 跳过 {target.name}（{exc.__class__.__name__}: {exc}）——"
                   f"游戏正在运行的话，退出后重跑一次安装即可",
                   f"[!] skipped {target.name} ({exc.__class__.__name__}: {exc}) - "
                   f"close the game and run the install again"))
    return skipped


def _write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\r\n")


def _backup(path: pathlib.Path, log) -> pathlib.Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(path.name + ".bak-er-echo-" + stamp)
    shutil.copy2(path, bak)
    log(tr(f"[i] 备份 {path.name} -> {bak.name}",
           f"[i] backup {path.name} -> {bak.name}"))
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
; 菜单文案语言（只影响 mod 自己注入的那几行，不影响游戏原版文本）
;   game   = 跟随游戏文本语言（默认/推荐：自动读 Steam 的 per-game 语言）
;   auto   = 跟随 Windows 显示语言
;   zh-CN / zh-TW / en / ja，或任意自定义代码（配合 er_echo_i18n.ini）
language=game
"""


def _set_profiles(text: str, value: str) -> str:
    """只改 `profiles=` 一行（没有 [clone] 段就补一行），其余手改项原样保留。"""
    if re.search(r"(?m)^\s*profiles\s*=", text):
        # 用 lambda 当替换：Windows 路径里的反斜杠不能被当成转义
        return re.sub(r"(?m)^\s*profiles\s*=.*$", lambda _m: "profiles=" + value,
                      text, count=1)
    if "[clone]" in text:
        return text.replace("[clone]\n", "[clone]\nprofiles=" + value + "\n", 1)
    return text.rstrip() + "\n\n[clone]\nprofiles=" + value + "\n"


#: 安装器/CLI 里可选的菜单语言代码（DLL 认的值；显示名在 GUI 的 STRINGS 里）。
MENU_LANGUAGES: tuple[str, ...] = ("game", "auto", "zh-CN", "zh-TW", "en", "ja")
#: 没传/写坏时的菜单语言
DEFAULT_MENU_LANGUAGE = "game"


def normalize_menu_language(value: str | None) -> str:
    """把 `game` / `auto` / `zh_CN` / `CHS` 之类归一成安装器认识的值。"""
    raw = (value or "").strip()
    if not raw:
        return DEFAULT_MENU_LANGUAGE
    low = raw.lower().replace("_", "-")
    if low in ("game", "steam", "follow", "follow-game"):
        return "game"
    if low == "auto":
        return "auto"
    aliases = {
        "zh": "zh-CN", "cn": "zh-CN", "chs": "zh-CN", "zh-cn": "zh-CN",
        "zh-hans": "zh-CN", "zh-sg": "zh-CN",
        "tw": "zh-TW", "cht": "zh-TW", "zh-tw": "zh-TW", "zh-hk": "zh-TW",
        "zh-mo": "zh-TW", "zh-hant": "zh-TW",
        "en": "en", "en-us": "en", "en-gb": "en",
        "ja": "ja", "jp": "ja", "ja-jp": "ja",
    }
    if low in aliases:
        return aliases[low]
    # 其他语言代码原样保留（配合 er_echo_i18n.ini 新增语言）
    if re.fullmatch(r"[A-Za-z0-9-]{1,12}", raw):
        return raw
    return DEFAULT_MENU_LANGUAGE


def set_language(text: str, language: str) -> str:
    """把 ini 的 `[i18n] language=` 改成 `language`，其余行原样保留。"""
    value = normalize_menu_language(language)
    if re.search(r"(?m)^\s*language\s*=", text, re.IGNORECASE):
        return re.sub(r"(?m)^\s*language\s*=.*$",
                      lambda _m: "language=" + value, text, count=1,
                      flags=re.IGNORECASE)
    if re.search(r"(?m)^\s*\[i18n\]\s*$", text, re.IGNORECASE):
        return re.sub(r"(?m)^(\s*\[i18n\]\s*)$",
                      lambda m: m.group(1) + "\nlanguage=" + value, text, count=1,
                      flags=re.IGNORECASE)
    return text.rstrip() + "\n\n[i18n]\nlanguage=" + value + "\n"


def parse_ini_language(text: str) -> str | None:
    """读 ini 里的 `language=`（只认第一处；注释行不算）。"""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith((";", "#", "[")):
            continue
        m = re.match(r"language\s*=\s*(.+)$", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def ini_language(ini: pathlib.Path) -> str | None:
    """读某个 er_echo.ini 实际写的菜单语言；文件不在/读不了就 None。"""
    try:
        text = pathlib.Path(ini).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return parse_ini_language(text)


def apply_ini_language(ini: pathlib.Path, language: str, log=print) -> bool:
    """只改现有 ini 的 `[i18n] language=`（改前备份）；返回是否真的改了。"""
    ini = pathlib.Path(ini)
    if not ini.is_file():
        return False
    text = ini.read_text(encoding="utf-8", errors="replace")
    new = set_language(text, language)
    if new == text:
        log(tr(f"[i] {ini}: language={normalize_menu_language(language)} 已经是这个值",
               f"[i] {ini}: language is already {normalize_menu_language(language)}"))
        return False
    try:
        _backup(ini, log)
        _write_text(ini, new)
    except OSError:
        # 文件被标成只读（Steam 校验/搬过目录）时清掉只读再试一次；
        # 目录本身没权限的话这里还会再抛，由调用方（GUI）给管理员入口。
        os.chmod(ini, 0o666)
        _backup(ini, log)
        _write_text(ini, new)
    log(tr(f"[ok] {ini}: [i18n] language={normalize_menu_language(language)}（重启游戏后生效）",
               f"[ok] {ini}: [i18n] language={normalize_menu_language(language)} "
               f"(restart the game to apply)"))
    return True


def write_ini(ini: pathlib.Path, profiles: list[pathlib.Path], log,
              legacy: pathlib.Path | None = None,
              language: str | None = None) -> None:
    value = ",".join(str(p.resolve()) for p in profiles) if profiles else ""
    if ini.is_file():
        text = ini.read_text(encoding="utf-8", errors="replace")
    elif legacy is not None and legacy.is_file():
        # 第一次装成插件布局（mods\ER-Echo\）：旧版平铺在游戏根目录的 er_echo.ini
        # 里可能有玩家手改过的 [i18n] language / [ui] nested_menu 等。整份沿用再
        # 只改 profiles，否则会一律回落到模板默认（language=game），中文菜单会
        # 在换布局后悄悄变英文（2026-11-22 实测）。
        text = legacy.read_text(encoding="utf-8", errors="replace")
        log(tr(f"[i] 沿用旧配置 {legacy}（保留 [i18n] language 等手改项）",
               f"[i] reusing old config {legacy} (keeps [i18n] language and other hand edits)"))
    else:
        text = INI_TEMPLATE.replace("{{PROFILES}}", value)
    text = _set_profiles(text, value)
    # 语言：显式传了就以传进来的为准（安装器 GUI 的「游戏内菜单语言」），
    # 没传就保留 ini 里原来的值（沿用旧配置时尤其重要）。
    if language is not None:
        text = set_language(text, language)
    _write_text(ini, text)
    log(tr(f"[ok] 写入 {ini}：profiles={value or '(空)'}",
               f"[ok] wrote {ini}: profiles={value or '(empty)'}"))
    log(tr(f"[i] 菜单语言：{ini_language(ini) or '(默认)'}",
               f"[i] menu language: {ini_language(ini) or '(default)'}"))


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

#: 原版 + me3：profile 放游戏根目录，路径相对 profile（即相对游戏根目录）
ME3_VANILLA_PROFILE_TEXT = """profileVersion = "v1"

[[supports]]
game = "eldenring"

[[package]]
id = "er-echo"
path = "./mods/ER-Echo/mod"

# --- ER Echo (added by installer: vanilla + me3) ---
[[natives]]
path = "./mods/ER-Echo/er_echo.dll"
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
            changes.append(tr("新加 [modengine] external_dlls",
                                  "added [modengine] external_dlls"))

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
                changes.append(tr("新加 [extension.mod_loader] mods",
                                  "added [extension.mod_loader] mods"))
    return text, changes


def install_me2(t: Target, save: pathlib.Path | None, payload: pathlib.Path, log,
                language: str = DEFAULT_MENU_LANGUAGE) -> dict:
    game = t.root
    plugin = game / ME2_PLUGIN_DIR
    result: dict = {"kind": KIND_ME2, "loader": "me2", "root": str(game),
                    "plugin": str(plugin), "changes": []}

    log(tr(f"[..] 安装到 {plugin}（加载器：Mod Engine 2）",
               f"[..] installing to {plugin} (loader: Mod Engine 2)"))
    _copy_tree(payload / "shared", plugin, log)
    _copy_tree(payload / "me2" / "plugin", plugin, log)
    write_loader_marker(plugin, "me2")
    result["changes"].append(tr(f"拷贝 payload -> {plugin}",
                                        f"copied payload -> {plugin}"))

    # 自带 ME2 配置（不动 config_eldenring.toml 也能启动）
    cfg = game / "config-er-echo.toml"
    src = payload / "me2" / "config-er-echo.toml"
    if not cfg.is_file():
        if src.is_file():
            shutil.copy2(src, cfg)
        else:
            _write_text(cfg, ME2_CONFIG)
        result["changes"].append(tr("写出 config-er-echo.toml",
                                        "wrote config-er-echo.toml"))

    main = game / "config_eldenring.toml"
    if main.is_file():
        text = main.read_text(encoding="utf-8", errors="replace")
        new, changes = _patch_config_eldenring(text)
        if changes:
            _backup(main, log)
            _write_text(main, new)
            result["changes"] += [f"config_eldenring.toml: {c}" for c in changes]
        else:
            log(tr("[i] config_eldenring.toml 已经有 er-echo 条目，跳过",
               "[i] config_eldenring.toml already has an er-echo entry; skipped"))
    else:
        log(tr("[!] 没找到 config_eldenring.toml（Mod Engine 2 没装？）",
               "[!] config_eldenring.toml not found (is Mod Engine 2 installed?)"))

    profiles = _install_profiles(plugin / "profiles", save, log, relative_to=game,
                                 table_dir=payload / "tables" / "vanilla")
    write_ini(game / ME2_PLUGIN_DIR / "er_echo.ini", profiles, log,
              legacy=game / "er_echo.ini", language=language)
    result["profiles"] = [str(p) for p in profiles]
    result["launch"] = str(plugin / "launch-er-echo.bat")
    return result


def install_vanilla_me3(t: Target, save: pathlib.Path | None, payload: pathlib.Path,
                        log, me3_path: str | pathlib.Path | None = None,
                        language: str = DEFAULT_MENU_LANGUAGE) -> dict:
    """原版 + 独立 me3：同样装 mods\\ER-Echo，但配置改成游戏根目录的 er-echo.me3。"""
    game = t.root
    plugin = game / ME2_PLUGIN_DIR
    exe = find_me3_exe(game, explicit=me3_path)
    result: dict = {"kind": KIND_ME2, "loader": "me3", "root": str(game),
                    "plugin": str(plugin), "changes": []}

    log(tr(f"[..] 安装到 {plugin}（加载器：me3）",
               f"[..] installing to {plugin} (loader: me3)"))
    _copy_tree(payload / "shared", plugin, log)
    _copy_tree(payload / "me2" / "plugin", plugin, log)
    result["changes"].append(tr(f"拷贝 payload -> {plugin}",
                                        f"copied payload -> {plugin}"))

    profile = game / ME3_VANILLA_PROFILE
    if profile.is_file():
        old = profile.read_text(encoding="utf-8", errors="replace")
        if "er_echo.dll" not in old:
            _backup(profile, log)
    _write_text(profile, ME3_VANILLA_PROFILE_TEXT)
    result["changes"].append(
            tr(f"写出 {ME3_VANILLA_PROFILE}（[[natives]] + [[package]]）",
               f"wrote {ME3_VANILLA_PROFILE} ([[natives]] + [[package]])"))
    log(tr(f"[ok] 写入 {profile}", f"[ok] wrote {profile}"))

    # me3 自己会挂 package；不再改 ME2 的 config_eldenring.toml
    profiles = _install_profiles(plugin / "profiles", save, log, relative_to=game,
                                 table_dir=payload / "tables" / "vanilla")
    write_ini(plugin / "er_echo.ini", profiles, log, legacy=game / "er_echo.ini",
              language=language)
    write_loader_marker(plugin, "me3", exe)
    result["profiles"] = [str(p) for p in profiles]
    result["me3"] = str(exe) if exe is not None else None
    result["me3_path"] = str(exe) if exe is not None else None
    result["launch"] = (f"{exe} launch --auto-detect -p .\\{ME3_VANILLA_PROFILE}"
                        if exe is not None else
                        f"me3 launch --auto-detect -p .\\{ME3_VANILLA_PROFILE}")
    if exe is None:
        log(tr("[!] 还没找到 me3.exe：装好 me3 后重新点「一键安装」，或把 me3.exe 加到 PATH",
               "[!] me3.exe not found yet: install me3 and click Install again, "
               "or add me3.exe to PATH"))
    return result


# ---------------------------------------------------------------- ME3 / Convergence

def _me3_block(dll_rel: str) -> str:
    return "\n# --- ER Echo (added by installer) ---\n[[natives]]\npath = '" + dll_rel + "'\n"


def install_me3(t: Target, save: pathlib.Path | None, payload: pathlib.Path, log,
                language: str = DEFAULT_MENU_LANGUAGE) -> dict:
    conv = t.root
    plugin = conv / ME3_PLUGIN_DIR
    result: dict = {"kind": KIND_ME3, "loader": "me3", "root": str(conv),
                    "plugin": str(plugin), "changes": []}

    log(tr(f"[..] 安装到 {plugin}（加载器：Convergence 自带的 me3）",
               f"[..] installing to {plugin} (loader: me3 bundled with Convergence)"))
    _copy_tree(payload / "shared", plugin, log)
    write_loader_marker(plugin, "me3", find_me3_exe(conv))
    result["changes"].append(tr(f"拷贝 payload -> {plugin}",
                                        f"copied payload -> {plugin}"))

    # 赐福菜单：默认不覆盖 Convergence 的 talk ESD（它会覆盖 m00_00_00_00），
    # 只有 payload/me3/mod 存在时才挂载我们自己的包。
    esd_src = payload / "me3" / "mod"
    esd_pkg = None
    if esd_src.is_dir():
        _copy_tree(esd_src, plugin / "mod", log)
        esd_pkg = plugin / "mod"
        result["changes"].append(tr("挂载自带 ESD 包",
                                        "mounted bundled ESD package"))

    dll = plugin / "er_echo.dll"
    if not dll.is_file():
        raise SystemExit(tr(f"payload 不完整：缺少 {dll}",
                        f"incomplete payload: missing {dll}"))

    dll_rel = "./../er-echo/er_echo.dll"
    for prof in me3_profiles(conv):
        text = prof.read_text(encoding="utf-8", errors="replace")
        if "er_echo.dll" in text:
            log(tr(f"[i] {prof.name} 已经有 er_echo.dll，跳过",
               f"[i] {prof.name} already references er_echo.dll; skipped"))
            continue
        _backup(prof, log)
        block = _me3_block(dll_rel)
        if esd_pkg is not None:
            block = ("\n# --- ER Echo (added by installer) ---\n[[package]]\n"
                     "id = \"er-echo\"\npath = './../er-echo/mod'\n") + block
        prof.write_text(text.rstrip() + "\n" + block, encoding="utf-8", newline="\r\n")
        result["changes"].append(f"{prof.name}: + [[natives]] er_echo.dll")
        log(tr(f"[ok] 已改 {prof}", f"[ok] patched {prof}"))

    if not me3_profiles(conv):
        log(tr("[!] me3\\ 下没有 *.me3 配置，Convergence 装得不对？",
               "[!] no *.me3 profile under me3\\ - is Convergence installed correctly?"))

    profiles = _install_profiles(plugin / "profiles", save, log, relative_to=None,
                                 table_dir=payload / "tables" / "convergence",
                                 merge_existing=False)
    write_ini(plugin / "er_echo.ini", profiles, log, legacy=conv / "er_echo.ini",
              language=language)
    result["profiles"] = [str(p) for p in profiles]
    conv_me3 = find_me3_exe(conv)
    result["me3_path"] = str(conv_me3) if conv_me3 else None
    result["launch"] = str(conv / "Start_Convergence.bat")
    return result


# ---------------------------------------------------------------- 共用

def _install_profiles(dirpath: pathlib.Path, save: pathlib.Path | None, log,
                      relative_to: pathlib.Path | None,
                      table_dir: pathlib.Path | None = None,
                      merge_existing: bool = True) -> list[pathlib.Path]:
    """导出存档角色 + 固定内置档案；失败就留示例档案。

    内置档案（payload `shared\\profiles\\builtin_*.json`）的处理规则：
      * 每次安装都用发布版**覆盖**到 profiles 目录（重装 = 恢复成原版）；
      * 永远追加在名单**末尾**，导出工具只写 `slot<N>_*.json`、不会覆盖它；
      * Convergence 清理「过时 slot*.json」时也不会删它（它不是 slot*）。
    """
    dirpath.mkdir(parents=True, exist_ok=True)
    shared = payload_dir() / "shared" / "profiles"
    builtins: list[pathlib.Path] = []
    for src in sorted(shared.glob("builtin_*.json")):
        dest = dirpath / src.name
        shutil.copy2(src, dest)
        builtins.append(dest)
    if builtins:
        log(tr("[i] 内置档案：%s（固定在 profiles 名单末尾，导出/重装不会覆盖）"
               % ", ".join(p.stem for p in builtins),
               "[i] built-in profile(s): %s (always last in profiles=; "
               "export/reinstall never overwrites them)"
               % ", ".join(p.stem for p in builtins)))

    example = shared / "profile.example.json"
    # 有内置角色时就不需要「示例档案」这个空壳了；老安装已经有这份文件也不影响（不在名单里）。
    if example.is_file() and not builtins and not (dirpath / example.name).is_file():
        shutil.copy2(example, dirpath / example.name)

    written: list[pathlib.Path] = []
    if save is None:
        log(tr("[!] 没有存档，先用内置/示例档案（进游戏后可在导出页换成本人角色）",
               "[!] no save file: using the built-in/example profile "
               "(you can export your own on the Profiles tab later)"))
    else:
        log(tr(f"[..] 解析存档 {save}", f"[..] reading save {save}"))
        try:
            written = _export_via_core_import(save, dirpath, log, table_dir)
        except Exception as exc:  # noqa: BLE001 - 导出失败不该让安装失败
            log(tr(f"[!] 导出失败：{exc}", f"[!] export failed: {exc}"))
        if not written:
            log(tr("[!] 存档里没有可解析的完整角色，先用内置/示例档案",
               "[!] no complete character found in the save; using the built-in/example profile"))

    if not merge_existing and written:
        # Convergence 例外：它的物品 id 和原版不同，旧档案（原版存档导出的）会穿错装备，
        # 所以 me3 目标只保留本次导出的 slot*.json。内置档案不是 slot*，不受影响。
        keep = {p for p in written}
        for stale in dirpath.glob("slot*.json"):
            if stale not in keep:
                stale.unlink(missing_ok=True)
                log(tr(f"[i] 删除过时档案 {stale.name}（Convergence 的 id 和原版不同）",
               f"[i] removed stale profile {stale.name} (Convergence item ids differ from vanilla)"))
        ordered = list(written)
    else:
        ordered = []
        for p in sorted(dirpath.glob("slot*.json")) + written:
            if p not in ordered:
                ordered.append(p)

    for b in builtins:
        if b not in ordered:
            ordered.append(b)

    if not ordered:
        fallback = dirpath / example.name
        if fallback.is_file():
            ordered = [fallback]
    return ordered


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
            log(tr(f"[i] 装备表：{eq.name}", f"[i] equipment table: {eq.name}"))
        if mg.is_file() and core.load_magic_table(mg):
            log(tr(f"[i] 法术表：{mg.name}", f"[i] magic table: {mg.name}"))
    if not loaded:
        tables = gui.lookup_tables()   # 退回到「游戏根目录 / tools 旁边」找
        log(tr(f"[i] 装备表：{tables.get('equip') or '缺失（弱校验，部分角色会判不完整）'}",
               f"[i] equipment table: {tables.get('equip') or 'missing (weak check; some characters may look incomplete)'}"))
        log(tr(f"[i] 法术表：{tables.get('magic') or '缺失（区间校验）'}",
               f"[i] magic table: {tables.get('magic') or 'missing (range check only)'}"))

    rows = gui.scan_save(save, on_slot=lambda slot, ch: log(
        f"  slot {slot}: {ch.get('name')} lv{ch.get('level')}"
        + ("" if ch.get("complete") else tr("  (缺脸/装备)", "  (missing face/equipment)"))))

    good = [r for r in rows if r["ch"].get("complete")]
    if good:
        return gui.export_profiles(save, good, outdir)

    # 一个都不「完整」时不要空手而归：全部导出，但在 ini 里能用就行
    if rows:
        log(tr("[!] 没有通过完整性校验的角色，改为全部导出（外观可能不完整）",
               "[!] no character passed the completeness check; exporting all (looks may be incomplete)"))
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
        raise SystemExit(tr(f"端口 {port} 被占用（是不是 bridge/director.py 在跑？）：{exc}",
                        f"port {port} is busy (is bridge/director.py running?): {exc}"))
    sock.listen(1)
    sock.settimeout(wait)
    log(tr(f"[..] 等游戏里的 DLL 连上来（{host}:{port}，最多 {wait:.0f} 秒）",
               f"[..] waiting for the in-game DLL to connect ({host}:{port}, "
               f"up to {wait:.0f}s)"))
    try:
        conn, _ = sock.accept()
    except socket.timeout:
        sock.close()
        raise SystemExit(tr("游戏没有连上来：确认游戏正在运行、且 er_echo.dll 已加载",
                        "the game did not connect: make sure it is running and er_echo.dll is loaded"))
    finally:
        try:
            sock.close()
        except OSError:
            pass

    with conn:
        hello = _ipc_read(conn, 10.0) or {}
        if hello.get("type") != "hello":
            raise SystemExit(tr(f"DLL 握手失败：{hello!r}", f"DLL handshake failed: {hello!r}"))
        log(tr(f"[ok] DLL 已连接：{hello.get('client')} v{hello.get('version')}",
               f"[ok] DLL connected: {hello.get('client')} v{hello.get('version')}"))
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
        raise SystemExit(tr(f"{cmd} 没有回执（超时）", f"{cmd}: no reply (timeout)"))


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
            log(tr(f"[!] {cmd} 失败：{msg}", f"[!] {cmd} failed: {msg}"))
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
            log(tr(f"[ok] {target} ({size} 字节)", f"[ok] {target} ({size} bytes)"))
        else:
            result["errors"].append(tr(f"{cmd}: 没看到 {name} 落盘",
                                       f"{cmd}: {name} was not written"))
            log(tr(f"[!] 没看到 {name} 落盘（DLL 的 CWD 可能不在游戏根目录）",
               f"[!] {name} was not written (the DLL CWD may not be the game root)"))
    return result


# ---------------------------------------------------------------- 一键启动

@dataclass
class LaunchPlan:
    """「一键启动」要执行的命令（不真的启动，方便预览/自检）。

    原版（me2）启动的是插件自带 `mods\\ER-Echo\\launch-er-echo.bat`；
    原版 + me3 启动 `<Game>\\er-echo.me3`（`me3 launch -p`）；
    Convergence（me3）直接调 `me3\\Windows\\me3.exe launch -p <convergence*.me3>`，
    和它自己的 `Start_Convergence.bat` 等价（但不会先 taskkill 已在跑的游戏）。
    """

    kind: str
    ok: bool
    reason: str = ""
    method: str = ""                       # "me2-bat" | "me3"
    command: list[str] = field(default_factory=list)
    cwd: pathlib.Path | None = None
    script: pathlib.Path | None = None     # 实际执行/查看的那份（bat 或 .me3）
    admin: bool = False
    seamless: bool = False
    notes: list[str] = field(default_factory=list)
    code: str = ""                         # 失败原因代码：loader-missing / install-missing / ...
    loader: str = ""                       # 缺哪个加载器：me2 / me3

    @property
    def display_command(self) -> str:
        return subprocess.list2cmdline([str(c) for c in self.command])

    @property
    def summary(self) -> str:
        """给界面/日志看的一行说明（相对路径，不暴露太长的绝对路径）。"""
        if self.script is None:
            return self.display_command
        base = self.cwd or self.script.parent
        try:
            rel = self.script.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            rel = self.script.as_posix()
        if self.method in ("me3", "me3-vanilla"):
            return f"me3.exe launch --auto-detect -p {rel}"
        return rel


def game_running() -> bool:
    """eldenring.exe 是否正在运行（查不到就当没运行，不阻塞启动）。"""
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq eldenring.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "eldenring.exe" in (out or "").lower()


def pick_me3_profile(conv: pathlib.Path) -> tuple[pathlib.Path | None, bool, list[str]]:
    """按 Convergence 自己的规则挑 .me3：有 SeamlessCoop 就优先无缝配置。"""
    notes: list[str] = []
    d = conv / "me3"
    seamless = d / "convergence - seamless.me3"
    normal = d / "convergence.me3"
    if (conv / "SeamlessCoop" / "ersc.dll").is_file():
        if seamless.is_file():
            return seamless, True, notes
        notes.append(tr("装了 SeamlessCoop，但没有 convergence - seamless.me3，改用普通配置",
                        "SeamlessCoop is installed but convergence - seamless.me3 is missing; "
                        "using the normal profile"))
    if normal.is_file():
        return normal, False, notes
    for prof in me3_profiles(conv):
        try:
            if "er_echo.dll" in prof.read_text(encoding="utf-8", errors="replace"):
                notes.append(f"没有 convergence.me3，改用 {prof.name}")
                return prof, False, notes
        except OSError:
            continue
    return None, False, notes


def _me2_launch_plan(t: Target, admin: bool) -> LaunchPlan:
    root = t.root
    plugin = root / ME2_PLUGIN_DIR
    if not (root / "eldenring.exe").is_file():
        return LaunchPlan(t.kind, False,
                          tr("不是游戏目录（没有 eldenring.exe）",
                             "not a game folder (no eldenring.exe)"), code="not-game")
    if not (plugin / "er_echo.dll").is_file():
        return LaunchPlan(t.kind, False,
                          tr("还没安装 ER Echo（先点「一键安装」）",
                             "ER Echo is not installed (click Install first)"),
                          code="install-missing")
    if not (root / "modengine2_launcher.exe").is_file():
        return LaunchPlan(t.kind, False,
                          tr("游戏目录里没有 modengine2_launcher.exe（先装 Mod Engine 2）",
                             "modengine2_launcher.exe not found (install Mod Engine 2 first)"),
                          code="loader-missing", loader="me2")
    if not (root / "config-er-echo.toml").is_file():
        return LaunchPlan(t.kind, False,
                          tr("缺少 config-er-echo.toml（重新点「一键安装」）",
                             "config-er-echo.toml is missing (click Install again)"),
                          code="install-missing")

    notes: list[str] = []
    name = "launch-er-echo-admin.bat" if admin else "launch-er-echo.bat"
    bat = plugin / name
    if admin and not bat.is_file():
        bat = plugin / "launch-er-echo.bat"
        notes.append(tr("安装里没有 admin 版启动脚本，改用普通版 + 提权",
                        "no admin launcher script; using the normal one with elevation"))
    if not bat.is_file():
        return LaunchPlan(t.kind, False,
                          tr(f"缺少启动脚本 {bat}（重新点「一键安装」）",
                             f"launcher script {bat} is missing (click Install again)"),
                          code="install-missing")
    return LaunchPlan(t.kind, True, method="me2-bat",
                      command=["cmd.exe", "/c", str(bat)], cwd=root,
                      script=bat, admin=admin, notes=notes)


def _me3_vanilla_launch_plan(t: Target, admin: bool,
                             me3_path: str | pathlib.Path | None = None) -> LaunchPlan:
    """原版 + 独立 me3：`<Game>\\er-echo.me3` + me3.exe launch。"""
    root = t.root
    plugin = root / ME2_PLUGIN_DIR
    if not (root / "eldenring.exe").is_file():
        return LaunchPlan(t.kind, False,
                          tr("不是游戏目录（没有 eldenring.exe）",
                             "not a game folder (no eldenring.exe)"), code="not-game")
    if not (plugin / "er_echo.dll").is_file():
        return LaunchPlan(t.kind, False,
                          tr("还没安装 ER Echo（先点「一键安装」）",
                             "ER Echo is not installed (click Install first)"),
                          code="install-missing")

    marker = read_loader_marker(plugin)
    profile = root / ME3_VANILLA_PROFILE
    if not profile.is_file():
        return LaunchPlan(t.kind, False,
                          tr(f"还没生成 {ME3_VANILLA_PROFILE}（加载器选 me3 重新点「一键安装」）",
                             f"{ME3_VANILLA_PROFILE} was not generated (pick me3 and click Install again)"),
                          code="install-missing")
    try:
        text = profile.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return LaunchPlan(t.kind, False,
                          tr(f"读不了 {profile.name}：{exc}",
                             f"cannot read {profile.name}: {exc}"), code="install-missing")
    if "er_echo.dll" not in text:
        return LaunchPlan(t.kind, False,
                          tr(f"{profile.name} 里没有 er_echo.dll 条目（重新点「一键安装」）",
                             f"{profile.name} has no er_echo.dll entry (click Install again)"),
                          code="install-missing")

    exe = find_me3_exe(root, explicit=me3_path or marker.get("me3_path"))
    if exe is None:
        return LaunchPlan(t.kind, False,
                          tr("没找到 me3.exe（先装 me3，或在安装页指定 me3.exe 路径）",
                             "me3.exe not found (install me3, or pick me3.exe on the Setup tab)"),
                          code="loader-missing", loader="me3")
    return LaunchPlan(t.kind, True, method="me3-vanilla",
                      command=[str(exe), "launch", "--auto-detect", "-p",
                               ".\\" + ME3_VANILLA_PROFILE],
                      cwd=root, script=profile, admin=admin, loader="me3",
                      notes=[f"me3: {exe}"])


def _launch_name(plan: LaunchPlan) -> str:
    if plan.method == "me2-bat":
        return "Mod Engine 2"
    if plan.code == "loader-missing" and plan.loader == "me2":
        return "Mod Engine 2"
    return "me3"


def _prefer_launch(primary: LaunchPlan, fallback: LaunchPlan) -> LaunchPlan:
    if primary.ok:
        return primary
    if fallback.ok:
        fallback.notes.append(
            tr(f"首选 {_launch_name(primary)} 不可用，改用 {_launch_name(fallback)}",
               f"preferred {_launch_name(primary)} unavailable; using {_launch_name(fallback)}"))
        return fallback
    return primary


def _me3_launch_plan(t: Target, admin: bool,
                     me3_path: str | pathlib.Path | None = None) -> LaunchPlan:
    conv = t.root
    exe = t.me3 or find_me3_exe(conv, explicit=me3_path)
    if exe is None:
        return LaunchPlan(t.kind, False,
                          tr("没找到 me3\\Windows\\me3.exe（Convergence 装得不对？）",
                             "me3\\Windows\\me3.exe not found (bad Convergence install?)"),
                          code="loader-missing", loader="me3")
    if not (conv / ME3_PLUGIN_DIR / "er_echo.dll").is_file():
        return LaunchPlan(t.kind, False,
                          tr("还没安装 ER Echo（先点「一键安装」）",
                             "ER Echo is not installed (click Install first)"),
                          code="install-missing")

    profile, seamless, notes = pick_me3_profile(conv)
    if profile is None:
        return LaunchPlan(t.kind, False,
                          tr("me3\\ 下没有可用的 *.me3 配置",
                             "no usable *.me3 profile under me3\\"),
                          code="install-missing")
    # 选中的配置里必须有我们追加的 [[natives]]；没有就退到另一份有它的（双配置只装了一半的情况）
    candidates = [profile] + [p for p in me3_profiles(conv) if p != profile]
    chosen: pathlib.Path | None = None
    for cand in candidates:
        try:
            text = cand.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "er_echo.dll" in text:
            chosen = cand
            break
    if chosen is None:
        return LaunchPlan(t.kind, False,
                          tr(f"{profile.name} 等 me3 配置里没有 er_echo.dll 条目（重新点「一键安装」）",
                             f"no er_echo.dll entry in {profile.name} and other me3 profiles "
                             f"(click Install again)"),
                          code="install-missing")
    if chosen != profile:
        notes.append(tr(f"{profile.name} 里没有 er_echo.dll，改用 {chosen.name}",
                        f"{profile.name} has no er_echo.dll; using {chosen.name}"))
        seamless = False
    profile = chosen

    # me3 的 -p 相对它的 CWD（Convergence 根目录），照抄 Start_Convergence.bat 的写法
    rel = profile.relative_to(conv).as_posix().replace("/", "\\")
    return LaunchPlan(t.kind, True, method="me3",
                      command=[str(exe), "launch", "--auto-detect", "-p", ".\\" + rel],
                      cwd=conv, script=profile, admin=admin, seamless=seamless, notes=notes)


def plan_launch(path: str | pathlib.Path, admin: bool = False,
                me3_path: str | pathlib.Path | None = None) -> LaunchPlan:
    """算出「一键启动」该跑什么，但不执行（界面预览 / --dry-run / 自检用）。

    原版目标会同时算 ME2 和 me3 两条链：按安装时记录的 loader 优先，另一条可用时兜底。
    """
    t = probe(path)
    if t.kind == KIND_UNKNOWN:
        return LaunchPlan(KIND_UNKNOWN, False,
                          tr(f"无法识别目标：{t.root}",
                             f"unrecognised target: {t.root}"), code="unknown")
    if t.kind == KIND_ME3:
        return _me3_launch_plan(t, admin, me3_path)

    me2_plan = _me2_launch_plan(t, admin)
    me3_plan = _me3_vanilla_launch_plan(t, admin, me3_path)
    mode = read_loader_marker(t.plugin_dir).get("loader")
    if mode == "me3":
        return _prefer_launch(me3_plan, me2_plan)
    if mode == "me2":
        return _prefer_launch(me2_plan, me3_plan)
    if me2_plan.ok:
        return me2_plan
    if me3_plan.ok:
        return me3_plan
    # 还没装过 / 两条都不可用：me3 已在但还没生成 profile 时，提示去安装（选 me3）
    if me2_plan.code == "loader-missing" and me3_plan.code == "install-missing":
        return me3_plan
    return me2_plan


def find_installed_targets() -> list[Target]:
    """所有「已装 ER Echo」的目标（原版 mods\\ER-Echo 或 Convergence er-echo）。"""
    out: list[Target] = []
    for game in find_game_dirs():
        if (game / ME2_PLUGIN_DIR / "er_echo.dll").is_file():
            out.append(probe(game))
    for conv in find_convergence_dirs():
        if (conv / ME3_PLUGIN_DIR / "er_echo.dll").is_file():
            out.append(probe(conv))
    return out


def _run_detached(plan: LaunchPlan, log=print) -> None:
    cmd = [str(c) for c in plan.command]
    cwd = str(plan.cwd) if plan.cwd is not None else None
    if plan.admin and os.name == "nt":
        # 提权：ShellExecuteW 的 runas 会走 UAC；bat 仍然交给 cmd /c
        import ctypes

        file = cmd[0]
        params = subprocess.list2cmdline(cmd[1:]) or None
        rc = int(ctypes.windll.shell32.ShellExecuteW(None, "runas", file, params, cwd, 1))
        if rc == 1223:                       # ERROR_CANCELLED：UAC 被点了「否」
            raise SystemExit(tr("已取消管理员权限请求，游戏没有启动",
                        "administrator request cancelled; the game was not started"))
        if rc <= 32:
            raise SystemExit(tr(f"提权启动失败（ShellExecuteW 返回 {rc}）",
                        f"elevated launch failed (ShellExecuteW returned {rc})"))
        log(tr("[i] 已请求管理员权限（UAC 允许后才会真正启动）",
               "[i] requested administrator rights (the game starts after UAC is accepted)"))
        return
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
    subprocess.Popen(cmd, cwd=cwd, creationflags=flags, close_fds=True)


def launch(path: str | pathlib.Path, admin: bool = False, dry_run: bool = False,
           log=print, me3_path: str | pathlib.Path | None = None) -> dict:
    """一键启动：原版（ME2 / 独立 me3）与 Convergence（自带 me3）自动走各自的启动链。

    返回可 JSON 序列化的结果（命令行、CWD、是否无缝、是否提权…）。
    `dry_run=True` 只算命令、不启动，测试/自检用。
    """
    plan = plan_launch(path, admin=admin, me3_path=me3_path)
    if not plan.ok:
        raise SystemExit(plan.reason)
    running = game_running()
    if running:
        log(tr("[!] eldenring.exe 已经在运行：再启动可能失败；先关掉当前游戏",
               "[!] eldenring.exe is already running; close it before launching again"))
    for note in plan.notes:
        log(f"[i] {note}")
    log(tr(f"[..] 启动（{kind_label(plan.kind)}）：{plan.display_command}",
               f"[..] launching ({kind_label(plan.kind)}): {plan.display_command}"))
    if not dry_run:
        _run_detached(plan, log)
        log(tr("[ok] 已发出启动命令", "[ok] launch command sent"))
    return {
        "kind": plan.kind,
        "kind_label": KIND_LABEL[plan.kind],
        "method": plan.method,
        "command": plan.command,
        "cwd": str(plan.cwd) if plan.cwd is not None else None,
        "summary": plan.summary,
        "display": plan.display_command,
        "admin": plan.admin,
        "seamless": plan.seamless,
        "code": plan.code,
        "loader": plan.loader,
        "game_running": running,
        "dry_run": dry_run,
        "notes": plan.notes,
    }


# ---------------------------------------------------------------- 入口

def install(path: str, save_override: str | None = None, log=print,
            force_kind: str | None = None, loader: str = "auto",
            me3_path: str | pathlib.Path | None = None,
            language: str = DEFAULT_MENU_LANGUAGE) -> dict:
    payload = payload_dir()
    for need in ("shared/er_echo.dll", "me2/config-er-echo.toml"):
        if not (payload / need).is_file():
            raise SystemExit(tr(f"payload 不完整，缺少 {payload / need}",
                        f"incomplete payload: missing {payload / need}"))
    t = probe(path)
    if force_kind:
        t.kind = force_kind
    if t.kind == KIND_UNKNOWN:
        raise SystemExit(tr(f"无法识别目标：{path}\n{t.describe()}",
                        f"unrecognised target: {path}\n{t.describe()}"))

    save, why = pick_save(t.kind, save_override)
    log(tr(f"[i] 存档：{save if save else '(无)'}  ({why})",
               f"[i] save: {save if save else '(none)'}  ({why})"))

    if t.kind == KIND_ME2:
        if not (t.root / "eldenring.exe").is_file():
            raise SystemExit(tr(f"不是游戏目录（没有 eldenring.exe）：{t.root}",
                        f"not a game folder (no eldenring.exe): {t.root}"))
        choice = (loader or "auto").lower()
        if choice not in ("auto", "me2", "me3"):
            choice = "auto"
        if choice == "auto":
            marker = read_loader_marker(t.plugin_dir).get("loader")
            me2_ok = (t.root / "modengine2_launcher.exe").is_file()
            me3_ok = find_me3_exe(t.root, explicit=me3_path) is not None
            if marker == "me3" and me3_ok:
                choice = "me3"
            elif marker == "me2" and me2_ok:
                choice = "me2"
            elif me2_ok:
                choice = "me2"
            elif me3_ok:
                choice = "me3"
            else:
                choice = "me2"
        log(tr(f"[i] 加载器：{'me3（独立安装）' if choice == 'me3' else 'Mod Engine 2'}",
               f"[i] loader: {'me3 (standalone)' if choice == 'me3' else 'Mod Engine 2'}"))
        if choice == "me3":
            res = install_vanilla_me3(t, save, payload, log, me3_path=me3_path,
                                      language=language)
        else:
            res = install_me2(t, save, payload, log, language=language)
    else:
        res = install_me3(t, save, payload, log, language=language)

    res.setdefault("loader", "me3" if t.kind == KIND_ME3 else "me2")
    res["loader_label"] = "me3" if res["loader"] == "me3" else "Mod Engine 2"
    res["kind_label"] = kind_label(t.kind)
    res["ini"] = str(t.ini_path)
    res["menu_language"] = ini_language(t.ini_path) or normalize_menu_language(language)
    res["save"] = str(save) if save else None
    res["save_note"] = why
    log(tr("[done] 安装完成", "[done] install finished"))
    return res


def uninstall(path: str, log=print) -> dict:
    t = probe(path)
    if t.kind == KIND_UNKNOWN:
        raise SystemExit(tr(f"无法识别目标：{path}", f"unrecognised target: {path}"))
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
        # 原版 + me3 时安装器生成的 profile 也一起清掉（只删我们写的那份）
        profile = t.root / ME3_VANILLA_PROFILE
        if profile.is_file():
            try:
                text = profile.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if "er_echo.dll" in text:
                profile.unlink()
                res["removed"].append(str(profile))
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
        log(tr(f"[ok] 删除 {plugin}", f"[ok] removed {plugin}"))
    for r in res["restored"]:
        log(tr(f"[ok] 恢复 {r}", f"[ok] restored {r}"))
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
    # 菜单语言：模板默认值 + 三种编辑路径（已有 language= / 只有 [i18n] / 完全没有）
    info["menu_language_template"] = parse_ini_language(INI_TEMPLATE)
    checks = [
        ("replace", INI_TEMPLATE, "zh-CN"),
        ("insert", "[clone]\nprofiles=foo.json\n", "ja"),
        ("append", "[ipc]\naddr=127.0.0.1:7811\n", "game"),
        ("alias", INI_TEMPLATE, "CHS"),
    ]
    for name, text, lang in checks:
        want = normalize_menu_language(lang)
        edited = set_language(text, lang)
        got = parse_ini_language(edited)
        info.setdefault("menu_language_checks", []).append(
            {"case": name, "want": want, "got": got})
        if got != want:
            info["errors"].append(f"set_language/{name}: got {got!r}, want {want!r}")
        if "profiles=foo.json" in text and "profiles=foo.json" not in edited:
            info["errors"].append(f"set_language/{name}: 把 profiles 行改坏了")

    def _target_entry(kind: str, path: pathlib.Path, extra: dict | None = None) -> dict:
        entry: dict = {"kind": kind, "path": str(path)}
        if extra:
            entry.update(extra)
        plan = plan_launch(path)
        entry["launch"] = {
            "ok": plan.ok,
            "method": plan.method,
            "command": plan.command,
            "reason": plan.reason,
            "code": plan.code,
            "loader": plan.loader,
            "seamless": plan.seamless,
        }
        entry["loader"] = loader_status(path)
        return entry

    for g in find_game_dirs():
        info["targets"].append(_target_entry(KIND_ME2, g))
    for c in find_convergence_dirs():
        info["targets"].append(_target_entry(
            KIND_ME3, c, {"profiles": [p.name for p in me3_profiles(c)]}))
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
    ap.add_argument("--launch", nargs="?", const="", metavar="PATH",
                    help="一键启动（PATH 可选；原版走 ME2 bat，Convergence 走 me3）")
    ap.add_argument("--launch-admin", "--admin", action="store_true", dest="launch_admin",
                    help="提权启动（UAC）")
    ap.add_argument("--dry-run", action="store_true", help="只打印启动命令，不真的启动")
    ap.add_argument("--save")
    ap.add_argument("--loader", choices=["auto", "me2", "me3"], default="auto",
                    help="原版加载器（auto = 有 ME2 用 ME2，否则有 me3 用 me3）")
    ap.add_argument("--me3", metavar="PATH", help="独立 me3.exe（或安装目录）路径")
    ap.add_argument("--menu-language", metavar="LANG", default=DEFAULT_MENU_LANGUAGE,
                    help="游戏内菜单语言：game（跟随游戏，默认）/ auto（跟随系统）/ "
                         "zh-CN / zh-TW / en / ja / 自定义代码")
    ap.add_argument("--set-language", nargs=2, metavar=("INI", "LANG"),
                    help="只改现有 er_echo.ini 的 [i18n] language=（不重装）")
    ap.add_argument("--force-kind", choices=[KIND_ME2, KIND_ME3])
    ap.add_argument("--selftest", metavar="OUT")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest(args.selftest)
    if args.set_language:
        ini, lang = args.set_language
        ok = apply_ini_language(pathlib.Path(ini), lang, log=print)
        print(json.dumps({"ini": str(ini), "language": normalize_menu_language(lang),
                          "changed": ok}, ensure_ascii=False))
        return 0 if ok or pathlib.Path(ini).is_file() else 1
    if args.detect is not None:
        if args.detect:
            t = probe(args.detect)
            print(t.describe())
            print(json.dumps({"kind": t.kind, "root": str(t.root)}, ensure_ascii=False))
        games = find_game_dirs()
        convs = find_convergence_dirs()
        print(tr("Steam 游戏目录：", "Steam game folders:"))
        for g in games:
            print("  ", g)
        print(tr("Convergence：", "Convergence:"))
        for c in convs:
            print("  ", c, [p.name for p in me3_profiles(c)])
        return 0
    if args.install:
        res = install(args.install, args.save, log=print, force_kind=args.force_kind,
                      loader=args.loader, me3_path=args.me3,
                      language=args.menu_language)
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
    if args.launch is not None:
        path = args.launch
        if not path:
            cands = find_installed_targets()
            if not cands:
                raise SystemExit(tr(
                    "没找到已安装的 ER Echo（原版 mods\\ER-Echo / Convergence er-echo）；"
                    "用 --launch <游戏路径> 指定",
                    "no installed ER Echo found (vanilla mods\\ER-Echo / Convergence er-echo); "
                    "pass --launch <game path>"))
            path = str(cands[0].root)
        res = launch(path, admin=args.launch_admin, dry_run=args.dry_run, log=print,
                     me3_path=args.me3)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
