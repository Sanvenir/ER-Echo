#!/usr/bin/env python3
"""ER Echo 存档导出工具（PySide6 / Qt6，中英双语）。

功能：
  * 选存档 → 列出 0–9 号槽角色 → 多选导出 profile.json
  * 直接把 profiles= 写进 er_echo.ini（自动备份，不用手改配置）
  * 安装页可装/卸插件、导出参数表、一键启动游戏
  * 安装器界面中文 / English 切换（默认英文）；「游戏内菜单语言」是另一个下拉框，
    写进 er_echo.ini 的 [i18n] language=（默认 game = 跟随游戏文本语言）
  * 界面语言 / 游戏路径 / 存档 / 输出目录 / ini 路径 / 菜单语言都会记住

命令行：
    profile_export_gui.py                     # 打开窗口（默认英文）
    profile_export_gui.py --lang en           # 以英文启动
    profile_export_gui.py --lang auto         # 跟随系统语言启动
    profile_export_gui.py --selftest OUT      # 不开窗口，扫描默认存档并写结果
    profile_export_gui.py --write-ini INI JSON...   # 不开窗口，写 profiles=
    profile_export_gui.py --launch [PATH] [--admin] [--dry-run] [--me3 PATH]
                                               一键启动（原版 ME2/me3、Convergence me3）
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
import webbrowser

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
        "lang_label": "安装器界面语言：",
        "menu_lang_label": "游戏内菜单语言：",
        "menu_lang_hint": "推荐「跟随游戏文本」：自动和游戏当前文本语言一致（不会出现方块）。改完立即写进 er_echo.ini，重启游戏生效。",
        "menu_lang_game": "跟随游戏文本（推荐）",
        "menu_lang_os": "跟随 Windows 显示语言",
        "menu_lang_no_ini": "[i] 还没装 ER Echo：菜单语言先记下，点「一键安装」时会写进 er_echo.ini。",
        "log_setup_path_stale": "[i] 上次记录的游戏路径不可用（{p}），已自动重新检测。",
        "log_permission_hint": "[!] 没有写权限：游戏装在 Program Files 下时，请关掉安装器，右键 ER-Echo-Setup.exe →「以管理员身份运行」再试。",
        "menu_lang_denied_title": "没有写入权限",
        "menu_lang_denied_msg": "写入失败：\n{p}\n\n{e}\n\n游戏装在 Program Files 下时，安装器没有管理员权限就改不了这里的文件。\n可以点「以管理员身份写入」（会弹 UAC），或者手动改 er_echo.ini 的 [i18n] language=。\n\n如果上面这个路径不是你的游戏目录（例如在 Temp 里），先关掉本窗口重开，它会重新检测。",
        "menu_lang_retry_admin": "以管理员身份写入",
        "menu_lang_admin_started": "[i] 已请求管理员权限：UAC 允许后会写入 {p}，然后重启游戏生效。",
        "menu_lang_admin_failed": "[!] 提权写入没有启动（UAC 被拒绝或系统限制）：{e}",
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
        "path_hint": r"...\ELDEN RING\Game   或   ...\Convergence3\ConvergenceER",
        "unknown_short": "未知",
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
        "confirm_msg": "目标：{kind}\n加载器：{loader}\n目录：{path}\n\n会写入 mod 文件，并自动备份、修改加载器配置。继续？",
        "confirm_uninstall_msg": "从 {p} 卸载 ER Echo？\n\n会删除装进去的文件，并把改过的配置恢复成备份版本。",
        "install_done_title": "安装完成",
        "install_done_msg": "{kind}\n加载器：{loader}\n装到：{plugin}\n角色档案：{n} 个\n\n手动启动：\n{launch}",
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
        "launch": "一键启动游戏",
        "launch_admin": "以管理员身份启动（原版 10 秒闪退时用）",
        "launch_hint_empty": "一键启动：填好上面的游戏路径后，这里会显示用哪个启动器。",
        "launch_hint_me2": "一键启动：原版 · Mod Engine 2 → {p}",
        "launch_hint_me3": "一键启动：Convergence · me3 → {p}{seamless}",
        "launch_hint_me3_vanilla": "一键启动：原版 · me3 → {p}",
        "launch_seamless": "（无缝联机）",
        "launch_hint_blocked": "还不能启动：{why}",
        "launching": "启动中…",
        "launch_done_title": "已启动",
        "launch_done_msg": "已发出启动命令：\n{cmd}\n\n如果游戏窗口没出现，看游戏根目录的 er_echo.log 和 modengine2\\logs。",
        "launch_failed_title": "启动失败",
        "launch_running_msg": "eldenring.exe 已经在运行。\n\n再启动一份会失败或开出第二个进程。先关掉当前游戏再启动？",
        "launch_now_ask": "现在启动游戏？",
        "log_launch_start": "[..] 启动（{kind}）：{p}",
        "log_launch_done": "[ok] 已发出启动命令",
        "log_launch_admin": "[i] 提权启动：UAC 允许后游戏才会出现。",
        "loader_empty": "加载器：先填游戏路径。",
        "loader_title": "加载器：",
        "loader_me2_ok": "加载器：Mod Engine 2 已安装",
        "loader_me2_missing": "加载器：未检测到 Mod Engine 2 —— 原版启动前需要先安装（点「加载器安装步骤…」）",
        "loader_me3_ok": "加载器：me3 已随 Convergence 安装",
        "loader_unknown": "加载器：路径未识别，先填游戏根目录。",
        "loader_auto": "自动（推荐）",
        "loader_opt_me2": "Mod Engine 2",
        "loader_opt_me3": "me3（独立安装）",
        "loader_me3_path": "me3.exe：",
        "loader_me3_hint": "留空自动查找（PATH / 注册表 / 常见目录），也可以点「浏览…」指定",
        "loader_will_ok": "加载器：{loader} 已就绪{p}",
        "loader_will_missing": "加载器：{loader} 未找到 —— 先安装，或点「浏览…」指定 me3.exe",
        "loader_installed_suffix": "｜当前安装：{loader}",
        "loader_switch_hint": "（点「一键安装」切换）",
        "loader_conv_ok": "加载器：Convergence 自带的 me3（{p}）",
        "loader_path_paren": "（{p}）",
        "loader_auto_note": "自动 = 已装 ME2 用 ME2，否则用 me3",
        "loader_get_me2": "获取 Mod Engine 2",
        "loader_get_me3": "获取 me3",
        "loader_guide": "加载器安装步骤…",
        "loader_guide_title": "安装 Mod Engine 2 / me3",
        "loader_open_me2": "打开 ME2 发布页",
        "loader_open_me3": "打开 me3 发布页",
        "loader_open_conv": "打开 Convergence 页",
        "loader_missing_title": "还没装加载器",
        "loader_missing_msg": "没有检测到 {loader}。\n\n安装器只装 ER Echo 文件，不包含也不分发加载器（许可证原因）。要打开官方发布页吗？原版用 ME2；Convergence 自带 me3，独立的 me3 可以用另一个按钮打开。\n\n装好加载器后回到本页重新点「一键安装」。",
        "loader_missing_launch_msg": "启动需要 {loader}，但没有检测到。\n\n打开官方发布页下载，装好后重新点「一键启动游戏」；也可以先看「加载器安装步骤…」。",
        "loader_open_page": "打开下载页",
        "install_anyway": "仍然安装文件",
        "cancel": "取消",
        "log_open_url": "[i] 已打开 {u}",
        "log_loader_missing": "[!] 没检测到 {loader}：装好加载器再启动。",
        "loader_guide_html": """<h2>安装加载器（Mod Engine 2 / me3）</h2>
<p>ER Echo 只是被加载器注入的 DLL。<b>本安装器不包含、也不分发</b> Mod Engine 2、me3
或 Convergence 的任何文件；请从下面的官方页面下载，并遵守各自的许可证。</p>
<p>三种组合都支持「一键安装 + 一键启动」：<b>原版 + ME2</b>、<b>原版 + me3</b>、
<b>Convergence + 自带 me3</b>。</p>
<h3>方案 A：原版 + Mod Engine 2</h3>
<ol>
<li>打开 <a href="{me2_url}">Mod Engine 2 发布页</a>，在 Assets 里下载最新的
<code>ModEngine-*-win64.zip</code>。ME2 已停止更新（仓库已归档），但仍是原版最省事的加载器。</li>
<li>解压后，把 <code>modengine2_launcher.exe</code> 和 <code>modengine2\\</code> 文件夹放到
游戏根目录，和 <code>eldenring.exe</code> 同级。</li>
<li>回到本工具：游戏路径填 <code>...\\ELDEN RING\\Game</code>，加载器选「Mod Engine 2」或「自动」，
点「自动检测」→「一键安装」。</li>
<li>装完点「一键启动游戏」；如果启动后约 10 秒闪退，勾上「以管理员身份启动」再试。</li>
</ol>
<h3>方案 B：原版 + me3（独立安装）</h3>
<ol>
<li>打开 <a href="{me3_url}">me3 发布页</a>，下载 <code>me3_installer.exe</code> 按向导安装；
或下载便携版解压到本地目录（不要放 OneDrive）。装好后 <code>me3 info</code> 能跑即可。</li>
<li>回到本工具：加载器选「me3（独立安装）」；<code>me3.exe</code> 路径留空会自动查找
（PATH / 注册表 / 常见目录），找不到就点「浏览…」指定（例如
<code>D:\\Games\\me3\\bin\\me3.exe</code>）。</li>
<li>点「一键安装」：会在游戏根目录生成 <code>er-echo.me3</code>（<code>[[natives]]</code>
指向 <code>mods\\ER-Echo\\er_echo.dll</code>，<code>[[package]]</code> 挂赐福菜单 ESD），
并记录这次用 me3。</li>
<li>点「一键启动游戏」：执行
<code>me3 launch --auto-detect -p .\\er-echo.me3</code>；装好后也可以手动跑这条命令。</li>
</ol>
<h3>方案 C：Convergence 3.x（自带 me3）</h3>
<ol>
<li>先装 <b>The Convergence</b>：整合包自带 <code>me3\\Windows\\me3.exe</code>。
发布页：<a href="{conv_url}">The Convergence</a>。</li>
<li>游戏路径填 Convergence 根目录（含 <code>me3\\Windows\\me3.exe</code> 和 <code>mod\\</code>）；
加载器会自动固定为 me3 →「一键安装」→「一键启动游戏」。有 SeamlessCoop 时会自动选无缝配置。</li>
</ol>
<h3>合规与安全</h3>
<ul>
<li>安装器不打包、不分发 ME2 / me3 / Convergence 的文件，只写 ER Echo 自己的文件并追加
配置引用（全部带备份）。</li>
<li>只离线使用；带 mod 存档上线有被隔离 / soft-ban 的风险。</li>
</ul>""",
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
        "lang_label": "Installer language:",
        "menu_lang_label": "In-game menu language:",
        "menu_lang_hint": "\"Follow game text\" is recommended: the menu matches the language the game itself is using (no missing-glyph boxes). Changes are written to er_echo.ini immediately; restart the game to apply.",
        "menu_lang_game": "Follow game text (recommended)",
        "menu_lang_os": "Follow Windows display language",
        "menu_lang_no_ini": "[i] ER Echo is not installed yet: the menu language is remembered and written to er_echo.ini when you click Install.",
        "log_setup_path_stale": "[i] The game path remembered last time is no longer usable ({p}); auto-detection was re-run.",
        "log_permission_hint": "[!] Permission denied: when the game is under Program Files, close the installer, right-click ER-Echo-Setup.exe and choose \"Run as administrator\".",
        "menu_lang_denied_title": "Permission denied",
        "menu_lang_denied_msg": "Could not write:\n{p}\n\n{e}\n\nWhen the game is installed under Program Files, the installer needs administrator rights to change this file.\nClick \"Write as administrator\" (UAC prompt), or edit [i18n] language= in er_echo.ini manually.\n\nIf the path above is not your game folder (e.g. it points into Temp), close and reopen the installer so it auto-detects the game again.",
        "menu_lang_retry_admin": "Write as administrator",
        "menu_lang_admin_started": "[i] Requested administrator rights: after allowing UAC the language is written to {p}; restart the game to apply.",
        "menu_lang_admin_failed": "[!] Elevated write did not start (UAC denied or blocked): {e}",
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
        "path_hint": r"...\ELDEN RING\Game   or   ...\Convergence3\ConvergenceER",
        "unknown_short": "unknown",
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
        "confirm_msg": "Target: {kind}\nLoader: {loader}\nFolder: {path}\n\nThis writes the mod files and patches the loader config (backups are made). Continue?",
        "confirm_uninstall_msg": "Uninstall ER Echo from {p}?\n\nInstalled files are removed and patched configs are restored from backups.",
        "install_done_title": "Installed",
        "install_done_msg": "{kind}\nLoader: {loader}\nInstalled to: {plugin}\nCharacter profiles: {n}\n\nOr launch manually with:\n{launch}",
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
        "launch": "Launch game",
        "launch_admin": "Launch as administrator (vanilla 10-second crash workaround)",
        "launch_hint_empty": "One-click launch: enter the game path above to see which launcher is used.",
        "launch_hint_me2": "One-click launch: vanilla / Mod Engine 2 -> {p}",
        "launch_hint_me3": "One-click launch: Convergence / me3 -> {p}{seamless}",
        "launch_hint_me3_vanilla": "One-click launch: vanilla / me3 -> {p}",
        "launch_seamless": " (Seamless Coop)",
        "launch_hint_blocked": "Cannot launch yet: {why}",
        "launching": "Launching...",
        "launch_done_title": "Launched",
        "launch_done_msg": "Launch command sent:\n{cmd}\n\nIf no game window appears, check er_echo.log and modengine2\\logs in the game folder.",
        "launch_failed_title": "Launch failed",
        "launch_running_msg": "eldenring.exe is already running.\n\nStarting another copy will fail or spawn a second process. Close the current game first?",
        "launch_now_ask": "Launch the game now?",
        "log_launch_start": "[..] launching ({kind}): {p}",
        "log_launch_done": "[ok] launch command sent",
        "log_launch_admin": "[i] elevated launch: accept the UAC prompt for the game to appear.",
        "loader_empty": "Loader: enter the game path first.",
        "loader_title": "Loader:",
        "loader_me2_ok": "Loader: Mod Engine 2 is installed.",
        "loader_me2_missing": "Loader: Mod Engine 2 not found - vanilla needs it before launching (see \"Loader install steps...\").",
        "loader_me3_ok": "Loader: me3 is installed with Convergence.",
        "loader_unknown": "Loader: path not recognised - enter the game root folder.",
        "loader_auto": "Auto (recommended)",
        "loader_opt_me2": "Mod Engine 2",
        "loader_opt_me3": "me3 (standalone)",
        "loader_me3_path": "me3.exe:",
        "loader_me3_hint": "Empty = auto-detect (PATH / registry / common folders); click Browse to pick it",
        "loader_will_ok": "Loader: {loader} ready{p}",
        "loader_will_missing": "Loader: {loader} not found - install it, or click Browse to pick me3.exe",
        "loader_installed_suffix": " | currently installed: {loader}",
        "loader_switch_hint": " (click Install to switch)",
        "loader_conv_ok": "Loader: me3 bundled with Convergence ({p})",
        "loader_path_paren": " ({p})",
        "loader_auto_note": "Auto = ME2 when installed, otherwise me3",
        "loader_get_me2": "Get Mod Engine 2",
        "loader_get_me3": "Get me3",
        "loader_guide": "Loader install steps...",
        "loader_guide_title": "Install Mod Engine 2 / me3",
        "loader_open_me2": "Open ME2 releases",
        "loader_open_me3": "Open me3 releases",
        "loader_open_conv": "Open Convergence page",
        "loader_missing_title": "Mod loader not installed",
        "loader_missing_msg": "No {loader} detected.\n\nThis installer only writes ER Echo files; it does not bundle or redistribute the loader (licensing). Open the official release page? Vanilla uses ME2; Convergence ships me3, and a standalone me3 can be opened with the other button.\n\nAfter installing the loader, come back and click \"Install\" again.",
        "loader_missing_launch_msg": "Launching needs {loader}, but it was not found.\n\nDownload it from the official release page, then click \"Launch game\" again. See \"Loader install steps...\" for details.",
        "loader_open_page": "Open download page",
        "install_anyway": "Install files anyway",
        "cancel": "Cancel",
        "log_open_url": "[i] opened {u}",
        "log_loader_missing": "[!] {loader} not found - install the loader before launching.",
        "loader_guide_html": """<h2>Install the mod loader (Mod Engine 2 / me3)</h2>
<p>ER Echo is only a DLL injected by a mod loader. <b>This installer does not include or
redistribute</b> any Mod Engine 2, me3 or Convergence files; download them from the official
pages below and follow their licences.</p>
<p>All three setups are one-click: <b>vanilla + ME2</b>, <b>vanilla + me3</b>,
<b>Convergence + bundled me3</b>.</p>
<h3>Option A: vanilla + Mod Engine 2</h3>
<ol>
<li>Open the <a href="{me2_url}">Mod Engine 2 releases page</a> and download the latest
<code>ModEngine-*-win64.zip</code> from Assets. ME2 is discontinued (repository archived) but is
still the simplest loader for vanilla.</li>
<li>Extract <code>modengine2_launcher.exe</code> and the <code>modengine2\\</code> folder into the
game root, next to <code>eldenring.exe</code>.</li>
<li>Back in this tool: set the game path to <code>...\\ELDEN RING\\Game</code>, pick
"Mod Engine 2" or "Auto", click "Detect", then "Install".</li>
<li>Click "Launch game". If it crashes after ~10 s, tick "Launch as administrator".</li>
</ol>
<h3>Option B: vanilla + me3 (standalone)</h3>
<ol>
<li>Open the <a href="{me3_url}">me3 releases page</a>, download <code>me3_installer.exe</code> and
run the wizard; or extract the portable build into a local folder (not OneDrive). Verify
<code>me3 info</code> works.</li>
<li>Back in this tool: pick "me3 (standalone)"; leave the me3.exe field empty for auto-detection
(PATH / registry / common folders), or click "Browse..." and pick it (e.g.
<code>D:\\Games\\me3\\bin\\me3.exe</code>).</li>
<li>Click "Install": it writes <code>er-echo.me3</code> in the game root
(<code>[[natives]]</code> -> <code>mods\\ER-Echo\\er_echo.dll</code>,
<code>[[package]]</code> -> the grace-menu ESD) and records me3 as the loader.</li>
<li>Click "Launch game": it runs
<code>me3 launch --auto-detect -p .\\er-echo.me3</code>. The same command works from a terminal.</li>
</ol>
<h3>Option C: Convergence 3.x (bundled me3)</h3>
<ol>
<li>Install <b>The Convergence</b> first: the pack ships <code>me3\\Windows\\me3.exe</code>.
Page: <a href="{conv_url}">The Convergence</a>.</li>
<li>Set the path to the Convergence root (with <code>me3\\Windows\\me3.exe</code> and
<code>mod\\</code>). The loader is fixed to me3 -> "Install" -> "Launch game". A Seamless Coop
profile is picked automatically when present.</li>
</ol>
<h3>Licensing and safety</h3>
<ul>
<li>No ME2 / me3 / Convergence files are bundled or redistributed. The installer writes only
ER Echo files and appends references to configs you already have (with backups).</li>
<li>Offline only; taking a modded save online risks isolation / a soft ban.</li>
</ul>""",
    },
}


def system_lang() -> str:
    try:
        from PySide6.QtCore import QLocale
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


def _builtin_entries(text: str) -> list[str]:
    """现有 `profiles=` 行里的内置档案条目（`builtin_*.json`）。

    内置档案是随包发布的彩蛋/备用角色，用户导出自己的角色时只该**追加**、
    不该把它从名单里挤掉 —— 所以写 ini 前先把这些条目原样捡回来。
    """
    m = re.search(r"(?m)^\s*profiles\s*=(.*)$", text)
    if not m:
        return []
    kept: list[str] = []
    for part in m.group(1).split(","):
        part = part.strip().strip('"').strip("'")
        if part and core.is_builtin_profile(part) and part not in kept:
            kept.append(part)
    return kept


def write_profiles(ini: pathlib.Path, profiles: list[pathlib.Path]) -> tuple[str, pathlib.Path]:
    """把 profiles= 写进 ini，返回 (写入值, 备份路径)。内置档案条目会被保留。"""
    text = ini.read_text(encoding="utf-8-sig")
    root = game_root_for(ini)
    parts = [ini_rel(p, root) for p in profiles]
    for keep in _builtin_entries(text):
        if keep not in parts:
            parts.append(keep)
    value = ",".join(parts)
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
    from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal as pyqtSignal
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
        QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
        QPlainTextEdit, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
        QTextBrowser, QVBoxLayout, QWidget,
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
    # setup_core 的日志/状态/错误跟着界面语言走（英文界面里不留中文）
    setup_core.set_ui_lang(lang)

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

            # 加载器选择 + 状态 + 官方发布页（不打包 ME2/me3，只跳转引导）
            self.loader_title = QLabel()
            self.loader_box = QComboBox()
            self.loader_box.currentIndexChanged.connect(self.on_loader_changed)
            self.me3_path_label = QLabel()
            self.me3_edit = QLineEdit()
            self.me3_edit.editingFinished.connect(self.update_loader_state)
            self.btn_me3_browse = QPushButton()
            self.btn_me3_browse.clicked.connect(self.browse_me3)

            lrow0 = QHBoxLayout()
            lrow0.addWidget(self.loader_title)
            lrow0.addWidget(self.loader_box)
            lrow0.addSpacing(12)
            lrow0.addWidget(self.me3_path_label)
            lrow0.addWidget(self.me3_edit, 1)
            lrow0.addWidget(self.btn_me3_browse)
            st.addLayout(lrow0)

            self.loader_label = QLabel()
            self.loader_label.setWordWrap(True)
            st.addWidget(self.loader_label)

            # 游戏内菜单语言（和窗口顶部「安装器界面语言」是两件事，别混）
            mrow = QHBoxLayout()
            self.menu_lang_label = QLabel()
            self.menu_lang_box = QComboBox()
            # 条目在 retranslate() 里填（要按界面语言取显示名）
            self.menu_lang_box.currentIndexChanged.connect(self.on_menu_lang_changed)
            mrow.addWidget(self.menu_lang_label)
            mrow.addWidget(self.menu_lang_box)
            self.menu_lang_hint = QLabel()
            self.menu_lang_hint.setWordWrap(True)
            mrow.addWidget(self.menu_lang_hint, 1)
            st.addLayout(mrow)

            lrow = QHBoxLayout()
            self.btn_get_me2 = QPushButton()
            self.btn_get_me2.clicked.connect(lambda: self.open_loader_page("me2"))
            lrow.addWidget(self.btn_get_me2)
            self.btn_get_me3 = QPushButton()
            self.btn_get_me3.clicked.connect(lambda: self.open_loader_page("me3"))
            lrow.addWidget(self.btn_get_me3)
            self.btn_loader_guide = QPushButton()
            self.btn_loader_guide.clicked.connect(self.show_loader_guide)
            lrow.addWidget(self.btn_loader_guide)
            lrow.addStretch(1)
            st.addLayout(lrow)

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

            # 一键启动：原版走 ME2 的 launch-er-echo*.bat，Convergence 走 me3 + *.me3
            srow4 = QHBoxLayout()
            self.btn_launch = QPushButton()
            self.btn_launch.clicked.connect(self.setup_launch)
            srow4.addWidget(self.btn_launch)
            self.chk_admin = QCheckBox()
            self.chk_admin.toggled.connect(self.on_admin_toggled)
            srow4.addWidget(self.chk_admin)
            srow4.addStretch(1)
            st.addLayout(srow4)

            self.launch_label = QLabel()
            self.launch_label.setWordWrap(True)
            st.addWidget(self.launch_label)

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
            self._settings.setValue("menu_lang", self._menu_lang())
            self._settings.setValue("save_path", self.save_edit.text().strip())
            self._settings.setValue("out_dir", self.out_edit.text().strip())
            self._settings.setValue("ini_path", self.ini_edit.text().strip())
            # 只记住能识别出来的游戏目录：半截路径 / 临时目录 / 已删除的目录
            # 写进去会让下次启动拿着坏路径去改 ini（2026-11-23 实测踩过）。
            target = self.current_target
            if (target is not None
                    and target.kind != setup_core.KIND_UNKNOWN
                    and pathlib.Path(self.path_edit.text().strip()).is_dir()):
                self._settings.setValue("setup_path", self.path_edit.text().strip())
            self._settings.setValue("setup_path", self.path_edit.text().strip())
            self._settings.setValue("setup_save", self.save2_edit.text().strip())
            self._settings.setValue("launch_admin", self.chk_admin.isChecked())
            self._settings.setValue("loader", self._loader_choice())
            self._settings.setValue("me3_path", self.me3_edit.text().strip())
            self._settings.setValue("tab", self.tabs.currentIndex())
            self._settings.setValue("geometry", self.saveGeometry())
            self._settings.sync()

        def _connect_persistence(self):
            for edit in (self.save_edit, self.out_edit, self.ini_edit,
                         self.path_edit, self.save2_edit):
                edit.textChanged.connect(self._schedule_save)
            self.chk_admin.toggled.connect(self._schedule_save)
            self.loader_box.currentIndexChanged.connect(self._schedule_save)
            self.me3_edit.textChanged.connect(self._schedule_save)
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

            # 一键启动的提权选项（原版 10 秒闪退时才需要）
            self.chk_admin.setChecked(
                settings_bool(self._settings.value("launch_admin", False)))
            # 加载器选择 / 独立 me3 路径
            self._set_loader_choice(self._saved("loader") or "auto")
            self.me3_edit.setText(self._saved("me3_path"))

            # 安装/配置页：上次的游戏路径 + 存档（没有/失效才自动探测）。
            saved_path = self._saved("setup_path")
            usable = bool(saved_path) and pathlib.Path(saved_path).is_dir()
            if usable:
                self.path_edit.setText(saved_path)
                self.update_kind()
                usable = (self.current_target is not None
                          and self.current_target.kind != setup_core.KIND_UNKNOWN)
            if not usable:
                # 上次记录的是临时目录 / 已删除 / 换布局后的旧路径：别拿它去写 ini
                if saved_path:
                    self.setup_log(self.t("log_setup_path_stale").format(p=saved_path))
                self.path_edit.clear()
                self.setup_autostart()
            else:
                saved_save2 = self._saved("setup_save")
                if saved_save2 and pathlib.Path(saved_save2).is_file():
                    self.save2_edit.setText(saved_save2)
                elif self.current_target is not None:
                    self._auto_save_for(self.current_target.kind)

            # 游戏内菜单语言：已装的 ini 里写的是什么就以它为准（真实生效值），
            # 否则沿用上次在界面上选的。不要用信号触发写盘。
            ini_lang = None
            if self.current_target is not None:
                ini_lang = setup_core.ini_language(self.current_target.ini_path)
            self._set_menu_lang(ini_lang or self._saved("menu_lang") or "game",
                                notify=False)

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
            setup_core.set_ui_lang(self.lang)
            self._settings.setValue("lang", self.lang)
            self._settings.setValue("lang_explicit", True)
            self.retranslate()
            self._schedule_save()

        # ---------------- 游戏内菜单语言（写 er_echo.ini 的 [i18n] language）
        def _menu_lang(self) -> str:
            return setup_core.normalize_menu_language(self.menu_lang_box.currentData())

        def _populate_menu_lang_box(self):
            labels = {
                "game": self.t("menu_lang_game"),
                "auto": self.t("menu_lang_os"),
                "zh-CN": "简体中文",
                "zh-TW": "繁體中文",
                "en": "English",
                "ja": "日本語",
            }
            current = self.menu_lang_box.currentData()
            self.menu_lang_box.blockSignals(True)
            self.menu_lang_box.clear()
            for code in setup_core.MENU_LANGUAGES:
                self.menu_lang_box.addItem(labels.get(code, code), code)
            idx = self.menu_lang_box.findData(current) if current else -1
            self.menu_lang_box.setCurrentIndex(idx if idx >= 0 else 0)
            self.menu_lang_box.blockSignals(False)

        def _set_menu_lang(self, code: str, notify: bool = True):
            code = setup_core.normalize_menu_language(code)
            idx = self.menu_lang_box.findData(code)
            self.menu_lang_box.blockSignals(True)
            self.menu_lang_box.setCurrentIndex(idx if idx >= 0 else 0)
            self.menu_lang_box.blockSignals(False)
            self._settings.setValue("menu_lang", code)
            if notify:
                self.apply_menu_language(code)

        def on_menu_lang_changed(self):
            code = self._menu_lang()
            self._settings.setValue("menu_lang", code)
            self._schedule_save()
            self.apply_menu_language(code)

        def apply_menu_language(self, code: str) -> bool:
            """把菜单语言写进已装的 er_echo.ini：没装就只记住，安装时再写入。"""
            code = setup_core.normalize_menu_language(code)
            target = self.current_target
            if (target is None
                    or target.kind == setup_core.KIND_UNKNOWN
                    or not target.ini_path.is_file()
                    or not (target.plugin_dir / "er_echo.dll").is_file()):
                self.setup_log(self.t("menu_lang_no_ini"))
                return False
            try:
                return setup_core.apply_ini_language(
                    target.ini_path, code, log=self.setup_log)
            except OSError as exc:
                # Program Files 下没写权限（或文件只读）：别崩，给「以管理员身份写入」的出路
                self.setup_log(f"[!] {target.ini_path}: {exc}")
                self._offer_elevated_language_write(target.ini_path, code, exc)
                return False

        def _offer_elevated_language_write(self, ini: pathlib.Path, code: str,
                                           exc: OSError):
            """改 ini 被拒时，让用户选「以管理员身份写入」（UAC），或取消去手动改。"""
            box = QMessageBox(QMessageBox.Warning,
                              self.t("menu_lang_denied_title"),
                              self.t("menu_lang_denied_msg").format(p=ini, e=exc),
                              QMessageBox.NoButton, self)
            admin_btn = box.addButton(self.t("menu_lang_retry_admin"),
                                      QMessageBox.AcceptRole)
            box.addButton(self.t("cancel"), QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not admin_btn:
                return
            try:
                import ctypes
                if getattr(sys, "frozen", False):
                    exe = sys.executable
                    params = '--set-language "{}" {}'.format(ini, code)
                else:
                    exe = sys.executable
                    params = '"{}" --set-language "{}" {}'.format(
                        pathlib.Path(__file__).resolve(), ini, code)
                # SW_SHOWNORMAL = 1；返回值 > 32 才算启动成功（不是 UAC 结果）
                rc = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", exe, params, str(pathlib.Path(exe).parent), 1)
                if rc <= 32:
                    raise OSError(f"ShellExecuteW returned {rc}")
                self.setup_log(self.t("menu_lang_admin_started").format(p=ini))
            except Exception as exc2:  # noqa: BLE001 - 提权失败只影响这一个可选项
                self.setup_log(self.t("menu_lang_admin_failed").format(e=exc2))

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
            self.path_edit.setPlaceholderText(self.t("path_hint"))
            self.btn_detect.setText(self.t("detect"))
            self.btn_path.setText(self.t("browse"))
            self.btn_install.setText(self.t("install"))
            self.btn_uninstall.setText(self.t("uninstall"))
            self.btn_dump.setText(self.t("dump_tables"))
            self.save2_label.setText(self.t("save2_label"))
            self.btn_save2.setText(self.t("auto"))
            self.save2_edit.setPlaceholderText(self.t("save2_hint"))
            self.btn_launch.setText(self.t("launch"))
            self.chk_admin.setText(self.t("launch_admin"))
            self.btn_get_me2.setText(self.t("loader_get_me2"))
            self.btn_get_me3.setText(self.t("loader_get_me3"))
            self.btn_loader_guide.setText(self.t("loader_guide"))
            self.loader_title.setText(self.t("loader_title"))
            self.me3_path_label.setText(self.t("loader_me3_path"))
            self.me3_edit.setPlaceholderText(self.t("loader_me3_hint"))
            self.btn_me3_browse.setText(self.t("browse"))
            self.menu_lang_label.setText(self.t("menu_lang_label"))
            self.menu_lang_hint.setText(self.t("menu_lang_hint"))
            self._populate_menu_lang_box()
            self._populate_loader_box()
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
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---------------- 工具
        def log(self, text: str):
            self.log_view.appendPlainText(text)

        def busy(self, on: bool, msg: str = ""):
            for b in (self.btn_scan, self.btn_export_sel, self.btn_export_all,
                      self.btn_install, self.btn_uninstall, self.btn_detect, self.btn_dump,
                      self.btn_launch, self.chk_admin, self.btn_get_me2,
                      self.btn_get_me3, self.btn_loader_guide,
                      self.loader_box, self.me3_edit, self.btn_me3_browse,
                      self.menu_lang_box):
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
            if "Permission denied" in msg or "Errno 13" in msg:
                self.setup_log(self.t("log_permission_hint"))
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
                self.update_launch_state()
                self.update_loader_state()
                return
            try:
                target = setup_core.probe(text)
            except Exception as exc:  # noqa: BLE001
                self.kind_label.setText(str(exc))
                self.update_launch_state()
                self.update_loader_state()
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
            self.update_launch_state()
            self.update_loader_state()

        def _loader_choice(self) -> str:
            data = self.loader_box.currentData()
            return data if data in ("auto", "me2", "me3") else "auto"

        def _set_loader_choice(self, choice: str):
            idx = self.loader_box.findData(choice if choice in ("auto", "me2", "me3") else "auto")
            self.loader_box.blockSignals(True)
            self.loader_box.setCurrentIndex(max(0, idx))
            self.loader_box.blockSignals(False)

        def _populate_loader_box(self):
            current = self.loader_box.currentData() if self.loader_box.count() else None
            if current not in ("auto", "me2", "me3"):
                current = self._saved("loader") or "auto"
            self.loader_box.blockSignals(True)
            self.loader_box.clear()
            self.loader_box.addItem(self.t("loader_auto"), "auto")
            self.loader_box.addItem(self.t("loader_opt_me2"), "me2")
            self.loader_box.addItem(self.t("loader_opt_me3"), "me3")
            idx = self.loader_box.findData(
                current if current in ("auto", "me2", "me3") else "auto")
            self.loader_box.setCurrentIndex(max(0, idx))
            self.loader_box.blockSignals(False)

        def _me3_override(self):
            text = self.me3_edit.text().strip()
            return text or None

        def _set_loader_enabled(self, enabled: bool):
            self.loader_box.setEnabled(enabled)
            self.me3_edit.setEnabled(enabled)
            self.btn_me3_browse.setEnabled(enabled)

        def on_loader_changed(self, _index=None):
            self._schedule_save()
            self.update_loader_state()
            self.update_launch_state()

        def browse_me3(self):
            path, _ = QFileDialog.getOpenFileName(
                self, self.t("loader_me3_path"),
                self.me3_edit.text().strip() or str(pathlib.Path.home()),
                "me3 (me3.exe);;All files (*.*)")
            if path:
                self.me3_edit.setText(path)
                self.update_loader_state()

        def update_loader_state(self):
            """显示加载器状态（ME2 / 独立 me3 / Convergence 自带 me3）；只检测，不安装。"""
            text = self.path_edit.text().strip()
            if not text:
                self.loader_label.setText(self.t("loader_empty"))
                self._set_loader_enabled(False)
                return
            try:
                status = setup_core.loader_status(
                    text, loader=self._loader_choice(), me3_path=self._me3_override())
            except Exception as exc:  # noqa: BLE001
                self.loader_label.setText(f"{self.t('loader_guide_title')}: {exc}")
                return
            kind = status["kind"]
            if kind == setup_core.KIND_ME2:
                self._set_loader_enabled(True)
            elif kind == setup_core.KIND_ME3:
                self._set_loader_enabled(False)
                self._set_loader_choice("me3")
                self.loader_label.setText(self.t("loader_conv_ok").format(
                    p=status.get("me3_path") or "?"))
                return
            else:
                self._set_loader_enabled(False)
                self.loader_label.setText(self.t("loader_unknown"))
                return

            preferred = status.get("preferred") or "me2"
            if preferred == "me3":
                if status.get("me3"):
                    label = self.t("loader_will_ok").format(
                        loader="me3",
                        p=self.t("loader_path_paren").format(p=status["me3_path"]))
                else:
                    label = self.t("loader_will_missing").format(loader="me3")
            else:
                if status.get("me2"):
                    label = self.t("loader_will_ok").format(loader="Mod Engine 2", p="")
                else:
                    label = self.t("loader_will_missing").format(loader="Mod Engine 2")
            if status.get("installed"):
                installed = status.get("mode")
                if not installed and status.get("me2"):
                    installed = "me2"
                if installed:
                    installed_name = "me3" if installed == "me3" else "Mod Engine 2"
                    label += self.t("loader_installed_suffix").format(loader=installed_name)
                    if installed != preferred:
                        label += self.t("loader_switch_hint")
            self.loader_label.setText(label)

        def open_loader_page(self, which: str):
            url = {
                "me2": setup_core.URL_ME2_RELEASES,
                "me3": setup_core.URL_ME3_RELEASES,
                "conv": setup_core.URL_CONVERGENCE,
            }.get(which)
            if not url:
                return
            try:
                webbrowser.open(url)
                self.setup_log(self.t("log_open_url").format(u=url))
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, self.t("error_title"), f"{url}\n{exc}")

        def show_loader_guide(self):
            """详细安装步骤（ME2 / me3 / Convergence）——只跳转发布页，不打包加载器。"""
            dlg = QDialog(self)
            dlg.setWindowTitle(self.t("loader_guide_title"))
            dlg.resize(820, 640)
            lay = QVBoxLayout(dlg)
            view = QTextBrowser(dlg)
            view.setOpenExternalLinks(True)
            view.setHtml(self.t("loader_guide_html").format(
                me2_url=setup_core.URL_ME2_RELEASES,
                me3_url=setup_core.URL_ME3_RELEASES,
                conv_url=setup_core.URL_CONVERGENCE,
                me3_docs=setup_core.URL_ME3_PROFILES))
            lay.addWidget(view, 1)
            box = QDialogButtonBox(dlg)
            b_me2 = box.addButton(self.t("loader_open_me2"), QDialogButtonBox.ActionRole)
            b_me3 = box.addButton(self.t("loader_open_me3"), QDialogButtonBox.ActionRole)
            b_conv = box.addButton(self.t("loader_open_conv"), QDialogButtonBox.ActionRole)
            box.addButton(QDialogButtonBox.Close)
            b_me2.clicked.connect(lambda: self.open_loader_page("me2"))
            b_me3.clicked.connect(lambda: self.open_loader_page("me3"))
            b_conv.clicked.connect(lambda: self.open_loader_page("conv"))
            box.rejected.connect(dlg.reject)
            lay.addWidget(box)
            dlg.exec()

        def _loader_name(self, which: str) -> str:
            return "Mod Engine 2" if which == "me2" else "me3"

        def _ask_install_without_loader(self, loader: str) -> bool:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(self.t("loader_missing_title"))
            box.setText(self.t("loader_missing_msg").format(loader=self._loader_name(loader)))
            b_open = box.addButton(self.t("loader_open_page"), QMessageBox.ActionRole)
            b_me3 = box.addButton(self.t("loader_open_me3"), QMessageBox.ActionRole)
            b_any = box.addButton(self.t("install_anyway"), QMessageBox.AcceptRole)
            box.addButton(self.t("cancel"), QMessageBox.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is b_open:
                self.open_loader_page(loader)
                self.setup_log(self.t("log_loader_missing").format(
                    loader=self._loader_name(loader)))
                return False
            if clicked is b_me3:
                self.open_loader_page("me3")
                return False
            return clicked is b_any

        def _warn_loader_missing(self, loader: str):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(self.t("loader_missing_title"))
            box.setText(self.t("loader_missing_launch_msg").format(
                loader=self._loader_name(loader)))
            b_open = box.addButton(self.t("loader_open_page"), QMessageBox.ActionRole)
            b_me3 = box.addButton(self.t("loader_open_me3"), QMessageBox.ActionRole)
            box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() is b_open:
                self.open_loader_page(loader)
            elif box.clickedButton() is b_me3:
                self.open_loader_page("me3")

        def update_launch_state(self):
            """按当前路径/目标类型刷新「一键启动」按钮和说明（原版 vs Convergence）。"""
            text = self.path_edit.text().strip()
            if not text:
                self.launch_label.setText(self.t("launch_hint_empty"))
                self.btn_launch.setEnabled(False)
                self.btn_launch.setToolTip("")
                return
            try:
                plan = setup_core.plan_launch(
                    text, admin=self.chk_admin.isChecked(), me3_path=self._me3_override())
            except Exception as exc:  # noqa: BLE001
                self.launch_label.setText(self.t("launch_hint_blocked").format(why=exc))
                self.btn_launch.setEnabled(False)
                self.btn_launch.setToolTip("")
                return
            self.btn_launch.setEnabled(plan.ok)
            self.btn_launch.setToolTip("" if plan.ok else plan.reason)
            if not plan.ok:
                self.launch_label.setText(self.t("launch_hint_blocked").format(why=plan.reason))
                return
            if plan.method == "me3":
                self.launch_label.setText(self.t("launch_hint_me3").format(
                    p=plan.summary,
                    seamless=self.t("launch_seamless") if plan.seamless else ""))
            elif plan.method == "me3-vanilla":
                self.launch_label.setText(
                    self.t("launch_hint_me3_vanilla").format(p=plan.summary))
            else:
                self.launch_label.setText(self.t("launch_hint_me2").format(p=plan.summary))

        def on_admin_toggled(self, _checked: bool):
            self._schedule_save()
            self.update_launch_state()

        def setup_launch(self):
            """一键启动：原版走 ME2 bat，Convergence 走 me3（自动选无缝/普通配置）。"""
            text = self.path_edit.text().strip()
            if not text:
                QMessageBox.warning(self, self.t("launch"), self.t("path_missing_msg"))
                return
            admin = self.chk_admin.isChecked()
            me3_path = self._me3_override()
            plan = setup_core.plan_launch(text, admin=admin, me3_path=me3_path)
            if not plan.ok:
                if plan.code == "loader-missing" and plan.loader:
                    self._warn_loader_missing(plan.loader)
                else:
                    QMessageBox.warning(self, self.t("launch_failed_title"), plan.reason)
                return
            if setup_core.game_running():
                answer = QMessageBox.question(
                    self, self.t("launch"), self.t("launch_running_msg"),
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return
            self.busy(True, self.t("launching"))
            self.setup_log(self.t("log_launch_start").format(
                kind=setup_core.kind_label(plan.kind), p=plan.summary))
            if admin:
                self.setup_log(self.t("log_launch_admin"))

            def fn(log):
                return setup_core.launch(text, admin=admin, log=log, me3_path=me3_path)

            self.run_worker(fn, self.on_launched)

        def on_launched(self, res: dict):
            self.setup_log(self.t("log_launch_done"))
            QMessageBox.information(
                self, self.t("launch_done_title"),
                self.t("launch_done_msg").format(
                    cmd=res.get("display") or res.get("summary") or ""))

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
                self.setup_log(f"  [{setup_core.kind_label(kind)}] {p}")
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
            # 没装选中的加载器：先引导去官方发布页（安装器不打包/不再分发 ME2、me3）
            loader = self._loader_choice()
            me3_path = self._me3_override()
            status = setup_core.loader_status(text, loader=loader, me3_path=me3_path)
            if status.get("missing"):
                if not self._ask_install_without_loader(status["missing"]):
                    return
            answer = QMessageBox.question(
                self, self.t("confirm_title"),
                self.t("confirm_msg").format(
                    kind=setup_core.kind_label(target.kind), path=target.root,
                    loader=self._loader_name(status.get("preferred") or "me2")),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer != QMessageBox.Yes:
                return
            save = self.save2_edit.text().strip() or None
            self.busy(True, self.t("installing"))
            self.setup_log(self.t("log_install_start").format(p=target.root))

            def fn(log):
                return setup_core.install(text, save, log=log, loader=loader,
                                          me3_path=me3_path,
                                          language=self._menu_lang())

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
            # 安装完按 ini 里实际写的值回显（安装器可能沿用了旧配置）
            if res.get("menu_language"):
                self._set_menu_lang(res["menu_language"], notify=False)
            self.written = []
            self._update_ini_button()
            self.update_launch_state()
            self.update_loader_state()
            answer = QMessageBox.question(
                self, self.t("install_done_title"),
                self.t("install_done_msg").format(
                    kind=res.get("kind_label", ""), plugin=res["plugin"],
                    loader=res.get("loader_label", ""),
                    launch=res.get("launch", ""), n=len(profiles))
                + "\n\n" + self.t("launch_now_ask"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                self.setup_launch()

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
            self.setup_log(self.t("log_dump_start").format(
                p=game or self.t("unknown_short")))

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
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
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

    # Qt6 默认就开高 DPI；这两个属性在 PySide6 里只是兼容用的弃用项，存在才设。
    for _attr in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        _value = getattr(QApplication, _attr, None)
        if _value is not None:
            QApplication.setAttribute(_value, True)
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    return app.exec()


# ------------------------------------------------------------------ 入口

def _safe_print(*args, **kwargs):
    """`--windowed` 的 exe 没有控制台时 stdout 会写失败；CLI 输出不能因此中断真正的动作
    （尤其是提权实例里 `--set-language` 的写盘）。"""
    try:
        print(*args, **kwargs)
    except (OSError, ValueError):
        pass


def _crash_log(exc: BaseException) -> pathlib.Path:
    base = pathlib.Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else _HERE
    try:
        path = base / ("gui-crash-" + time.strftime("%Y%m%d-%H%M%S") + ".log")
        path.write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        path = pathlib.Path(os.environ.get("TEMP", ".")) / "er-echo-gui-crash.log"
        path.write_text(traceback.format_exc(), encoding="utf-8")
    return path


def _pop_option(args: list[str], name: str) -> tuple[str | None, list[str]]:
    """从参数表里取走 `--name VALUE`，返回 (值, 剩下的参数)。"""
    if name not in args:
        return None, list(args)
    i = args.index(name)
    value = args[i + 1] if i + 1 < len(args) else None
    rest = list(args[:i]) + list(args[i + 2:])
    return value, rest


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
        res = setup_core.dump_tables(game, log=_safe_print)
        _safe_print(json.dumps(res, ensure_ascii=False, indent=2))
        raise SystemExit(0 if not res["errors"] else 1)
    if args and args[0] == "--launch":
        rest = args[1:]
        me3_path, rest = _pop_option(rest, "--me3")
        admin = any(a in ("--admin", "--launch-admin") for a in rest)
        dry_run = "--dry-run" in rest
        path = next((a for a in rest if not a.startswith("--")), "")
        if not path:
            cands = setup_core.find_installed_targets()
            if not cands:
                raise SystemExit(
                    "没找到已安装的 ER Echo（原版 mods\\ER-Echo / Convergence er-echo）；"
                    "用 --launch <游戏路径> 指定")
            path = str(cands[0].root)
        res = setup_core.launch(path, admin=admin, dry_run=dry_run, log=_safe_print,
                                me3_path=me3_path)
        _safe_print(json.dumps(res, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if args and args[0] == "--install":
        rest = args[1:]
        loader, rest = _pop_option(rest, "--loader")
        me3_path, rest = _pop_option(rest, "--me3")
        menu_lang, rest = _pop_option(rest, "--menu-language")
        path = rest[0] if rest else ""
        save = rest[1] if len(rest) > 1 else None
        _safe_print(json.dumps(setup_core.install(path, save, loader=loader or "auto",
                                                  me3_path=me3_path,
                                                  language=menu_lang or
                                                  setup_core.DEFAULT_MENU_LANGUAGE),
                               ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if args and args[0] == "--set-language":
        rest = args[1:]
        if len(rest) < 2:
            raise SystemExit("用法：--set-language <er_echo.ini> <game|auto|zh-CN|zh-TW|en|ja>")
        ini, lang = rest[0], rest[1]
        changed = setup_core.apply_ini_language(ini, lang, log=_safe_print)
        _safe_print(json.dumps({"ini": ini,
                                "language": setup_core.normalize_menu_language(lang),
                                "changed": changed}, ensure_ascii=False))
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
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "ER Echo", f"Startup failed. Log: {log}")
        except Exception:
            pass
        raise
