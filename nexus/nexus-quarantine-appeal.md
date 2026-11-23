# Nexus quarantine — appeal email

Send to **support@nexusmods.com** from the account that uploaded the file. Keep the tone plain and
factual; include the hash and the source link (Nexus asks for exactly those two things to review a
compiled-code upload).

---

**Subject:** Quarantine review request — ER Echo (Elden Ring) 0.1.0, `ER-Echo-Setup-0.1.0.zip`

**Body:**

Hello,

My upload **ER Echo 0.1.0** for ELDEN RING was quarantined by your automated checks. Could you review
it, please?

- Mod: ER Echo — summon characters from your own save files as Spirit Ash companions (offline only)
- File: `ER-Echo-Setup-0.1.0.zip` — 29,757,434 bytes
  SHA-256 `F53F0A977447490AE1D1CA88BD1DA6F545798374FFB74BD496C6054123CA7000`
- Other files in the same release: `ER-Echo-0.1.0.zip` (manual install, no .exe),
  `ER-Echo-0.1.0-ESD-fallback.zip` (optional data file)

**What the file is**

The archive contains one executable, `ER-Echo-Setup.exe` (1,932,338 bytes, SHA-256
`ECCBAD6725EDB76D1BA75828C6321A5670E597E18F914FD20472AC9B59F8B495`), plus its `_internal\` folder.
It is an installer/config GUI built with PyInstaller in **onedir** mode: CPython 3.11 + Qt 6 /
PySide6 (unmodified, LGPL/PSF notices included in `LICENSES\`). `_internal\base_library.zip` is
PyInstaller's Python standard-library archive, not a user archive — there is no installer inside an
installer and no other executable.

It copies the mod into the game folder the user selects, exports a character from their own save,
writes the loader config (with `.bak` backups) and has an Uninstall button. It does not create
services, scheduled tasks or autoruns, and it makes no outbound connections. The mod DLL only opens a
loopback socket (`127.0.0.1:7811`) for the bundled local tools.

**Why a scanner may flag it (false positive)**

The build is **unsigned**, and the payload contains a DLL loaded into `eldenring.exe` by the user's
mod loader (Mod Engine 2 or me3). Both are common heuristic triggers for game mods. On VirusTotal the
report I have shows an **Elastic** "Malicious (moderate confidence)" verdict (one engine); Elastic has
publicly acknowledged that its standalone VirusTotal scanner can disagree with its actual endpoint
product and produces false positives on signed and unsigned installers alike. The report already lists
the build hashes:

- https://www.virustotal.com/gui/file/F53F0A977447490AE1D1CA88BD1DA6F545798374FFB74BD496C6054123CA7000

We also rebuilt after the first upload and removed the developer/automation scripts from the released
archive (key-simulation and DLL-swap helpers), which are the kind of files heuristic engines dislike.

**Source code and build steps** (public, MIT OR Apache-2.0):

- https://github.com/Sanvenir/ER-Echo — branch `main`
- Release hashes: `nexus/release-checksums.txt` in that repo

Build on Windows:

```
# 0) prerequisites: rustup stable-x86_64-pc-windows-gnu + MSYS2 binutils (as.exe),
#    Python 3.11, pip packages PySide6 6.12 / PyInstaller 6.22 / Pillow
# 1) the DLL (Rust)
powershell -NoProfile -ExecutionPolicy Bypass -File mod\build.ps1
# 2) the installer payload (DLL + docs + launcher + ESD)
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_payload.ps1 -SkipBuild
# 3) ER-Echo-Setup.exe (PyInstaller onedir)
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_gui_exe.ps1 -SkipPayload
# 4) the three release zips
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_nexus.ps1 -SkipBuild
```

The mod source is a Rust `cdylib` (`mod/src/`); the installer source is `tools/profile_export_gui.py`
+ `tools/er_echo_setup.py`. Nothing is obfuscated or packed (no UPX), and the full third-party
licence texts ship inside the archive.

**Options if the executable is still a problem**

1. I can publish the **manual-install archive only** (`ER-Echo-0.1.0.zip`, 953,382 bytes, no .exe) as
   the main file, and keep the installer as an optional file after your review.
2. I can supply a **code-signed** build once the certificate is issued (in progress).
3. I can provide any additional build logs or a signed statement if that helps.

Please let me know if you need anything else. Thanks for your time.

— <your Nexus username>

---

## After sending

1. If they clear the file: re-upload the **same** file (the hash in the appeal must match what you
   upload — do not rebuild in between).
2. If they ask for a non-exe option: upload `ER-Echo-0.1.0.zip` as **Main files** and the installer
   as **Optional files**; update `page-fields.md`/`description.bbcode` accordingly.
3. Record the ticket number and outcome in `checklist.md` for the next release.
