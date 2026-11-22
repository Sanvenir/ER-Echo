# Install & portability (ER Echo)

Short version: **it runs on another machine, but only if three hard gates pass** —
exact game version, ModEngine2 config, and write access to the game folder. Plus one
soft gate: you must export your **own** character profile.

---

## 0. Compatibility at a glance

| Requirement | Value | If not met |
|---|---|---|
| Game version | **1.17.2** — `eldenring.exe` product version `2.7.2.0` (worldwide) or `2.7.2.1` (JP) | DLL idles or the game crashes (RVA/AOB mismatch) |
| OS | Windows 10/11 x64 | cannot load (x64 PE) |
| Runtimes | **none** — no VC++ redist, no .NET, no Python | — |
| Loader | ModEngine2 2.x (tested 2.1.0) with a correct `config_eldenring.toml` | DLL is never injected |
| Network | offline only; launch with `launchmod_eldenring.bat` (bypasses EAC) | modded save online = soft-ban |
| Saves | `.sl2` is never written; injection happens in memory | back it up anyway |

Why these are hard limits:

* `mod/vendor/fromsoftware-rs-main/crates/eldenring/src/rva.rs` registers only
  `(EN, "2.7.2.0")` and `(JP, "2.7.2.1")`; anything else panics in `rva::get()`.
* `mod/src/ui.rs` / `ezstate.rs` hook by **byte-exact AOB**, matched against 1.17.2.
* `er_echo.dll` imports only system DLLs (`kernel32`, `msvcrt`, `ntdll`, `oleaut32`,
  `user32`, `ws2_32`, `bcryptprimitives`, `api-ms-win-core-synch-l1-2-0`) — that's why
  no redistributable is needed.
* The grace menu comes from a **version-bound ESD**
  (`mod/script/talk/m00_00_00_00.talkesdbnd.dcx`).

---

## 1. Fresh install (an untested machine)

Run from the game root (next to `eldenring.exe`).

0. **Confirm vanilla works first.** Launch `eldenring.exe` directly (no ME2) and let it sit at
   the title screen for a minute. If that crashes, the problem is the game install or EAC, not
   this mod — verify files / repair EAC / reinstall (see §3), and do not install mods on top.
   Then **back up** `%APPDATA%\EldenRing\<SteamID>\ER0000.sl2` and turn off Steam auto-updates
   (or use offline mode). A game update to 1.17.3+ breaks this build.
1. Install **ModEngine2** release into the game root:
   `modengine2_launcher.exe`, `modengine2\bin\modengine2.dll`,
   `config_eldenring.toml`. Then copy the package's launchers over the stock one:
   `launchmod_eldenring.bat` (adds `-p ".\eldenring.exe"`, which avoids a ME2 2.1.0 launcher
   crash — `0xC0000409` in `ucrtbase.dll`) and `launchmod_eldenring_admin.bat` (self-elevating,
   for the 10-second Steam-overlay crash).
2. **Easiest path:** run `ER-Echo-Setup.exe` from the release zip, point it at
   `...\ELDEN RING\Game` (or a Convergence folder) and press Install — it copies the files,
   exports your characters, writes `profiles=` and patches the loader config (with backups).
   The manual steps below are the equivalent by hand.

> **Path convention (since 2026-11-21):** the source tree lives at `D:\Projects\ER-Echo\`,
> **not** inside the game folder. In the commands below, `er-echo\tools\...` means the repo
> root (`D:\Projects\ER-Echo\tools\...`). Scripts locate the game automatically
> (`-GameDir` / `$env:ER_ECHO_GAME_DIR` / Steam registry); you no longer put the sources in `Game\`.
2. Copy the release package over `...\ELDEN RING\Game`. Minimum set:
   `er_echo.dll`, `er_echo.ini`, `profiles\`, `er-echo\tools\`, `er-echo\bridge\`,
   `er-echo\docs\`, and **`mod\script\talk\m00_00_00_00.talkesdbnd.dcx`** — the grace-menu
   patch requires that ESD to be mounted (without it the log says
   `cannot find grace root list start state` and no "Comrades" entry appears).
3. Make sure the DLL is in `config_eldenring.toml`, and mount the ESD:
   ```toml
   [modengine]
   external_dlls = ["er_echo.dll"]

   [extension.mod_loader]
   enabled = true
   loose_params = false
   mods = [ { enabled = true, name = "er-echo", path = "mod" } ]
   ```
4. Export your own character:
   ```powershell
   python er-echo\tools\export_profile_from_save.py --list
   python er-echo\tools\export_profile_from_save.py --slot 2 -o profiles\me.slot2.json
   ```
   then set `profiles=profiles/me.slot2.json` under `[clone]` in `er_echo.ini`.
5. Launch with `.\launchmod_eldenring.bat` — **not** via Steam's Play button (that starts
   EAC).
6. Verify:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1
   ```
   and check `er_echo.log` for `er_echo attached`, `i18n: language=...`,
   `ui: message hook installed`. Sit at a Site of Grace: the first entry is
   "Comrades (n/m)" / "战友（n/m）"; summon with a Spirit Ash or press **F8**.
7. Optional LLM director (stdlib only, no `pip install`):
   ```powershell
   python er-echo\bridge\director.py --llm mock
   ```

---

## 2. What to change when moving machines

| Item | Copy as-is? | Change |
|---|---|---|
| `er_echo.dll`, `mod\...\*.dcx`, `config_eldenring.toml` | yes | must match game version |
| `er_echo.ini` | mostly | `profiles=` → your own export; `[i18n] language` if needed |
| Profiles exported from the author's save | **no** | export your own |
| `er-echo\tools\*.ps1` | yes | they locate the game via `tools\gamedir.ps1` (`-GameDir` / `ER_ECHO_GAME_DIR` / Steam registry) |
| ModEngine2 | **no** | install on the target machine |

---

## 3. Symptom → cause

| Symptom | Cause | Fix |
|---|---|---|
| Nothing happens, no `er_echo.log` | DLL not injected | check `external_dlls`; launch via the bat; read `modengine2\logs\*.log` |
| Log exists but no `attached` | wrong game version | run 1.17.2 |
| Crash on startup | version mismatch / other DLL mods | keep only `er_echo.dll`; check `crashdumps\` |
| Core-dump ~10 s after launch; WER shows `eldenring.exe` / `0xc0000005` / offset `0x1EBCEF9` | Steam's in-game overlay (`gameoverlayrenderer64.dll`) collides with ModEngine2's hooks in the input manager (dump panic: `DLUserInputManagerImpl_win32.cpp(98)`) | run `launchmod_eldenring_admin.bat` (elevated ⇒ Steam cannot inject the overlay), or untick "Enable the Steam Overlay" in Steam > Settings > In Game |
| The .bat window flashes and closes; WER shows `modengine2_launcher.exe` / `0xC0000409` | ME2's `-t er` runs Steam install-path auto-detection, which throws on some machines | make sure the command has `-p ".\eldenring.exe"` (both bats do); it skips the detection |
| No "Comrades" entry at a grace | `mods = []` or ESD missing/overwritten | fix `mods`; restore the ESD; remove conflicting mods |
| Menu shows blanks/boxes | message hook failed (AOB) or font lacks glyphs | check `message hook installed`; set `language` to match the game text language |
| Clone looks like the player | `profiles` empty/wrong | export and point `profiles=` |
| No logs/JSON in the game folder | no write permission (Program Files) | grant permission or move the game out of Program Files |

---

## 4. Localization

`er_echo.ini` → `[i18n] language=en|auto|zh-CN|zh-TW|ja`. New installs default to English;
`auto` follows the Windows display language. Any other language code (e.g. `ko`, `de`) can be supplied through
`er_echo_i18n.ini` (copy `er_echo_i18n.example.ini`). See `docs/i18n.md`.

Keep the menu language consistent with the game's text language: the game only loads
the font atlas of its current language, so mismatches can render as boxes.
