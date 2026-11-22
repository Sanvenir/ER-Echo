# Changelog

## Unreleased

- New "Companion AI" entry in the "Comrades" grace sub-menu (a third-level menu): each of the three
  companion slots can be given its own AI style (**Default / Balanced / Melee / Caster / Guardian /
  Aggressive**). The choice is written back to that companion's own profile JSON (`ai`:
  `preset` + `aggression` / `spell_rate` / `guard_rate` / `target_switch`), so it follows the
  character across sessions and profile sets. `spell_rate` (number of memorised spells equipped)
  applies immediately; aggression / guard / target-switch live on a per-slot `NpcThinkParam` row and
  apply on the next summon. Profiles without an `ai` section keep following the global weights.
  New commands: `teammate_ai_status`, `set_teammate_ai`, `teammate_think_rows`.
- Companions now use the player Tarnished's damage correction: the summon debuff spEffects
  (`296000` attack ×0.25 / taken ×0.5 / poise ×0.05, and `20297000` poise taken ×0.5) are removed
  from the Mimic-Tear NpcParam rows and from live clones. `SpEffectParam` rows themselves are not
  edited, so other Spirit Ashes keep their vanilla numbers. Toggle: `[clone] player_damage`.
- Player level-ups now propagate to companions: the level/8-stat/HP-FP-stamina deltas of the
  player are applied to every loaded profile and written back to its JSON file, then the live
  clones' `PlayerGameData` is updated. Toggle: `[clone] auto_level`.
- New "Friendly fire" entry in the "Comrades" grace sub-menu: player and companion attacks can hit
  each other at **20% damage** (configurable via `[combat] friendly_fire_rate`), while companions keep
  team 47 / buddy AI (they never treat the player as an enemy) and cannot be locked on
  (`disable_lock_on`). The state persists in `er_echo_roster.json`; damage to ordinary enemies is unchanged.
- Comrade-mode enemy HP correction: enemy max HP scales with the number of **living** companions
  (1 / 2 / 3 → ×1.5 / ×1.8 / ×2.0, 0 → ×1.0). Implemented by writing each enemy's runtime
  `CSChrDataModule` (`hp` / `max_hp` / `max_uncapped_hp` / `base_hp`), so bosses already in combat
  scale immediately and keep their current HP percentage; `NpcParam` / `regulation.bin` are untouched.
  Config: `[balance] enemy_hp_scaling` / `enemy_hp_rates`; diagnostics: `enemy_hp_status`,
  `enemy_hp_scale`.
- Installer GUI now defaults to English and remembers the user's settings across launches (language,
  game path, save, export folder, `er_echo.ini` path and last tab) via `QSettings`; new installs write
  `[i18n] language=en` into `er_echo.ini` (`auto` still supported).
- `F12` with nothing selected now restores that companion's profile loadout (equipment and spells)
  instead of copying the player's current gear.
- Docs: spell giving now correctly documented as "prepended to the memorised spell list".

## 0.1.0 — 2026-11-20 (first public release, beta)

Initial public build for ELDEN RING 1.17.2 (exe 2.7.2.0 / 2.7.2.1).

**Companions**
- Summon characters exported from your own save files: face, 22 equipment slots, level, stats and
  memorised spells are injected into the clone.
- Up to 3 companions at once, each from a different profile.
- Native Spirit Ash behaviour: follow, catch-up teleport, target selection, guard, casting.
- Summon anywhere: no Summoning Pool, no dead zone, no one-party limit.

**In-game UI**
- New "Comrades (n/m)" entry at the top of the Site of Grace menu, with a nested sub-menu for party
  size, slot assignment and resummon. Injected into the live menu at runtime; no ESD is shipped or
  replaced.
- Localised menu: English, 简体中文, 繁體中文, 日本語; other languages via `er_echo_i18n.ini`.
- `F12` gives the selected item/equipment to a companion.

**Quality of life**
- Auto-summon after resting, fast travelling or resurrecting (optional).
- Dismissed/lost companions can be recalled; a full-party lost fallback resummons the party.
- `doctor.ps1` self-check for game version, loader config, DLL dependencies, profiles, permissions,
  elevation and launcher arguments.
- Bundled launchers: `launchmod_eldenring.bat` passes `-p` (works around the ME2 2.1.0 launcher
  abort, `0xC0000409` in `ucrtbase.dll`), and `launchmod_eldenring_admin.bat` self-elevates for the
  environment-specific 10-second crash (`0xc0000005` at `0x1EBCEF9`, Steam overlay vs ME2 hooks).

**Optional**
- LLM battle director (Python sidecar, `mock` by default): reads combat state and adjusts
  aggression / spell rate / guard rate / target switching; can swap clone gear or stats with
  whitelists, clamps and a rollback point.

**Known issues**
- Version-locked to 1.17.2.
- Conflicts with mods that rewrite the same parameter rows or the same talk/ESD content.
- The legacy root-menu fallback requires the optional ESD archive.
