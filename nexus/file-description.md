## ER Echo 0.1.0 — main file

DLL mod. Requires **ELDEN RING 1.17.2** and **Mod Engine 2**. Offline only.

### Install

1. Back up `%APPDATA%\EldenRing\<SteamID>\ER0000.sl2`.
2. Install Mod Engine 2 into the game folder.
3. Extract this archive into `...\ELDEN RING\Game` (next to `eldenring.exe`).
4. In `config_eldenring.toml`, add the DLL to the existing array:

   ```toml
   [modengine]
   external_dlls = ["er_echo.dll"]
   ```

   If the array already has entries, append `"er_echo.dll"` — do not replace them.
   No `mods` entry is needed; this mod does not replace game files.

5. Export a character from one of your saves:

   ```
   python er-echo\tools\export_profile_from_save.py --list
   python er-echo\tools\export_profile_from_save.py --slot 2 -o profiles\slot2.json
   ```

6. Set `profiles=profiles/slot2.json` under `[clone]` in `er_echo.ini`.
7. Launch with the bundled **`launchmod_eldenring.bat`** (not through Steam's Play button).

### If it does not start

| Symptom | Fix |
|---|---|
| Console flashes, nothing happens; WER: `modengine2_launcher.exe` / `0xC0000409` in `ucrtbase.dll` | The bundled bat passes `-p ".\eldenring.exe"`. If you use your own bat, add it. |
| Game window closes after ~10 s; WER: `eldenring.exe` / `0xc0000005` / offset `0x1EBCEF9` | Run `launchmod_eldenring_admin.bat`, or disable the Steam in-game overlay. |
| Crashes with no mods loaded | Not this mod — verify game files / repair EAC / reinstall, then test vanilla first. |

### Verify

```
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1
```

Then check `er_echo.log` for `er_echo attached` and `ui: message hook installed`.

### Contents

- `er_echo.dll` — the mod
- `er_echo.ini` — configuration (profiles, summoning, AI, language)
- `er_echo_i18n.example.ini` — menu translation override template
- `launchmod_eldenring.bat` — launcher with the `-p` workaround for ME2 2.1.0
- `launchmod_eldenring_admin.bat` — same, self-elevating (for the 10-second Steam-overlay crash)
- `mod\script\talk\m00_00_00_00.talkesdbnd.dcx` — grace-menu ESD; must be mounted through
  `mod_loader` (see the config snippet)
- `profiles\profile.example.json` — placeholder; replace with your own export
- `er-echo\docs\` — install (incl. §3 launch troubleshooting), usage, localisation docs
- `er-echo\tools\` — profile export, doctor, IPC client
- `er-echo\bridge\` — optional LLM battle director (off by default)
- `THIRD-PARTY-LICENSES.txt`, `LICENSES\` — third-party license texts

### Notes

- Do **not** use online. Modded saves get flagged.
- A game update will break the mod until it is rebuilt for the new version.
- Other mods that rewrite the same `BuddyParam` / `NpcParam` / `NpcThinkParam` rows may conflict.
