# Changelog

## 0.1.0 — 2026-11-23 (first public release, beta)

Initial public build for ELDEN RING 1.17.2 (exe 2.7.2.0 / 2.7.2.1).

**Companions**

- Summon characters exported from your own save files: face, 22 equipment slots, level, stats and
  memorised spells are injected into the clone.
- Each companion keeps its **own body type and proportions** (`body_type` + the 5 body sliders)
  instead of the player's/default body. The engine bakes body shape at summon time, so the mod
  prepares a per-slot `CharaInitParam` / `FACE_PARAM` row and points each carrier Spirit Ash row at
  it; changes apply on the next summon ("Resummon now" / F8).
- Up to 3 companions at once, each from a different profile.
- Native Spirit Ash behaviour: follow, catch-up teleport, target selection, guard, casting.
- Summon anywhere: no Summoning Pool, no dead zone, no one-party limit.
- "Companion AI" entry in the Comrades sub-menu: each of the three slots can be given its own style
  (Default / Balanced / Melee / Caster / Guardian / Aggressive). The choice is written back to that
  companion's profile JSON (`ai`: `preset` + `aggression` / `spell_rate` / `guard_rate` /
  `target_switch`), so it follows the character across sessions and profile sets. `spell_rate`
  applies immediately; the other three live on a per-slot `NpcThinkParam` row and apply on the next
  summon. Profiles without an `ai` section keep following the global weights.
  Commands: `teammate_ai_status`, `set_teammate_ai`, `teammate_think_rows`.
- Companions use the player Tarnished's damage correction: the Spirit Ash debuff spEffects
  (`296000` attack ×0.25 / taken ×0.5 / poise ×0.05, and `20297000` poise taken ×0.5) are removed
  from the Mimic-Tear NpcParam rows and from live clones. `SpEffectParam` rows are not edited, so
  other Spirit Ashes keep their vanilla numbers. Toggle: `[clone] player_damage`.
- Player level-ups propagate to companions: the level / 8-stat / HP-FP-stamina deltas are applied to
  every loaded profile and written back to its JSON file, then the live clones' `PlayerGameData` is
  updated. Toggle: `[clone] auto_level`.
- "Friendly fire" entry in the Comrades menu: player and companion attacks can hit each other at
  **20% damage** (configurable via `[combat] friendly_fire_rate`), while companions keep team 47 /
  buddy AI (they never treat the player as an enemy) and cannot be locked on (`disable_lock_on`).
  The state persists in `er_echo_roster.json`; damage to ordinary enemies is unchanged.
- Comrade-mode enemy HP correction: enemy max HP scales with the number of **living** companions
  (1 / 2 / 3 → ×1.5 / ×1.8 / ×2.0, 0 → ×1.0). Implemented by writing each enemy's runtime
  `CSChrDataModule` (`hp` / `max_hp` / `max_uncapped_hp` / `base_hp`), so bosses already in combat
  scale immediately and keep their current HP percentage; `NpcParam` / `regulation.bin` are
  untouched. Config: `[balance] enemy_hp_scaling` / `enemy_hp_rates`; diagnostics:
  `enemy_hp_status`, `enemy_hp_scale`.
- `F12` gives the selected item/equipment to a companion; with nothing selected it restores that
  companion's profile loadout (equipment and spells) instead of copying the player's current gear.
- New built-in companion profile: **Sanvenir** (Lv1 easter egg / spare). The installer always copies
  `profiles\builtin_sanvenir.json` and appends it to the end of `profiles=`, so a fresh machine
  without a save still has a summonable companion (instead of the empty example profile). Export
  tools only write/delete `slot<N>_*.json`, and the GUI keeps existing `builtin_*` entries when it
  rewrites `profiles=`, so exporting your own characters never clobbers it; a re-install restores
  the shipped version.

**In-game menu**

- New "Comrades (n/m)" entry at the top of the Site of Grace menu, with a nested sub-menu for party
  size, slot assignment, per-slot Companion AI, resummon, friendly fire and back. Injected into the
  live menu at runtime; the talk ESD it needs is mounted through `mod_loader`.
- Fix: the Comrades entry no longer disappears after returning to the title screen or loading a
  save. The talk-state group is re-created on those reloads, and the menu patch used to be applied
  only once per process; it is now verified and re-applied on the next grace visit.
- Localised menu: English and 简体中文 (follows the game's own text language); wording can be
  overridden with `er_echo_i18n.ini`.
- Auto-summon after resting, fast travelling or resurrecting (optional). Dismissed/lost companions
  can be recalled; a full-party lost fallback resummons the party.
- Hotkeys: `F6` status, `F7` dismiss, `F8` summon, `F9` reload profile, `F10` toggle debug apply,
  `F11` toggle continuous injection, `F12` give item / restore loadout.

**Installer and launch**

- `ER-Echo-Setup.exe`: a one-click installer that only needs the game path. It copies
  `mods\ER-Echo\` and its own `config-er-echo.toml`, exports save characters, writes `profiles=`,
  patches the loader config (all with backups), and uninstalls from the same window. The exe does
  not have to live in the game folder.
- One-click **Launch game** on the Setup tab, branching by target: vanilla + ME2 runs
  `mods\ER-Echo\launch-er-echo*.bat` (optional elevated launch for the Steam-overlay 10-second
  crash); Convergence runs `me3\Windows\me3.exe launch --auto-detect -p .\me3\convergence*.me3`
  and picks the Seamless Co-op profile when `SeamlessCoop\ersc.dll` is present. It warns when
  `eldenring.exe` is already running and offers to launch right after a successful install. CLI:
  `ER-Echo-Setup.exe --launch [path] [--admin] [--dry-run]`.
- Loader guidance: when Mod Engine 2 is not installed the installer offers to open the official ME2
  release page (or install the ER Echo files anyway), and the Setup tab has **Get Mod Engine 2** /
  **Get me3** buttons plus a **Loader install steps...** dialog covering vanilla + ME2 and
  Convergence + me3. Nothing is bundled or redistributed: the installer only writes ER Echo files
  and config references, so users download loaders from the official GitHub/Nexus pages under their
  own licences.
- Vanilla + me3 is supported end to end. The Setup tab has a loader selector (Auto / Mod Engine 2 /
  me3), finds a standalone me3 via `ME3_PATH`, PATH, the me3 uninstall registry entry, common
  folders, or a Browse button, writes `<Game>\er-echo.me3` (`[[natives]]` + `[[package]]`) plus
  `er_echo_loader.json`, and launches it with `me3 launch --auto-detect -p .\er-echo.me3`.
  Switching between ME2 and me3 is one re-install; the recorded loader wins on launch (the other
  one is used as a fallback). All three setups (vanilla + ME2, vanilla + me3, Convergence + bundled
  me3) are one-click install + launch.
- The installer GUI defaults to English and remembers the user's settings across launches
  (language, game path, save, export folder, `er_echo.ini` path and last tab) via `QSettings`; new
  installs write `[i18n] language=game` into `er_echo.ini` (`auto` still supported).
- Menu language can now **follow the game**: `[i18n] language=game` resolves the game's own text
  language (Steam per-game language via `ISteamApps::GetCurrentGameLanguage` inside the game
  process, then `steamapps\appmanifest_1245620.acf`, then Goldberg/SteamEmu settings, then the
  Windows display language). This is the default for fresh installs, so the menu matches the game's
  font and no longer shows missing-glyph boxes.
- Fix: choosing a language in the installer used to only change the installer UI — the in-game menu
  stayed English. The Setup tab now has a separate **"In-game menu language"** dropdown (follow
  game / follow Windows / English / 简体中文) that writes `[i18n] language=` into `er_echo.ini`
  immediately (with a backup) and on every install; the top dropdown is explicitly labelled
  "Installer language". CLI: `--menu-language LANG` on install and `--set-language <ini> LANG` to
  change an existing install without reinstalling.
- Fix: the in-game menu-language write could fail with `Permission denied` when the remembered game
  path was stale (e.g. a deleted temp folder). The installer now only remembers a path it can
  actually recognise as an ER install, drops an invalid remembered path and auto-detects again, and
  — when the game lives under `Program Files` — offers a one-click **"Write as administrator"**
  (UAC) fallback.
- Fix: moving from the flat layout to `mods\ER-Echo\` no longer resets the menu language to English.
  The installer now carries over an existing `<Game>\er_echo.ini` (so `[i18n] language=auto` and
  other hand-edited options survive) instead of always writing the template default `en`.
- The installer is fully localised: with the installer language set to English, the Setup log,
  install/uninstall progress, loader/launch status and error dialogs are English too. CLI logs keep
  following the same language switch (`set_ui_lang`).

**Tools and docs**

- `doctor.ps1` self-check for game version, loader config, DLL dependencies, profiles, permissions,
  elevation and launcher arguments.
- Bundled launchers: `launchmod_eldenring.bat` passes `-p` (works around the ME2 2.1.0 launcher
  abort, `0xC0000409` in `ucrtbase.dll`), and `launchmod_eldenring_admin.bat` self-elevates for the
  environment-specific 10-second crash (`0xc0000005` at `0x1EBCEF9`, Steam overlay vs ME2 hooks).
- Diagnostics: the config log line now shows which `er_echo.ini` was read (`loaded` /
  `not read — defaults`) and its `language=`, making "why is the menu in English?" answerable from
  `er_echo.log`.
- Docs: spell giving is documented as "prepended to the memorised spell list".

**Optional**

- LLM battle director (Python sidecar, `mock` by default): reads combat state and adjusts
  aggression / spell rate / guard rate / target switching; can swap clone gear or stats with
  whitelists, clamps and a rollback point.

**Known issues**

- Version-locked to 1.17.2.
- Conflicts with mods that rewrite the same parameter rows or the same talk/ESD content.
- The legacy root-menu fallback requires the optional ESD archive.
- Beta: the core loop is tested end-to-end on 1.17.2, but this is a 0.x release. Keep a save backup.
