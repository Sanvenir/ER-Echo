#!/usr/bin/env python3
"""ER Echo 存档导出工具（PyQt5，中英双语）。

功能：
  * 选存档 → 列出 0–9 号槽角色 → 多选导出 profile.json
  * 直接把 profiles= 写进 er_echo.ini（自动备份，不用手改配置）
  * 中文 / English 切换；默认英文；语言 / 游戏路径 / 存档 / 输出目录 / ini 路径都会记住

命令行：
    profile_export_gui.py                     # 打开窗口（默认英文）
    profile_export_gui.py --lang en           # 以英文启动
    profile_export_gui.py --lang auto         # 跟随系统语言启动
    profile_export_gui.py --selftest OUT      # 不开窗口，扫描默认存档并写结果
    profile_export_gui.py --write-ini INI JSON...   # 不开窗口，写 profiles=
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import sys
import time
import traceback

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import export_profile_from_save as core  # noqa: E402
import er_echo_setup as setup_core  # noqa: E402


# ------------------------------------------------------------------ i18n

STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "title": "ER Echo — 安装 / 导出",
        "save_label": "存档（ER0000*）：",
        "auto": "自动检测",
        "browse": "浏览…",
        "scan": "读取存档",
        "col_slot": "槽位",
        "col_name": "名字",
        "col_level": "等级",
        "col_runes": "卢恩",
        "col_status": "状态",
        "col_spells": "法术",
        "col_equip": "装备预览",
        "status_complete": "完整",
        "status_incomplete": "缺脸/装备",
        "out_label": "输出目录：",
        "export_sel": "导出选中",
        "export_all": "导出全部可解析",
        "open_dir": "打开目录",
        "ini_label": "er_echo.ini：",
        "ini_write": "写入 profiles",
        "ini_hint_missing": "没找到 er_echo.ini（装插件后通常在 mods\\ER-Echo\\）",
        "lang_label": "语言：",
        "ready": "就绪",
        "scanning": "读取存档…",
        "exporting": "导出中…",
        "no_save": "存档不存在",
        "no_rows": "先读取存档",
        "no_rows_msg": "先点「读取存档」列出角色。",
        "no_complete": "没有可导出的角色",
        "no_complete_msg": "选中的角色缺 FaceData/装备，无法导出。",
        "done_title": "导出完成",
        "done_msg": "写出 {n} 个文件：\n{d}\n\n是否把它们写进 er_echo.ini 的 profiles=？",
        "ini_done_title": "已写入配置",
        "ini_done_msg": "已更新：\n{p}\n\nprofiles={v}\n\n原文件备份为 {b}",
        "ini_fail_title": "写入失败",
        "ini_no_profiles": "还没有导出任何 profile，先导出一次。",
        "ini_missing_msg": "没有找到 er_echo.ini，请先安装插件，或手动选择。",
        "error_title": "出错了",
        "log_hint": "提示：导出的是离线档案，不需要进游戏；不会改存档。",
        "log_ini_found": "[i] er_echo.ini：{p}",
        "log_ini_missing": "[i] 没找到 er_echo.ini，导出后可手动选。",
        "log_equip_table": "[i] 装备 id 表：{n}",
        "log_magic_table": "[i] 法术 id 表：{n}",
        "log_no_equip": "[i] 没找到 er_echo_equip.json（只做弱校验）",
        "log_no_magic": "[i] 没找到 er_echo_magic.json（只做区间校验）",
        "log_autosave": "已自动选中最新存档。",
        "log_nosave": "没自动找到存档，请手动选。",
        "log_scan_start": "[..] 解析 {p}",
        "log_slot": "  slot {s}: {n} lv{l}",
        "log_incomplete": "  (缺脸/装备)",
        "log_chars": "[chars] {n} 个可解析角色",
        "log_export": "[..] 导出 {n} 个到 {d}",
        "log_written": "[ok] {p}",
        "log_export_done": "[done] 写出 {n} 个 profile 到 {d}",
        "log_ini_written": "[ok] 写入 {p}：profiles={v}",
        "log_ini_backup": "[i] 备份 {p}",
        "row_count": "{n} 个角色",
        "lang_name": "中文",
        "tab_setup": "安装 / 配置",
        "tab_export": "角色导出",
        "path_label": "游戏路径：",
        "detect": "自动检测",
        "install": "一键安装",
        "uninstall": "卸载",
        "kind_empty": "填一个路径，或点「自动检测」：\n原版填 ...\\ELDEN RING\\Game；Convergence 填 ...\\ConvergenceER",
        "kind_unknown_hint": "（这个路径里没有 eldenring.exe，也没有 me3\\Windows\\me3.exe）",
        "save2_label": "存档（ER0000*）：",
        "save2_hint": "留空 = 安装时自动挑（Convergence 优先 *.cnv 存档）",
        "installing": "安装中…",
        "uninstalling": "卸载中…",
        "confirm_title": "确认安装",
        "confirm_msg": "目标：{kind}\n目录：{path}\n\n会写入 mod 文件，并自动备份、修改加载器配置。继续？",
        "confirm_uninstall_msg": "从 {p} 卸载 ER Echo？\n\n会删除装进去的文件，并把改过的配置恢复成备份版本。",
        "install_done_title": "安装完成",
        "install_done_msg": "{kind}\n装到：{plugin}\n角色档案：{n} 个\n\n启动：\n{launch}",
        "uninstall_done_title": "已卸载",
        "uninstall_done_msg": "删除了 {n} 个路径，恢复了 {m} 个配置文件。",
        "path_missing_msg": "先填游戏路径。",
        "log_no_target": "[i] 没自动找到游戏/Convergence 目录，手动填路径吧。",
        "log_found": "[i] 找到 {n} 个可安装目标：",
        "log_save": "[i] 存档：{p}（{why}）",
        "log_no_save2": "[i] 没自动找到存档：装完先用示例档案。",
        "log_install_start": "[..] 安装到 {p}",
        "log_install_done": "[done] 安装完成：{p}",
        "log_uninstall_start": "[..] 从 {p} 卸载",
        "log_restored": "[ok] 恢复 {p}",
        "log_removed": "[ok] 删除 {p}",
        "dump_tables": "导出参数表",
        "dumping": "导出参数表中…",
        "confirm_dump_msg": "现在让游戏导出参数表（装备/法术 id 全集）？\n\n需要游戏已经在运行（Convergence 或原版都行）。\n工具会在 127.0.0.1:7811 等 DLL 连上来，最多 25 秒。",
        "dump_done_title": "参数表已导出",
        "dump_done_msg": "写出 {n} 个文件到：\n{d}\n\n之后的「角色导出 / 安装」会用它们做装备 id 硬校验（混搭套装的角色也能通过）。",
        "log_dump_start": "[..] 导出参数表（游戏根目录：{p}）",
        "log_dump_file": "[ok] {p}（{n} 字节）",
    },
    "en": {
        "title": "ER Echo - Setup / Profiles",
        "save_label": "Save (ER0000*):",
        "auto": "Auto-detect",
        "browse": "Browse...",
        "scan": "Load save",
        "col_slot": "Slot",
        "col_name": "Name",
        "col_level": "Level",
        "col_runes": "Runes",
        "col_status": "Status",
        "col_spells": "Spells",
        "col_equip": "Equipment",
        "status_complete": "complete",
        "status_incomplete": "no face/gear",
        "out_label": "Output folder:",
        "export_sel": "Export selected",
        "export_all": "Export all",
        "open_dir": "Open folder",
        "ini_label": "er_echo.ini:",
        "ini_write": "Write profiles",
        "ini_hint_missing": "er_echo.ini not found (usually in mods\\ER-Echo\\)",
        "lang_label": "Language:",
        "ready": "Ready",
        "scanning": "Reading save...",
        "exporting": "Exporting...",
        "no_save": "Save not found",
        "no_rows": "Load the save first",
        "no_rows_msg": "Click \"Load save\" first.",
        "no_complete": "Nothing to export",
        "no_complete_msg": "The selected characters have no face/equipment data.",
        "done_title": "Export finished",
        "done_msg": "Wrote {n} file(s):\n{d}\n\nWrite them into er_echo.ini (profiles=) now?",
        "ini_done_title": "Config updated",
        "ini_done_msg": "Updated:\n{p}\n\nprofiles={v}\n\nBackup: {b}",
        "ini_fail_title": "Write failed",
        "ini_no_profiles": "Nothing exported yet - export first.",
        "ini_missing_msg": "er_echo.ini not found. Install the plugin or pick it manually.",
        "error_title": "Error",
        "log_hint": "Note: offline export; the game does not need to run and your save is not modified.",
        "log_ini_found": "[i] er_echo.ini: {p}",
        "log_ini_missing": "[i] er_echo.ini not found - you can pick it after exporting.",
        "log_equip_table": "[i] equip ids: {n}",
        "log_magic_table": "[i] magic ids: {n}",
        "log_no_equip": "[i] no er_echo_equip.json (weak validation only)",
        "log_no_magic": "[i] no er_echo_magic.json (range validation only)",
        "log_autosave": "Latest save selected automatically.",
        "log_nosave": "No save found automatically; please pick one.",
        "log_scan_start": "[..] parsing {p}",
        "log_slot": "  slot {s}: {n} lv{l}",
        "log_incomplete": "  (no face/gear)",
        "log_chars": "[chars] {n} character(s)",
        "log_export": "[..] exporting {n} to {d}",
        "log_written": "[ok] {p}",
        "log_export_done": "[done] wrote {n} profile(s) to {d}",
        "log_ini_written": "[ok] updated {p}: profiles={v}",
        "log_ini_backup": "[i] backup {p}",
        "row_count": "{n} character(s)",
        "lang_name": "English",
        "tab_setup": "Setup",
        "tab_export": "Profiles",
        "path_label": "Game path:",
        "detect": "Detect",
        "install": "Install",
        "uninstall": "Uninstall",
        "kind_empty": "Enter a path or click Detect:\nvanilla -> ...\\ELDEN RING\\Game; Convergence -> ...\\ConvergenceER",
        "kind_unknown_hint": "(no eldenring.exe and no me3\\Windows\\me3.exe here)",
        "save2_label": "Save (ER0000*):",
        "save2_hint": "empty = auto (prefers *.cnv save for Convergence)",
        "installing": "Installing...",
        "uninstalling": "Uninstalling...",
        "confirm_title": "Confirm install",
        "confirm_msg": "Target: {kind}\nFolder: {path}\n\nThis writes the mod files and patches the loader config (backups are made). Continue?",
        "confirm_uninstall_msg": "Uninstall ER Echo from {p}?\n\nInstalled files are removed and patched configs are restored from backups.",
        "install_done_title": "Installed",
        "install_done_msg": "{kind}\nInstalled to: {plugin}\nCharacter profiles: {n}\n\nLaunch with:\n{launch}",
        "uninstall_done_title": "Uninstalled",
        "uninstall_done_msg": "Removed {n} path(s), restored {m} config file(s).",
        "path_missing_msg": "Enter the game path first.",
        "log_no_target": "[i] No game / Convergence folder found automatically; type the path.",
        "log_found": "[i] {n} install target(s) found:",
        "log_save": "[i] save: {p} ({why})",
        "log_no_save2": "[i] no save found: the example profile is used until you export.",
        "log_install_start": "[..] installing to {p}",
        "log_install_done": "[done] installed: {p}",
        "log_uninstall_start": "[..] uninstalling from {p}",
        "log_restored": "[ok] restored {p}",
        "log_removed": "[ok] removed {p}",
        "dump_tables": "Dump id tables",
        "dumping": "Dumping id tables...",
        "confirm_dump_msg": "Let the running game dump its id tables (all weapon/armor/spell ids)?\n\nRequires the game to be running (Convergence or vanilla).\nThe tool listens on 127.0.0.1:7811 for up to 25 s.",
        "dump_done_title": "Id tables dumped",
        "dump_done_msg": "Wrote {n} file(s) to:\n{d}\n\nProfile export / install will now use them for strict id validation (mixed armor sets pass too).",
        "log_dump_start": "[..] dumping id tables (game root: {p})",
        "log_dump_file": "[ok] {p} ({n} bytes)",
    },
}


def system_lang() -> str:
    try:
        from PyQt5.QtCore import QLocale
        if QLocale.system().language() == QLocale.Chinese:
            return "zh"
    except Exception:
        pass
    return "en" if os.environ.get("LANG", "").lower().startswith("en") else "zh"


def settings_bool(value) -> bool:
    """QSettings 在 Windows 上可能把 bool 读回 "true"/"false" 字符串。"""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# ------------------------------------------------------------------ 核心封装

def scan_save(save: pathlib.Path, on_slot=None) -> list[dict]:
    entries = core.parse_bnd4(save)
    found: list[dict] = []
    for name, data in entries:
        if not name.startswith("USER_DATA") or len(data) < core.SLOT_SIZE:
            continue
        try:
            slot = int(name[len("USER_DATA"):])
        except ValueError:
            continue
        if slot >= 10:
            continue
        payload = data[0x10:]
        try:
            ch = core.char_from_slot(payload)
        except Exception:
            ch = None
        if ch is None:
            continue
        found.append({"slot": slot, "ch": ch, "payload": payload})
        if on_slot is not None:
            try:
                on_slot(slot, ch)
            except Exception:
                pass
    found.sort(key=lambda x: x["slot"])
    return found


def export_profiles(save: pathlib.Path, rows: list[dict], outdir: pathlib.Path) -> list[pathlib.Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[pathlib.Path] = []
    for row in rows:
        ch = row["ch"]
        if not ch.get("complete"):
            continue
        profile = core.build_profile(row["slot"], ch, row["payload"], source=save.parent.name)
        out = outdir / f"slot{row['slot']}_{core.sanitize(ch['name'])}.json"
        out.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(out)
    return written


def lookup_tables() -> dict:
    """返回 {'equip': name|None, 'magic': name|None}；文案由界面本地化。"""
    out = {"equip": None, "magic": None}
    eq = core.find_equip_tables()
    if eq is not None and core.load_equip_tables(eq):
        out["equip"] = eq.name
    mg = core.find_magic_table_path()
    if mg is not None and core.load_magic_table(mg):
        out["magic"] = mg.name
    return out


# ------------------------------------------------------------------ 路径

def _app_dirs() -> list[pathlib.Path]:
    dirs: list[pathlib.Path] = []
    if getattr(sys, "frozen", False):
        dirs.append(pathlib.Path(sys.executable).resolve().parent)
    dirs.append(_HERE)
    dirs.append(pathlib.Path.cwd())
    # 源码搬出游戏目录后，靠检测找已安装的插件（原版 mods\ER-Echo / Convergence er-echo）
    try:
        dirs.extend(setup_core.find_game_dirs())
        dirs.extend(setup_core.find_convergence_dirs())
    except Exception:  # noqa: BLE001 - 检测失败不影响导出
        pass
    return dirs


def default_out_dir() -> pathlib.Path:
    # 最可靠：er_echo.ini 同级的 profiles（插件布局 mods\ER-Echo\profiles）
    for ini in find_inis():
        cand = ini.parent / "profiles"
        if cand.is_dir():
            return cand.resolve()
    for d in _app_dirs():
        for rel in ("../profiles", "../../profiles", "../../mods/ER-Echo/profiles",
                    "../mods/ER-Echo/profiles"):
            p = (d / rel).resolve()
            if p.is_dir() and p.name == "profiles":
                return p
    return pathlib.Path.cwd() / "profiles"


def find_inis() -> list[pathlib.Path]:
    seen: list[pathlib.Path] = []
    for d in _app_dirs():
        for rel in ("er_echo.ini",
                    "../er_echo.ini",
                    "../../er_echo.ini",
                    "../../mods/ER-Echo/er_echo.ini",
                    "../mods/ER-Echo/er_echo.ini",
                    "mods/ER-Echo/er_echo.ini",
                    "er-echo/er_echo.ini"):
            p = (d / rel).resolve()
            if p.is_file() and p not in seen:
                seen.append(p)
    return seen


def game_root_for(ini: pathlib.Path) -> pathlib.Path | None:
    """插件布局 mods/ER-Echo/er_echo.ini → 游戏根目录。

    不在游戏目录里（例如 Convergence 的 `<Conv>\\er-echo\\er_echo.ini`，DLL 的 CWD 仍是
    Steam 的 Game 目录）时返回 None —— 这时 profiles 必须写绝对路径，否则会被解析到
    Game 根目录下。
    """
    p = ini.parent
    if p.name.lower() == "er-echo" and p.parent.name.lower() == "mods":
        root = p.parent.parent
    else:
        root = p
    if (root / "eldenring.exe").is_file() or (root / "modengine2_launcher.exe").is_file():
        return root
    return None


def ini_rel(path: pathlib.Path, game_root: pathlib.Path | None) -> str:
    if game_root is not None:
        try:
            return path.resolve().relative_to(game_root.resolve()).as_posix()
        except ValueError:
            pass
    return str(path.resolve()).replace("\\", "/")


def write_profiles(ini: pathlib.Path, profiles: list[pathlib.Path]) -> tuple[str, pathlib.Path]:
    """把 profiles= 写进 ini，返回 (写入值, 备份路径)。"""
    text = ini.read_text(encoding="utf-8-sig")
    root = game_root_for(ini)
    value = ",".join(ini_rel(p, root) for p in profiles)
    line = f"profiles={value}"
    backup = ini.with_name(ini.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(ini, backup)
    if re.search(r"(?m)^\s*profiles\s*=.*$", text):
        text = re.sub(r"(?m)^\s*profiles\s*=.*$", line, text)
    elif re.search(r"(?m)^\s*\[clone\]\s*$", text):
        text = re.sub(r"(?m)^(\s*\[clone\]\s*)$", r"\1\n" + line, text, count=1)
    else:
        text = text.rstrip() + "\n\n[clone]\n" + line + "\n"
    ini.write_text(text, encoding="utf-8")
    return value, backup


# ------------------------------------------------------------------ 自检/CLI

def selftest(out_path: str) -> int:
    try:
        save = core.pick_default_save()
    except SystemExit as exc:
        pathlib.Path(out_path).write_text(f"no save: {exc}\n", encoding="utf-8")
        return 2
    rows = scan_save(save)
    data = {"save": str(save), "count": len(rows),
            "chars": [{"slot": r["slot"], "name": r["ch"]["name"], "level": r["ch"]["level"],
                       "complete": r["ch"]["complete"]} for r in rows]}
    pathlib.Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if rows else 2


def cli_write_ini(ini: str, jsons: list[str]) -> int:
    value, backup = write_profiles(pathlib.Path(ini), [pathlib.Path(j) for j in jsons])
    print(f"profiles={value}")
    print(f"backup={backup}")
    return 0


def cli_paths(out_path: str) -> int:
    data = {
        "frozen": bool(getattr(sys, "frozen", False)),
        "exe": sys.executable,
        "inis": [str(p) for p in find_inis()],
        "out_dir": str(default_out_dir()),
    }
    pathlib.Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


# ------------------------------------------------------------------ GUI

def run_gui(start_lang: str | None = None) -> int:
    from PyQt5.QtCore import QSettings, Qt, QThread, QTimer, pyqtSignal
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import (
        QApplication, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
        QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
        QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    )

    settings = QSettings("ER-Echo", "ProfileExport")
    # GUI 默认英文。旧版只存了 lang（没有 lang_explicit），其中的 zh 可能只是当年的
    # 系统默认值；这种情况按新默认英文启动。用户真正从下拉框里选过的语言会带
    # lang_explicit=true，继续沿用。
    saved_lang = str(settings.value("lang", "") or "")
    lang_explicit = settings_bool(settings.value("lang_explicit", False))
    if start_lang:
        lang = start_lang
    elif lang_explicit and saved_lang:
        lang = saved_lang
    else:
        lang = "en"
    if lang == "auto":
        lang = system_lang()
    if lang not in STRINGS:
        lang = "en"

    class Worker(QThread):
        log = pyqtSignal(str)
        done = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, fn):
            super().__init__()
            self._fn = fn

        def run(self):
            try:
                self.done.emit(self._fn(self.log.emit))
            except SystemExit as exc:
                self.failed.emit(str(exc))
            except Exception:
                self.failed.emit(traceback.format_exc())

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.lang = lang
            self.rows: list[dict] = []
            self.written: list[pathlib.Path] = []
            self._worker = None
            self.current_target = None
            self._settings = settings
            self.resize(1020, 680)

            central = QWidget()
            self.setCentralWidget(central)
            outer = QVBoxLayout(central)
            root = QVBoxLayout()          # 导出页主体（下面所有 row 都加到这里）

            # 语言
            row0 = QHBoxLayout()
            self.lang_label = QLabel()
            row0.addWidget(self.lang_label)
            self.lang_box = QComboBox()
            self.lang_box.addItem("中文", "zh")
            self.lang_box.addItem("English", "en")
            self.lang_box.setCurrentIndex(0 if self.lang == "zh" else 1)
            self.lang_box.currentIndexChanged.connect(self.on_lang_changed)
            row0.addWidget(self.lang_box)
            row0.addStretch(1)
            outer.addLayout(row0)

            # 存档
            row1 = QHBoxLayout()
            self.save_label = QLabel()
            row1.addWidget(self.save_label)
            self.save_edit = QLineEdit()
            row1.addWidget(self.save_edit, 1)
            self.btn_auto = QPushButton()
            self.btn_auto.clicked.connect(self.auto_detect)
            row1.addWidget(self.btn_auto)
            self.btn_browse = QPushButton()
            self.btn_browse.clicked.connect(self.browse_save)
            row1.addWidget(self.btn_browse)
            self.btn_scan = QPushButton()
            self.btn_scan.setDefault(True)
            self.btn_scan.clicked.connect(self.scan)
            row1.addWidget(self.btn_scan)
            root.addLayout(row1)

            # 表格
            self.table = QTableWidget(0, 7)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setSelectionMode(QTableWidget.ExtendedSelection)
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.verticalHeader().setVisible(False)
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(6, QHeaderView.Stretch)
            for i in range(6):
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            root.addWidget(self.table, 1)

            # 输出目录
            row2 = QHBoxLayout()
            self.out_label = QLabel()
            row2.addWidget(self.out_label)
            self.out_edit = QLineEdit(str(default_out_dir()))
            row2.addWidget(self.out_edit, 1)
            self.btn_out = QPushButton()
            self.btn_out.clicked.connect(self.browse_out)
            row2.addWidget(self.btn_out)
            self.btn_export_sel = QPushButton()
            self.btn_export_sel.clicked.connect(lambda: self.export(True))
            row2.addWidget(self.btn_export_sel)
            self.btn_export_all = QPushButton()
            self.btn_export_all.clicked.connect(lambda: self.export(False))
            row2.addWidget(self.btn_export_all)
            self.btn_open = QPushButton()
            self.btn_open.clicked.connect(self.open_out)
            row2.addWidget(self.btn_open)
            root.addLayout(row2)

            # er_echo.ini
            row3 = QHBoxLayout()
            self.ini_label = QLabel()
            row3.addWidget(self.ini_label)
            self.ini_edit = QLineEdit()
            row3.addWidget(self.ini_edit, 1)
            self.btn_ini = QPushButton()
            self.btn_ini.clicked.connect(self.browse_ini)
            row3.addWidget(self.btn_ini)
            self.btn_write_ini = QPushButton()
            self.btn_write_ini.clicked.connect(self.write_ini_clicked)
            row3.addWidget(self.btn_write_ini)
            root.addLayout(row3)

            # 日志
            self.log_view = QPlainTextEdit()
            self.log_view.setReadOnly(True)
            self.log_view.setMaximumBlockCount(1000)
            self.log_view.setFont(QFont("Consolas", 9))
            self.log_view.setFixedHeight(150)
            root.addWidget(self.log_view, 0)

            # ---------------- 安装/配置页（输入游戏路径 -> 自动装好一切）
            self.setup_tab = QWidget()
            st = QVBoxLayout(self.setup_tab)

            srow1 = QHBoxLayout()
            self.path_label = QLabel()
            srow1.addWidget(self.path_label)
            self.path_edit = QLineEdit()
            self.path_edit.setPlaceholderText(
                r"...\ELDEN RING\Game   或   ...\Convergence3\ConvergenceER")
            self.path_edit.editingFinished.connect(self.update_kind)
            srow1.addWidget(self.path_edit, 1)
            self.btn_detect = QPushButton()
            self.btn_detect.clicked.connect(lambda: self.setup_detect())
            srow1.addWidget(self.btn_detect)
            self.btn_path = QPushButton()
            self.btn_path.clicked.connect(self.setup_browse)
            srow1.addWidget(self.btn_path)
            st.addLayout(srow1)

            self.kind_label = QLabel()
            self.kind_label.setWordWrap(True)
            self.kind_label.setMinimumHeight(48)
            st.addWidget(self.kind_label)

            srow2 = QHBoxLayout()
            self.save2_label = QLabel()
            srow2.addWidget(self.save2_label)
            self.save2_edit = QLineEdit()
            srow2.addWidget(self.save2_edit, 1)
            self.btn_save2 = QPushButton()
            self.btn_save2.clicked.connect(self.setup_pick_save)
            srow2.addWidget(self.btn_save2)
            st.addLayout(srow2)

            srow3 = QHBoxLayout()
            self.btn_install = QPushButton()
            self.btn_install.setDefault(True)
            self.btn_install.clicked.connect(self.setup_install)
            srow3.addWidget(self.btn_install)
            self.btn_uninstall = QPushButton()
            self.btn_uninstall.clicked.connect(self.setup_uninstall)
            srow3.addWidget(self.btn_uninstall)
            self.btn_dump = QPushButton()
            self.btn_dump.clicked.connect(self.setup_dump_tables)
            srow3.addWidget(self.btn_dump)
            srow3.addStretch(1)
            st.addLayout(srow3)

            self.setup_log_view = QPlainTextEdit()
            self.setup_log_view.setReadOnly(True)
            self.setup_log_view.setMaximumBlockCount(2000)
            self.setup_log_view.setFont(QFont("Consolas", 9))
            st.addWidget(self.setup_log_view, 1)

            self.tabs = QTabWidget()
            export_tab = QWidget()
            export_tab.setLayout(root)
            self.tabs.addTab(self.setup_tab, "")
            self.tabs.addTab(export_tab, "")
            outer.addWidget(self.tabs, 1)
            self.tabs.setCurrentIndex(0)

            self.statusBar()
            self.retranslate()

            # 用户改动 → 500ms 防抖写入 QSettings；关闭窗口时再强制写一次。
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._save_settings)
            self._connect_persistence()
            self._restore_window_state()

            tables = lookup_tables()
            self.log(self.t("log_equip_table").format(n=tables["equip"]) if tables["equip"]
                     else self.t("log_no_equip"))
            self.log(self.t("log_magic_table").format(n=tables["magic"]) if tables["magic"]
                     else self.t("log_no_magic"))
            self._restore_settings()

        # ---------------- 持久化（QSettings / 注册表）
        def _saved(self, key: str, default: str = "") -> str:
            value = self._settings.value(key, default)
            return default if value is None else str(value)

        def _saved_int(self, key: str, default: int = 0) -> int:
            try:
                return int(self._settings.value(key, default))
            except (TypeError, ValueError):
                return default

        def _schedule_save(self, *_args):
            if getattr(self, "_save_timer", None) is not None:
                self._save_timer.start(500)

        def _save_settings(self):
            self._settings.setValue("lang", self.lang)
            self._settings.setValue("save_path", self.save_edit.text().strip())
            self._settings.setValue("out_dir", self.out_edit.text().strip())
            self._settings.setValue("ini_path", self.ini_edit.text().strip())
            self._settings.setValue("setup_path", self.path_edit.text().strip())
            self._settings.setValue("setup_save", self.save2_edit.text().strip())
            self._settings.setValue("tab", self.tabs.currentIndex())
            self._settings.setValue("geometry", self.saveGeometry())
            self._settings.sync()

        def _connect_persistence(self):
            for edit in (self.save_edit, self.out_edit, self.ini_edit,
                         self.path_edit, self.save2_edit):
                edit.textChanged.connect(self._schedule_save)
            self.tabs.currentChanged.connect(self._schedule_save)

        def _restore_window_state(self):
            geometry = self._settings.value("geometry")
            if geometry is not None:
                try:
                    self.restoreGeometry(geometry)
                except TypeError:
                    pass
            self.tabs.setCurrentIndex(
                max(0, min(1, self._saved_int("tab", 0))))

        def _restore_settings(self):
            inis = find_inis()

            # 安装/配置页：上次的游戏路径 + 存档（没有才自动探测）。
            saved_path = self._saved("setup_path")
            if saved_path:
                self.path_edit.setText(saved_path)
                self.update_kind()
                saved_save2 = self._saved("setup_save")
                if saved_save2:
                    self.save2_edit.setText(saved_save2)
                elif self.current_target is not None and self.current_target.kind != setup_core.KIND_UNKNOWN:
                    self._auto_save_for(self.current_target.kind)
            else:
                self.setup_autostart()

            # 导出页：上次的 ini / 输出目录 / 存档路径。
            saved_ini = self._saved("ini_path")
            if saved_ini:
                self.ini_edit.setText(saved_ini)
                self.log(self.t("log_ini_found").format(p=saved_ini))
            elif inis:
                self.ini_edit.setText(str(inis[0]))
                self.log(self.t("log_ini_found").format(p=inis[0]))
            else:
                self.log(self.t("log_ini_missing"))

            self.out_edit.setText(self._saved("out_dir") or str(default_out_dir()))

            saved_save = self._saved("save_path")
            if saved_save:
                self.save_edit.setText(saved_save)
                if pathlib.Path(saved_save).is_file():
                    self.log(self.t("log_autosave"))
                    QTimer.singleShot(300, self.scan)
                else:
                    self.log(self.t("log_nosave"))
            else:
                try:
                    self.save_edit.setText(str(core.pick_default_save()))
                    self.log(self.t("log_autosave"))
                    QTimer.singleShot(300, self.scan)
                except SystemExit:
                    self.log(self.t("log_nosave"))
            self._update_ini_button()

        # ---------------- i18n
        def t(self, key: str) -> str:
            return STRINGS[self.lang].get(key, key)

        def on_lang_changed(self):
            self.lang = self.lang_box.currentData()
            self._settings.setValue("lang", self.lang)
            self._settings.setValue("lang_explicit", True)
            self.retranslate()
            self._schedule_save()

        def closeEvent(self, event):
            # 关闭前把当前所有输入框/页签/窗口位置落盘，避免下次回到默认值。
            self._save_settings()
            super().closeEvent(event)

        def retranslate(self):
            self.setWindowTitle(self.t("title"))
            self.lang_label.setText(self.t("lang_label"))
            self.tabs.setTabText(0, self.t("tab_setup"))
            self.tabs.setTabText(1, self.t("tab_export"))
            self.path_label.setText(self.t("path_label"))
            self.btn_detect.setText(self.t("detect"))
            self.btn_path.setText(self.t("browse"))
            self.btn_install.setText(self.t("install"))
            self.btn_uninstall.setText(self.t("uninstall"))
            self.btn_dump.setText(self.t("dump_tables"))
            self.save2_label.setText(self.t("save2_label"))
            self.btn_save2.setText(self.t("auto"))
            self.save2_edit.setPlaceholderText(self.t("save2_hint"))
            self.update_kind()
            self.save_label.setText(self.t("save_label"))
            self.btn_auto.setText(self.t("auto"))
            self.btn_browse.setText(self.t("browse"))
            self.btn_scan.setText(self.t("scan"))
            self.table.setHorizontalHeaderLabels([
                self.t("col_slot"), self.t("col_name"), self.t("col_level"), self.t("col_runes"),
                self.t("col_status"), self.t("col_spells"), self.t("col_equip")])
            self.out_label.setText(self.t("out_label"))
            self.btn_out.setText(self.t("browse"))
            self.btn_export_sel.setText(self.t("export_sel"))
            self.btn_export_all.setText(self.t("export_all"))
            self.btn_open.setText(self.t("open_dir"))
            self.ini_label.setText(self.t("ini_label"))
            self.btn_ini.setText(self.t("browse"))
            self.btn_write_ini.setText(self.t("ini_write"))
            self.statusBar().showMessage(self.t("ready"))
            self._refresh_table()

        def _refresh_table(self):
            if not self.rows:
                return
            for i, r in enumerate(self.rows):
                if self.table.rowCount() <= i:
                    continue
                ch = r["ch"]
                status = self.t("status_complete") if ch.get("complete") else self.t("status_incomplete")
                item = self.table.item(i, 4)
                if item is not None:
                    item.setText(status)
                    item.setTextAlignment(Qt.AlignCenter)

        # ---------------- 工具
        def log(self, text: str):
            self.log_view.appendPlainText(text)

        def busy(self, on: bool, msg: str = ""):
            for b in (self.btn_scan, self.btn_export_sel, self.btn_export_all,
                      self.btn_install, self.btn_uninstall, self.btn_detect, self.btn_dump):
                b.setEnabled(not on)
            if not on:
                self.update_kind()
            self._update_ini_button()
            self.statusBar().showMessage(msg or self.t("ready"))

        def run_worker(self, fn, on_done):
            self._worker = Worker(fn)
            self._worker.log.connect(self.log)
            self._worker.failed.connect(self.on_failed)
            self._worker.done.connect(lambda r: (self.busy(False), on_done(r)))
            self._worker.start()

        def on_failed(self, msg: str):
            self.busy(False)
            self.log("[error] " + msg.strip().splitlines()[-1])
            QMessageBox.critical(self, self.t("error_title"), msg[-1500:])

        def _update_ini_button(self):
            ok = bool(self.ini_edit.text().strip()) and bool(self.written)
            self.btn_write_ini.setEnabled(ok)
            self.btn_write_ini.setToolTip("" if ok else self.t("ini_no_profiles"))

        # ---------------- 安装 / 配置
        def setup_log(self, text: str):
            self.setup_log_view.appendPlainText(text)

        def update_kind(self):
            text = self.path_edit.text().strip()
            if not text:
                self.current_target = None
                self.kind_label.setText(self.t("kind_empty"))
                self.btn_install.setEnabled(False)
                self.btn_uninstall.setEnabled(False)
                return
            try:
                target = setup_core.probe(text)
            except Exception as exc:  # noqa: BLE001
                self.kind_label.setText(str(exc))
                return
            self.current_target = target
            if target.kind == setup_core.KIND_UNKNOWN:
                self.kind_label.setText(target.describe() + "\n" + self.t("kind_unknown_hint"))
                self.btn_install.setEnabled(False)
                self.btn_uninstall.setEnabled(False)
            else:
                self.kind_label.setText(target.describe())
                self.btn_install.setEnabled(True)
                self.btn_uninstall.setEnabled(True)

        def setup_autostart(self):
            games = setup_core.find_game_dirs()
            convs = setup_core.find_convergence_dirs()
            if not games and not convs:
                self.setup_log(self.t("log_no_target"))
                self.update_kind()
                return
            self.setup_detect(quiet=True)

        def setup_detect(self, quiet: bool = False):
            games = setup_core.find_game_dirs()
            convs = setup_core.find_convergence_dirs()
            cands = [(setup_core.KIND_ME2, g) for g in games] + \
                    [(setup_core.KIND_ME3, c) for c in convs]
            if not cands:
                self.setup_log(self.t("log_no_target"))
                if not quiet:
                    QMessageBox.warning(self, self.t("detect"), self.t("log_no_target"))
                return
            self.setup_log(self.t("log_found").format(n=len(cands)))
            for kind, p in cands:
                self.setup_log(f"  [{setup_core.KIND_LABEL[kind]}] {p}")
            kind, path = cands[0]
            self.path_edit.setText(str(path))
            self.update_kind()
            self._auto_save_for(kind)

        def _auto_save_for(self, kind: str):
            save, why = setup_core.pick_save(kind, None)
            if save is not None:
                self.save2_edit.setText(str(save))
                self.setup_log(self.t("log_save").format(p=save, why=why))
            else:
                self.setup_log(self.t("log_no_save2"))

        def setup_browse(self):
            start = self.path_edit.text().strip() or str(pathlib.Path.home())
            path = QFileDialog.getExistingDirectory(self, self.t("path_label"), start)
            if path:
                self.path_edit.setText(path)
                self.update_kind()

        def setup_pick_save(self):
            path, _ = QFileDialog.getOpenFileName(
                self, self.t("save2_label"),
                self.save2_edit.text() or str(pathlib.Path.home()),
                "Elden Ring save (ER0000*);;All files (*.*)")
            if path:
                self.save2_edit.setText(path)

        def setup_install(self):
            text = self.path_edit.text().strip()
            if not text:
                QMessageBox.warning(self, self.t("install"), self.t("path_missing_msg"))
                return
            target = setup_core.probe(text)
            if target.kind == setup_core.KIND_UNKNOWN:
                QMessageBox.warning(self, self.t("install"), target.describe())
                return
            answer = QMessageBox.question(
                self, self.t("confirm_title"),
                self.t("confirm_msg").format(
                    kind=setup_core.KIND_LABEL[target.kind], path=target.root),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer != QMessageBox.Yes:
                return
            save = self.save2_edit.text().strip() or None
            self.busy(True, self.t("installing"))
            self.setup_log(self.t("log_install_start").format(p=target.root))

            def fn(log):
                return setup_core.install(text, save, log=log)

            self.run_worker(fn, self.on_installed)

        def on_installed(self, res: dict):
            self.setup_log(self.t("log_install_done").format(p=res["plugin"]))
            for c in res.get("changes") or []:
                self.setup_log("  + " + str(c))
            profiles = res.get("profiles") or []
            for p in profiles:
                self.setup_log("  profile: " + str(p))
            self.ini_edit.setText(res.get("ini", ""))
            self.out_edit.setText(str(pathlib.Path(res["plugin"]) / "profiles"))
            self.written = []
            self._update_ini_button()
            QMessageBox.information(
                self, self.t("install_done_title"),
                self.t("install_done_msg").format(
                    kind=res.get("kind_label", ""), plugin=res["plugin"],
                    launch=res.get("launch", ""), n=len(profiles)))

        def setup_dump_tables(self):
            """让运行中的游戏导出参数 id 表（装备/法术），导出器随后就能做硬校验。"""
            text = self.path_edit.text().strip()
            game = None
            if text:
                target = setup_core.probe(text)
                if target.kind == setup_core.KIND_ME2:
                    game = target.root
                elif target.kind == setup_core.KIND_ME3:
                    game = target.game_dir
            if game is None:
                games = setup_core.find_game_dirs()
                game = games[0] if games else None
            answer = QMessageBox.question(
                self, self.t("dump_tables"), self.t("confirm_dump_msg"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            self.busy(True, self.t("dumping"))
            self.setup_log(self.t("log_dump_start").format(p=game or "(未知)"))

            def fn(log):
                return setup_core.dump_tables(game, log=log)

            self.run_worker(fn, self.on_dumped)

        def on_dumped(self, res: dict):
            files = res.get("files") or []
            errors = res.get("errors") or []
            for f in files:
                self.setup_log(self.t("log_dump_file").format(p=f.get("path"), n=f.get("size")))
            for e in errors:
                self.setup_log("[!] " + str(e))
            if errors and not files:
                QMessageBox.critical(self, self.t("dump_tables"), "\n".join(map(str, errors))[-1200:])
                return
            QMessageBox.information(
                self, self.t("dump_done_title"),
                self.t("dump_done_msg").format(n=len(files), d=pathlib.Path(files[0]["path"]).parent))

        def setup_uninstall(self):
            text = self.path_edit.text().strip()
            if not text:
                QMessageBox.warning(self, self.t("uninstall"), self.t("path_missing_msg"))
                return
            target = setup_core.probe(text)
            if target.kind == setup_core.KIND_UNKNOWN:
                QMessageBox.warning(self, self.t("uninstall"), target.describe())
                return
            answer = QMessageBox.question(
                self, self.t("uninstall"), self.t("confirm_uninstall_msg").format(p=target.root),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            self.busy(True, self.t("uninstalling"))
            self.setup_log(self.t("log_uninstall_start").format(p=target.root))

            def fn(log):
                return setup_core.uninstall(text, log=log)

            self.run_worker(fn, self.on_uninstalled)

        def on_uninstalled(self, res: dict):
            for p in res.get("restored") or []:
                self.setup_log(self.t("log_restored").format(p=p))
            for p in res.get("removed") or []:
                self.setup_log(self.t("log_removed").format(p=p))
            QMessageBox.information(
                self, self.t("uninstall_done_title"),
                self.t("uninstall_done_msg").format(
                    n=len(res.get("removed") or []), m=len(res.get("restored") or [])))

        # ---------------- 选择
        def auto_detect(self):
            try:
                self.save_edit.setText(str(core.pick_default_save()))
                self.log(self.t("log_autosave"))
            except SystemExit as exc:
                QMessageBox.warning(self, self.t("no_save"), str(exc))

        def browse_save(self):
            path, _ = QFileDialog.getOpenFileName(
                self, self.t("save_label"), self.save_edit.text() or str(pathlib.Path.home()),
                "Elden Ring save (ER0000*);;All files (*.*)")
            if path:
                self.save_edit.setText(path)

        def browse_out(self):
            path = QFileDialog.getExistingDirectory(self, self.t("out_label"), self.out_edit.text())
            if path:
                self.out_edit.setText(path)

        def browse_ini(self):
            path, _ = QFileDialog.getOpenFileName(
                self, self.t("ini_label"), self.ini_edit.text() or str(pathlib.Path.cwd()),
                "er_echo.ini (er_echo.ini);;All files (*.*)")
            if path:
                self.ini_edit.setText(path)
                self._update_ini_button()

        def open_out(self):
            out = pathlib.Path(self.out_edit.text())
            out.mkdir(parents=True, exist_ok=True)
            os.startfile(str(out))  # noqa: S606

        # ---------------- 读取
        def scan(self):
            text = self.save_edit.text().strip()
            if not text:
                return
            save = pathlib.Path(text)
            if not save.is_file():
                QMessageBox.warning(self, self.t("no_save"), str(save))
                return
            self.busy(True, self.t("scanning"))
            self.log(self.t("log_scan_start").format(p=save))

            def fn(log):
                rows = scan_save(
                    save, on_slot=lambda slot, ch: log(
                        self.t("log_slot").format(s=slot, n=ch["name"], l=ch["level"])
                        + ("" if ch.get("complete") else self.t("log_incomplete"))))
                log(self.t("log_chars").format(n=len(rows)))
                return rows

            self.run_worker(fn, self.on_scanned)

        def on_scanned(self, rows):
            self.rows = rows
            self.table.setRowCount(0)
            for r in rows:
                ch = r["ch"]
                i = self.table.rowCount()
                self.table.insertRow(i)
                spells = [v for v in (ch.get("magic") or []) if v != -1]
                eq = ch.get("equip") or []
                weapon = next((hex(v) for v in eq[0:6] if v not in (-1, 0, None)), "-")
                armor = next((hex(v) for v in eq[12:16] if v not in (-1, 0, None)), "-")
                status = self.t("status_complete") if ch.get("complete") else self.t("status_incomplete")
                cells = [str(r["slot"]), ch["name"], str(ch["level"]), str(ch["runes"]),
                         status, str(len(spells)) if spells else "-", f"{weapon} / {armor}"]
                for c, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    if c in (0, 2, 3, 4, 5):
                        item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(i, c, item)
            self.statusBar().showMessage(self.t("row_count").format(n=len(rows)))

        # ---------------- 导出
        def export(self, selected: bool):
            text = self.save_edit.text().strip()
            save = pathlib.Path(text) if text else pathlib.Path()
            if not text or not save.is_file():
                QMessageBox.warning(self, self.t("no_save"), text)
                return
            if not self.rows:
                QMessageBox.information(self, self.t("no_rows"), self.t("no_rows_msg"))
                return
            if selected:
                idxs = sorted({i.row() for i in self.table.selectionModel().selectedRows()})
                rows = [self.rows[i] for i in idxs if i < len(self.rows)]
            else:
                rows = list(self.rows)
            rows = [r for r in rows if r["ch"].get("complete")]
            if not rows:
                QMessageBox.warning(self, self.t("no_complete"), self.t("no_complete_msg"))
                return
            outdir = pathlib.Path(self.out_edit.text().strip() or default_out_dir())
            self.busy(True, self.t("exporting"))
            self.log(self.t("log_export").format(n=len(rows), d=outdir))

            def fn(log):
                written = export_profiles(save, rows, outdir)
                for p in written:
                    log(self.t("log_written").format(p=p))
                log(self.t("log_export_done").format(n=len(written), d=outdir))
                return written

            self.run_worker(fn, lambda w: self.on_exported(w, outdir))

        def on_exported(self, written, outdir):
            self.written = written
            self._update_ini_button()
            if not written:
                return
            answer = QMessageBox.question(
                self, self.t("done_title"),
                self.t("done_msg").format(n=len(written), d=outdir),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                self.write_ini_clicked()

        # ---------------- 写 ini
        def write_ini_clicked(self):
            ini = pathlib.Path(self.ini_edit.text().strip())
            if not ini.is_file():
                QMessageBox.warning(self, self.t("ini_fail_title"), self.t("ini_missing_msg"))
                return
            if not self.written:
                QMessageBox.information(self, self.t("ini_fail_title"), self.t("ini_no_profiles"))
                return
            try:
                value, backup = write_profiles(ini, self.written)
            except Exception as exc:
                QMessageBox.critical(self, self.t("ini_fail_title"), str(exc))
                return
            self.log(self.t("log_ini_written").format(p=ini, v=value))
            self.log(self.t("log_ini_backup").format(p=backup))
            QMessageBox.information(
                self, self.t("ini_done_title"),
                self.t("ini_done_msg").format(p=ini, v=value, b=backup))

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    return app.exec_()


# ------------------------------------------------------------------ 入口

def _crash_log(exc: BaseException) -> pathlib.Path:
    base = pathlib.Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else _HERE
    try:
        path = base / ("gui-crash-" + time.strftime("%Y%m%d-%H%M%S") + ".log")
        path.write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        path = pathlib.Path(os.environ.get("TEMP", ".")) / "er-echo-gui-crash.log"
        path.write_text(traceback.format_exc(), encoding="utf-8")
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--selftest":
        out = args[1] if len(args) > 1 else "selftest.json"
        raise SystemExit(selftest(out))
    if args and args[0] == "--selftest-setup":
        out = args[1] if len(args) > 1 else "selftest-setup.json"
        raise SystemExit(setup_core.selftest(out))
    if args and args[0] == "--dump-tables":
        game = None
        if len(args) > 1:
            target = setup_core.probe(args[1])
            game = target.game_dir or (target.root if target.kind == setup_core.KIND_ME2 else None)
        res = setup_core.dump_tables(game, log=print)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        raise SystemExit(0 if not res["errors"] else 1)
    if args and args[0] == "--install":
        path = args[1] if len(args) > 1 else ""
        save = args[2] if len(args) > 2 else None
        print(json.dumps(setup_core.install(path, save), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if args and args[0] == "--write-ini":
        raise SystemExit(cli_write_ini(args[1], args[2:]))
    if args and args[0] == "--paths":
        raise SystemExit(cli_paths(args[1]))
    start = None
    if "--lang" in args:
        i = args.index("--lang")
        if i + 1 < len(args):
            start = args[i + 1]
    try:
        raise SystemExit(run_gui(start))
    except SystemExit:
        raise
    except BaseException:
        log = _crash_log(sys.exc_info()[1])
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "ER Echo", f"Startup failed. Log: {log}")
        except Exception:
            pass
        raise
