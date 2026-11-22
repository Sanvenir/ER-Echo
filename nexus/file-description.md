## ER Echo 0.1.0 — installer (main file)

One-click installer for **ER Echo**, the companion mod that summons characters from your own save
files as Spirit Ash allies. Requires **ELDEN RING 1.17.2** and **Mod Engine 2**. Offline only.

### Install

1. Back up `%APPDATA%\EldenRing\<your SteamID>\ER0000.sl2`.
2. Install Mod Engine 2 into your game folder (`...\ELDEN RING\Game`).
3. Extract this archive anywhere and run **`ER-Echo-Setup.exe`**.
4. Set the game path — `...\ELDEN RING\Game` for vanilla, or
   `...\Convergence3\ConvergenceER` for Convergence/me3 — and click **Install**.

The installer:

- copies `mods\ER-Echo\` (DLL, `er_echo.ini`, talk ESD, tools, docs) and its own
  `config-er-echo.toml`; it does **not** overwrite your `config_eldenring.toml`;
- exports that save's character(s) and writes `profiles=` in `er_echo.ini`;
- backs up every file it touches; **Uninstall** is in the same window.

5. Start the game with `mods\ER-Echo\launch-er-echo.bat` (the installer dialog shows the exact path).

### If it does not start

| Symptom | Fix |
|---|---|
| Console flashes, nothing happens; WER: `modengine2_launcher.exe` / `0xC0000409` in `ucrtbase.dll` | Use the bundled `launch-er-echo.bat` (it passes `-p ".\eldenring.exe"`). |
| Game window closes after ~10 s; WER: `eldenring.exe` / `0xc0000005` / offset `0x1EBCEF9` | Run `launch-er-echo-admin.bat`, or disable the Steam in-game overlay. |
| Crashes with no mods loaded | Not this mod — verify game files / repair EAC / reinstall, then test vanilla first. |

### Verify

```
powershell -NoProfile -ExecutionPolicy Bypass -File mods\ER-Echo\er-echo\tools\doctor.ps1
```

Then check `mods\ER-Echo\er_echo.log` for `er_echo attached` and `ui: message hook installed`.

### Contents

- `ER-Echo-Setup.exe` — installer / config / profile-export GUI
- `_internal\payload\` — mod files embedded into the installer (not meant to be used directly)
- `_internal\` — bundled Python + Qt runtime; keep the whole folder together

### Manual install alternative

If you prefer not to run an installer, download the optional **ER Echo - Manual Install** archive,
unzip it into `...\ELDEN RING\Game` and follow its `README.txt` (add `external_dlls` and the
`mod_loader` entry to `config_eldenring.toml` yourself).

### Notes

- Do **not** go online with a modded save.
- A game update breaks the mod until it is rebuilt for the new version.
- Other mods that rewrite the same `BuddyParam` / `NpcParam` / `NpcThinkParam` rows, or the same talk
  ESD, may conflict.
