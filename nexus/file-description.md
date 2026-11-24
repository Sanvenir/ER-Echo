## ER Echo 0.1.0 — installer (main file)

One-click installer for **ER Echo**, the companion mod that summons characters from your own save
files as Spirit Ash allies. Requires **ELDEN RING 1.17.2** and a mod loader: **Mod Engine 2**
(tested with 2.1.0) or **me3** (standalone, or bundled with The Convergence 3.x). Offline only.

### Install

1. Back up `%APPDATA%\EldenRing\<your SteamID>\ER0000.sl2`.
2. Install a loader (`Mod Engine 2` into `...\ELDEN RING\Game`, or `me3` for vanilla /
   Convergence). The installer links to the official pages if one is missing — no loader files
   are bundled.
3. Extract this archive anywhere and run **`ER-Echo-Setup.exe`**.
4. Set the game path — `...\ELDEN RING\Game` for vanilla, or
   `...\Convergence3\ConvergenceER` for Convergence/me3 — pick the loader and click **Install**.

The installer:

- copies `mods\ER-Echo\` (DLL, generated `er_echo.ini`, talk ESD, tools, docs, licences) and its own
  `config-er-echo.toml`; it **adds** the er-echo entries to your `config_eldenring.toml` after a `.bak`
  backup — it never replaces the file. For me3 it appends to the `.me3` profile instead;
- exports that save's character(s) and writes `profiles=` in `er_echo.ini` (built-in Sanvenir stays at
  the end of the list);
- backs up the config files it edits (`.bak-er-echo-*`); copied mod files are replaced in place;
  **Uninstall** is in the same window;
- detects whether a loader is installed: if not, it offers to open the official
  [ME2 release page](https://github.com/soulsmods/ModEngine2/releases) (and the
  [me3 release page](https://github.com/garyttierney/me3/releases) / Convergence page) and includes a
  **Loader install steps...** dialog. Loader binaries are **not** bundled or redistributed;
- supports **vanilla + me3**: pick "me3 (standalone)" in the loader selector (me3.exe is found via
  PATH / registry or picked with Browse); it writes `<Game>\er-echo.me3` and the Launch button runs
  `me3 launch --auto-detect -p .\er-echo.me3`. ME2 <-> me3 switching is one re-install.

5. Click **Launch game** in the same window (the install dialog also offers "Launch the game now?").
   Vanilla starts `mods\ER-Echo\launch-er-echo.bat`; Convergence starts
   `me3\Windows\me3.exe launch --auto-detect -p .\me3\convergence*.me3` (Seamless Coop profile
   auto-selected).

### If it does not start

| Symptom | Fix |
|---|---|
| Console flashes, nothing happens; WER: `modengine2_launcher.exe` / `0xC0000409` in `ucrtbase.dll` | Use the bundled `launch-er-echo.bat` (it passes `-p ".\eldenring.exe"`). |
| Game window closes after ~10 s; WER: `eldenring.exe` / `0xc0000005` / offset `0x1EBCEF9` | Tick **Launch as administrator** in the installer (or run `launch-er-echo-admin.bat`), or disable the Steam in-game overlay. |
| Crashes with no mods loaded | Not this mod — verify game files / repair EAC / reinstall, then test vanilla first. |

### Verify

```
powershell -NoProfile -ExecutionPolicy Bypass -File mods\ER-Echo\tools\doctor.ps1 -Target "C:\...\ELDEN RING\Game"
```

Then check `er_echo.log` in the game folder for `er_echo attached` and
`ui: message hook installed`.

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
- The installer is **unsigned**, so some heuristic engines (Elastic on VirusTotal in particular) may
  flag it. It is a PyInstaller bundle: no persistence, no outbound network, writes only into the game
  folder you pick, and has an Uninstall button. Source, build scripts and the SHA-256 of every release
  file are public: <https://github.com/Sanvenir/ER-Echo>. Use the manual archive if you prefer not to
  run an .exe.
- Mirror: the same archives + `release-checksums.txt` are on
  [GitHub Releases](https://github.com/Sanvenir/ER-Echo/releases/latest).
