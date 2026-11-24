# ER Echo

Summon characters from your own ELDEN RING save files as Spirit Ash companions: same face, body,
gear, level and spells, driven by the game's native AI. Offline only.

![ER Echo](nexus/media/00-banner-1400x400.jpg)

[Download](#download-and-install) | [Build from source](#build-from-source) | [Project structure](#project-structure) | [Docs](#documentation) | [Releasing](#releasing)

## What it is

ER Echo is a DLL mod for **ELDEN RING 1.17.2** (Rust, loaded by Mod Engine 2 or me3). It replaces a
Spirit Ash with a character exported from one of your own save slots and keeps the ash's native
follow / engage / catch-up / casting behaviour.

- **Your own Tarnished.** Export from any save slot: face, body type, 22 equipment slots, level,
  8 stats and memorised spells.
- **1-3 companions at once**, each from a different profile. No Summoning Pool, no dead zone, no
  one-party limit for direct summons (F8 / auto-summon).
- **Native AI.** Follow, catch-up teleport, target selection, guard, casting. Nothing is written to
  `regulation.bin` or to your `.sl2`.
- **Site of Grace menu.** A "Comrades (n/m)" entry with party size, slot assignment, per-slot
  Companion AI, resummon, friendly fire and back.
- **Balance and QoL.** Player-level damage correction, level-ups carry over to companions, enemy HP
  scales with the number of living companions, `F12` gives gear / restores a loadout.
- **Localised menu.** Follows the game's text language (English and Simplified Chinese bundled,
  overridable with a plain-text file).
- **Optional LLM battle director** (Python sidecar, mock/offline by default).

> Offline only. Launch with EAC disabled through a mod loader, and never take a modded save online
> (soft-ban). Back up `%APPDATA%\EldenRing\<SteamID>\ER0000.sl2` before changing anything.

## Download and install

| Where | What |
|---|---|
| **Nexus Mods** (main page) | Main file `ER-Echo-Setup-0.1.0.zip`; optional manual install and ESD fallback archives |
| **[GitHub Releases](https://github.com/Sanvenir/ER-Echo/releases/latest)** | The same three archives plus `release-checksums.txt` (mirror / hash verification) |

| File | Purpose |
|---|---|
| `ER-Echo-Setup-0.1.0.zip` | **Recommended.** One-click installer: copies the mod, exports a save character, writes `profiles=` and the loader config (all with backups), uninstalls from the same window, launches the game. |
| `ER-Echo-0.1.0.zip` | Manual install (no `.exe`): unzip into `...\ELDEN RING\Game` and follow its `README.txt` (add `external_dlls` and the `mod_loader` entry yourself). |
| `ER-Echo-0.1.0-ESD-fallback.zip` | Optional. Root-menu ESD variant, only if the runtime-injected "Comrades" entry never appears. |

Requirements:

1. Legit **ELDEN RING 1.17.2** (exe 2.7.2.0 / 2.7.2.1), Windows 10/11 x64. Confirm the vanilla game
   reaches the title screen and stays up for a minute **without** mods before installing.
2. A loader: [Mod Engine 2](https://github.com/soulsmods/ModEngine2/releases) for vanilla, or
   [me3](https://github.com/garyttierney/me3/releases) for vanilla / The Convergence 3.x. Loaders are
   **not** bundled or redistributed; the installer links to their official pages.

Quick start:

1. Back up your save.
2. Extract `ER-Echo-Setup-0.1.0.zip` anywhere and run `ER-Echo-Setup.exe`.
3. Set the game path, pick the loader, click **Install**, then **Launch game**.
4. At a Site of Grace the first entry is **Comrades (n/m)**. `F8` also summons directly.

The installer is unsigned, so some heuristic engines (Elastic on VirusTotal in particular) may flag
it. It is a PyInstaller bundle: no persistence, no outbound network, writes only into the game folder
you select, and has an Uninstall button. Source, build scripts and the SHA-256 of every release are
in this repository; use the manual archive if you prefer not to run an `.exe`.

## Build from source

### Toolchain (one-time setup)

| Component | Requirement | Used for |
|---|---|---|
| Windows | 10/11 x64 | everything |
| Rust | `rustup` with the `stable-x86_64-pc-windows-gnu` toolchain | `er_echo.dll` |
| MSYS2 binutils | extracted to `%USERPROFILE%\er-tools\binutils` (provides `mingw64\bin\as.exe`) | GNU linker |
| Python | 3.11, `python` on PATH | installer and export tools |
| Python packages | `PySide6`, `PyInstaller`, `Pillow` | installer build; scripts install them into `build\pydeps`, not system Python |
| Game install | ELDEN RING 1.17.2 (optional) | `doctor.ps1`, copy DLL after build |

The GNU toolchain is used because it ships `rust-lld` + MinGW and does **not** need Visual Studio
Build Tools, but it lacks `as.exe`, hence MSYS2 binutils.

### One command

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_all.ps1
```

Runs all four steps below, prints the archives, and refreshes `nexus\release-checksums.txt`.

### Step by step

```powershell
# 1) Rust DLL -> mod\target\release\er_echo.dll (also copied to the game folder if one is detected)
powershell -NoProfile -ExecutionPolicy Bypass -File mod\build.ps1

# 2) Installer payload -> build\payload (DLL, docs, launcher bats, talk ESD, licences)
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_payload.ps1 -SkipBuild

# 3) Installer -> dist\tools\ER-Echo-Setup\ (PyInstaller onedir; installs PySide6/PyInstaller/Pillow on first run)
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_gui_exe.ps1 -SkipPayload

# 4) Release archives -> dist\nexus\ plus nexus\release-checksums.txt
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_nexus.ps1 -SkipBuild
```

Outputs:

| Artifact | Location | Notes |
|---|---|---|
| `er_echo.dll` | `mod\target\release\` | Rust DLL, about 1.6 MB |
| payload | `build\payload\` | 47 files embedded into the installer |
| `ER-Echo-Setup.exe` + `_internal\` | `dist\tools\ER-Echo-Setup\` | onedir, about 73 MB; ship the whole folder |
| `ER-Echo-Setup-<ver>.zip` | `dist\nexus\` | main download, about 28 MB |
| `ER-Echo-<ver>.zip` | `dist\nexus\` | manual install, about 1 MB |
| `ER-Echo-<ver>-ESD-fallback.zip` | `dist\nexus\` | optional ESD variant |
| `release-checksums.txt` | `nexus\` | SHA-256 of the three archives and the DLL |

### Build notes

- **PowerShell 5.1 and UTF-8.** `.ps1` files containing non-ASCII text must be saved as UTF-8 **with
  BOM**, otherwise Windows PowerShell reads them as ANSI/GBK and can swallow the next line into a
  comment. Every tracked `.ps1` has a BOM; check the first three bytes after editing.
- **`as.exe` not found.** Verify `%USERPROFILE%\er-tools\binutils\mingw64\bin\as.exe`; `mod\build.ps1`
  adds it and `%USERPROFILE%\.cargo\bin` to PATH for the build.
- **Slow pip.** The installer build uses a Tsinghua mirror (see `tools\build_gui_exe.ps1`). Offline,
  install `PySide6` / `pyinstaller` / `pillow` into `build\pydeps` first.
- **Do not switch back to PyQt5.** PyQt5 is GPLv3/commercial and would make the installer a GPL work;
  the GUI uses PySide6 (LGPLv3) and the build trims unused Qt modules.
- **Antivirus.** Unsigned PyInstaller bundles plus a game-injecting DLL are common false-positive
  targets; builds use `--onedir` and `--noupx`. See `nexus\false-positive-report.md`.
- **Build outputs are not committed.** `mod/target/`, `build/` and `dist/` are ignored and reproducible.

## Project structure

```
ER-Echo/
|- mod/                       Rust DLL (cdylib)
|  |- src/                    lib.rs, ezstate.rs, i18n.rs, balance.rs, spirit.rs, ui.rs, ipc.rs, ...
|  |- Cargo.toml              version (keep in sync with file names and the mod page)
|  |- build.ps1               cargo build --release with the right PATH
|  `- examples/offsets.rs     offset probing helper
|- vendor/fromsoftware-rs-main/   upstream crates (eldenring, shared) + NON-AI licence texts
|- tools/                     build and runtime tools
|  |- build_all.ps1           one-command build (DLL -> payload -> installer -> archives)
|  |- package_payload.ps1     builds the installer payload
|  |- build_gui_exe.ps1       PyInstaller build of ER-Echo-Setup.exe
|  |- package_nexus.ps1       builds the three release archives + checksums
|  |- publish_github_release.ps1   publishes a GitHub Release (tag, notes, assets)
|  |- er_echo_setup.py        install/uninstall, loader handling, launch, param tables (no Qt)
|  |- profile_export_gui.py   Qt GUI (install, export, settings)
|  |- doctor.ps1              install self-check (version, loader, deps, permissions, launcher args)
|  |- gamedir.ps1 / gamedir.py    game folder detection
|  |- export_profile_from_save.py  export a character from .sl2
|  |- ipc_client.py / ipc_send.py  local IPC tools for the DLL
|  `- switch_menu_mode.ps1, reset_to_vanilla.ps1, ...
|- bridge/                    optional Python sidecar (LLM battle director, mock by default)
|- config/                    behavior_map.yaml, weights.schema.json
|- install/                   er_echo.ini template, ME2 config snippet, launcher templates, built-in profile, Convergence tables
|- ui/                        Site of Grace ESD assets (base template, esd scripts, out_vanilla, out_rootmenu)
|- docs/                      install, usage, plugin, Convergence, i18n, design, implementation log, releasing
|- nexus/                     Nexus release materials (copy, fields, checklist, media, licences, appeal templates)
|- dist/                      (ignored) build output
`- build/                     (ignored) intermediate files and PyInstaller dependencies
```

Key files:

| Path | Role |
|---|---|
| `mod/src/lib.rs` | DLL entry point, hotkeys, IPC commands, config parsing, summon/inject flow |
| `mod/src/ezstate.rs` | runtime EzState patch for the grace menu, re-applied after reloads |
| `mod/src/i18n.rs` | menu strings and game-language resolution |
| `tools/package_nexus.ps1` | the only release packaging entry point (three archives + hashes) |
| `install/er_echo.ini.template` | config defaults (`profiles`, friendly fire, balance, AI, i18n) |
| `nexus/checklist.md` | upload-day checklist |
| `docs/RELEASING.md` | GitHub release instructions (web UI, script, gh) |

## Documentation

Most documents are written in Chinese; the code, comments and Nexus page are bilingual.

| Document | Content |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) / [INSTALL.en.md](docs/INSTALL.en.md) | install from scratch, moving to another machine, symptom table |
| [docs/usage.md](docs/usage.md) | every config key, menu, hotkey, IPC command, troubleshooting |
| [docs/PLUGIN.md](docs/PLUGIN.md) | plugin layout (`mods\ER-Echo\`) and uninstall |
| [docs/CONVERGENCE.md](docs/CONVERGENCE.md) | The Convergence 3.x + me3 adaptation |
| [docs/i18n.md](docs/i18n.md) | menu language resolution and custom strings |
| [docs/design.md](docs/design.md) | design notes and research |
| [docs/implementation-log.md](docs/implementation-log.md) | day-by-day implementation log |
| [docs/RELEASING.md](docs/RELEASING.md) | publishing to GitHub Releases |
| [nexus/](nexus/README.md) | mod page copy, fields, screenshots, upload checklist |

Useful commands:

```powershell
powershell -File tools\doctor.ps1                     # install self-check
python tools\export_profile_from_save.py --list       # list save characters
python tools\ipc_client.py status                     # in-game state
python tools\ipc_send.py rebuild_clone --arg mode=model
```

## Releasing

1. Bump the version in `mod/Cargo.toml` and keep page / file names in sync.
2. Build: `powershell -File tools\build_all.ps1`.
3. Check `nexus\release-checksums.txt`.
4. **Nexus:** follow [nexus/checklist.md](nexus/checklist.md); if a file is quarantined, use
   [nexus/nexus-quarantine-appeal.md](nexus/nexus-quarantine-appeal.md).
5. **GitHub:** `powershell -File tools\publish_github_release.ps1 -DryRun`, then run it without
   `-DryRun` (or follow [docs/RELEASING.md](docs/RELEASING.md) for the web UI / `gh`).

## Compatibility and known limitations

- **Version-locked** to 1.17.2 (exe 2.7.2.0 / 2.7.2.1). A game update breaks the mod until offsets
  and patterns are re-mapped and it is rebuilt.
- **Conflicts** with mods that rewrite the same parameter rows (BuddyParam, NpcParam, NpcThinkParam,
  BuddyStoneParam) or the same talk/ESD content. Test with only this mod first.
- **Spirit Ash choice:** the Lone Wolf Ashes rows are rewritten by default; map other ashes in
  `er_echo.ini` (`buddy_rows`).
- **Beta:** the core loop is tested end-to-end on 1.17.2, but this is a 0.x release.

## License and third parties

- This repository: **MIT OR Apache-2.0** ([LICENSE](LICENSE), [LICENSE-MIT](LICENSE-MIT),
  [LICENSE-APACHE](LICENSE-APACHE)).
- `vendor/fromsoftware-rs-main`: **MIT-NON-AI / Apache-2.0-NON-AI**; full texts ship with the
  repository and every archive ([nexus/THIRD-PARTY-LICENSES.txt](nexus/THIRD-PARTY-LICENSES.txt)).
  The software may not be used to train machine-learning models.
- Installer runtime: Qt 6 / PySide6 (LGPLv3), CPython (PSF), OpenSSL (Apache-2.0), libffi (MIT),
  PyInstaller (GPLv2 with exception); full texts are in the archives under `LICENSES\`.
- The release archives contain a modified copy of the vanilla talk ESD (required as the grace-menu
  mount point). No `regulation.bin`, no other game files, no third-party saves. `ui/base` is only a
  repacking template and is not shipped.
- Mod Engine 2, me3 and The Convergence are not redistributed.

ELDEN RING is a trademark of FromSoftware, Inc. and Bandai Namco Entertainment. This is an
unofficial fan work, not affiliated with or endorsed by either company.
