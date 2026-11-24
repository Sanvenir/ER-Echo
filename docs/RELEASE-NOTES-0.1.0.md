# ER Echo 0.1.0

Summon characters from your own save files as Spirit Ash companions. Offline only.

**ELDEN RING 1.17.2** (exe 2.7.2.0 / 2.7.2.1) · Windows 10/11 x64 · Mod Engine 2 or me3

## Downloads

| Asset | What it is |
|---|---|
| `ER-Echo-Setup-0.1.0.zip` | **Recommended.** One-click installer (`ER-Echo-Setup.exe`): copies the mod, exports a character from your save, writes the loader config with backups, uninstalls from the same window. |
| `ER-Echo-0.1.0.zip` | Manual install: extract into `...\ELDEN RING\Game`, follow `README.txt` (add `external_dlls` + `mod_loader` yourself). No `.exe`. |
| `ER-Echo-0.1.0-ESD-fallback.zip` | Optional. Root-menu ESD variant, only if the runtime-injected "Comrades" entry never appears. |
| `release-checksums.txt` | SHA-256 of the DLL and of each archive. |

## Quick start

1. Back up `%APPDATA%\EldenRing\<your SteamID>\ER0000.sl2`.
2. Install **Mod Engine 2** (vanilla) or use **me3** (vanilla standalone or The Convergence 3.x).
3. Download `ER-Echo-Setup-0.1.0.zip`, extract it anywhere and run **`ER-Echo-Setup.exe`**.
4. Set the game path, pick the loader, click **Install**, then **Launch game**.
5. At a Site of Grace the first entry is **Comrades (n/m)**. `F8` also summons directly.

The installer does not bundle Mod Engine 2 / me3 / Convergence — it links to their official pages.
The mod works offline; never take a modded save online.

## Verify

```
er_echo.dll  SHA-256 e7bc7603470e7556a05679508988a39a6a19a6bef2b8a657c8ecc501a033aec4
```

Compare the archives with `release-checksums.txt`. Source, build scripts and the exact build steps
are in the repository: <https://github.com/Sanvenir/ER-Echo>.

## Notes

- The installer is **unsigned**. Heuristic engines (Elastic on VirusTotal in particular) may flag
  PyInstaller bundles; the installer has no persistence, no outbound network, writes only into the
  game folder you choose and has an Uninstall button. Use the manual archive if you prefer not to run
  an `.exe`.
- Version-locked: a game update breaks the mod until offsets/patterns are re-mapped and it is rebuilt.
- Conflicts with mods that rewrite the same parameter rows or the same talk/ESD content.
- Beta: keep a save backup.

## Links

- Documentation: <https://github.com/Sanvenir/ER-Echo/tree/main/docs>
- Build instructions: <https://github.com/Sanvenir/ER-Echo#build-from-source>
- Nexus Mods page: (link once published)

ELDEN RING is a trademark of FromSoftware, Inc. and Bandai Namco Entertainment. This is an
unofficial fan work.
