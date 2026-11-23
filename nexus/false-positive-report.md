# Antivirus / VirusTotal false positive — report pack

If a scanner flags the release, this file has what to send. Elastic's VirusTotal engine is an
ML verdict that is known to false-positive on unsigned PyInstaller bundles (Elastic staff have
said the standalone VT scanner can disagree with their real endpoint product), so a single
`Elastic / Malicious (moderate confidence)` hit is not evidence of malware.

## Artifacts (current build, 2026-11-23 23:44)

| File | Size | SHA-256 |
|---|---|---|
| `ER-Echo-Setup-0.1.0.zip` | 29,757,434 B | `F53F0A977447490AE1D1CA88BD1DA6F545798374FFB74BD496C6054123CA7000` |
| ↳ `ER-Echo-Setup.exe` | 1,932,338 B | `ECCBAD6725EDB76D1BA75828C6321A5670E597E18F914FD20472AC9B59F8B495` |
| `ER-Echo-0.1.0.zip` | 953,382 B | `65C9549C58C3BC92F170D9E9EF1541679A49F6B6749AE1AF5404D39936B37B64` |
| `ER-Echo-0.1.0-ESD-fallback.zip` | 92,595 B | `11FB723E9D8D0BB001AAE303FB08E2A9874AA3E3894D43FACEE8A3FE88FDA98D` |
| `er_echo.dll` (inside both archives) | 1,624,673 B | `E7BC7603470E7556A05679508988A39A6A19A6BEF2B8A657C8ECC501A033AEC4` |

VirusTotal lookup (replace the hash if the build changed):

- setup zip: <https://www.virustotal.com/gui/file/F53F0A977447490AE1D1CA88BD1DA6F545798374FFB74BD496C6054123CA7000>
- setup exe: <https://www.virustotal.com/gui/file/ECCBAD6725EDB76D1BA75828C6321A5670E597E18F914FD20472AC9B59F8B495>
- manual zip: <https://www.virustotal.com/gui/file/65C9549C58C3BC92F170D9E9EF1541679A49F6B6749AE1AF5404D39936B37B64>

`ER-Echo-Setup.zip` also contains `_internal/base_library.zip` — that is PyInstaller's
CPython standard-library archive, not a user archive. The only `.exe` in the release is
`ER-Echo-Setup.exe` itself.

Build hashes are also regenerated into `nexus/release-checksums.txt` by `tools/package_nexus.ps1`.
**A rebuild changes every hash** (PE timestamp + zip), so a hash-based ML verdict is cleared by
shipping a fresh build; a structure-based one is not.

## What the software actually does (for the submission form)

- Open-source ELDEN RING mod. Source: <https://github.com/Sanvenir/ER-Echo> (MIT OR Apache-2.0).
- `er_echo.dll` is a Rust DLL loaded into `eldenring.exe` by Mod Engine 2 / me3. It patches game
  structures in **its own process** (no process injection into other processes, no driver, no
  service, no scheduled task).
- It opens one loopback socket: `127.0.0.1:7811` for local tools. No outbound connections, no
  telemetry.
- It writes only into the game folder the user selects (`mods\ER-Echo\`) and the profile files
  next to it; the installer backs up files it changes and has an Uninstall button.
- `ER-Echo-Setup.exe` is a PyInstaller **onedir** bundle (CPython 3.11 + Qt 6 / PySide6, all
  unmodified, LGPL/PSF notices included in `LICENSES\`). It is **not code-signed** — this is the
  only reason heuristic engines rate it.
- The archive contains no obfuscation, no packer (no UPX), no macros.

## Where to submit

| Engine / platform | Where |
|---|---|
| Elastic (VirusTotal) | false-positive process linked from <https://discuss.elastic.co/t/request-for-review-false-positive-flag-on-mypcleanpc-by-elastic-virustotal/380120> (the "Submitting False Positives" form). Attach the hash + VT link + GitHub link. |
| Microsoft Defender | <https://www.microsoft.com/en-us/wdsi/filesubmission> → "Software developer" → false positive |
| McAfee | <https://www.mcafee.com/enterprise/en-us/threat-center/threat-submission.html> |
| VirusTotal | open the file page → Comments → post the explanation + GitHub link (reviewers and users read it) |
| Nexus Mods | if the upload is quarantined, reply to the moderation notice with the VT link, this document, and the source link |

## Copy-paste submission text

```
False positive: ER Echo (ELDEN RING companion mod), open source.

Files (unsigned build):
  ER-Echo-Setup.exe  SHA-256 2143DB47EF0D3387C62C349FCBD2F5E51D492FF40DC4C2EC7320600E1F71B281
  ER-Echo-Setup-0.1.0.zip  SHA-256 3E1DDEDAE3B8E84C4D4064D8E44AB41E33F8C29F2EDE3E71191945D3647DCF10
  er_echo.dll  SHA-256 E7BC7603470E7556A05679508988A39A6A19A6BEF2B8A657C8ECC501A033AEC4

Source (public, MIT/Apache-2.0): https://github.com/Sanvenir/ER-Echo
Build scripts: tools/build_gui_exe.ps1 (installer), mod/build.ps1 (DLL).

ER-Echo-Setup.exe is an unsigned PyInstaller onedir bundle (CPython + Qt6/PySide6, unmodified,
licences included). The DLL is loaded into the game process by the user's mod loader (Mod Engine 2
or me3) and only modifies that process's memory; no persistence, no service, no driver, no
outbound network (a loopback-only 127.0.0.1:7811 socket for local tools). It writes only inside
the game folder the user picks and ships an uninstaller. No packer, no obfuscation.

Please re-check the verdict. Happy to provide a build walkthrough or a signed build if needed.
```

## Reduce the hit rate for the next build

1. **Code signing** is the durable fix (Authenticode OV/EV certificate or Azure Trusted Signing).
   Signing requires identity/business verification; it clears most heuristic and SmartScreen
   warnings. Until then, expect occasional single-engine hits.
2. Keep the build configuration already in place: **onedir** (not onefile), **no UPX**, version
   info + icon, no obfuscation.
3. If the verdict survives a rebuild, ask the engine for a reclassification (above) rather than
   rebuilding repeatedly.
