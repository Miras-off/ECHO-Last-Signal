# v2.1.3 — Free Life Regeneration (13.11.2026)

- Бесплатное восстановление +1 жизнь раз в 15 минут до максимума 3 бесплатных жизней.
- Таймер работает по времени системы, сохраняется в SQLite и продолжается после закрытия игры.
- Отсчёт виден в главном меню, магазине и на экране блокировки/поражения.
- Демо-покупка +3 жизни и Premium безлимит сохранены, купленные жизни не теряются.
- Миграция старых сохранений и тесты граничных условий.
- Бесплатное восстановление офлайн (без серверной защиты от изменения часов).

# ECHO Final Release v2.1

## Visual overhaul

- cinematic top-down palette based on cold cyan and emergency red lighting;
- 64 px presentation scale, broad metal deck panels and dimensional bulkheads;
- deterministic service panels, vents, pipes, hazard markings and wear;
- soft cached glows and grounded object shadows;
- updated camera cones and dual-layer drone perception visualisation;
- reduced label clutter: distant props remain readable by silhouette and marker;
- new ALEX / НОВА portrait cards, segmented alert strip, objective card, modules and integrated tactical map;
- new generated menu backdrop adapted to the supplied art direction.

## Preserved gameplay

- three Tiled levels and room-by-room visibility;
- nine logical puzzles;
- core hints in the HUD and permanent notes;
- Vosk voice commands;
- local Q-learning difficulty director;
- stealth, cameras, turrets, drones, gates, inventory and saves.

## Reliability

- SQLite sessions now close their Windows file handles deterministically;
- image, text and glow surfaces are cached;
- sensor-ray rendering was reduced to sub-tile sampling for responsive play;
- 56 automated tests pass;
- headless menu and gameplay previews are stored in `docs/previews/`.

## Smooth marker hotfix

- coloured interaction rings are rendered at 4x resolution and smoothly downsampled;
- rings now breathe through quarter-pixel radius steps while opacity changes continuously, replacing the old four-state integer pulse;
- a smooth travelling highlight makes marker motion readable without overpowering the object sprite;
- marker animation now uses UI time, so it remains fluid while map, notes or puzzle overlays pause the world;
- duplicate terminal/core/exit and hover outlines were removed;
- camera, turret, drone, lure, shield and open-gate rings use the same cached renderer.
- `scripts/verify_marker_animation.py` captures four timed frames and fails if the marker pixels remain static.

## Combat animation and tactical fog update

- turret hits now produce a charged red shot, travelling tracer and impact burst;
- drone attacks use a distinct gold/red electrical bolt and target impact;
- the player's EMP pulse expands across its real 5.1-tile range and flashes on every stunned drone;
- short combat events keep fixed source/target snapshots, so effects stay synchronized with simulation events;
- fog of war now reveals only a three-step slice through open doorways, never the complete adjacent room;
- sensor cones are calculated behind the fog and become visible only where they cross the revealed doorway slice;
- hidden camera and drone bodies remain concealed until their tiles enter the visible area;
- tiny L-shaped connector pockets retain the previous room view, preventing a one-step fog collapse;
- `scripts/render_combat_preview.py` renders deterministic QA frames for all three effects and the doorway warning view;
- `scripts/verify_combat_animation.py` compares four phases of every combat animation and fails on static output.


## v2.1.1 — Cinematic audio overhaul

- 7 original OGG looping tracks: 4 scene themes, suspense, chase and non-tonal ship ventilation.
- New distinctive alerts for camera pre-lock/full-lock, drone pursuit, combat attacks and turret firing.
- One-shot sounds for terminal, puzzle correct/wrong answers, ship gates, power core, pickups and Nova abilities.
- Per-track crossfading and music intensity layering without repeatedly restarting ambient.
- Sound priority/cooldowns to avoid ear-piercing overlap.
- Separate saved master/music/SFX/Nova-signal volumes; music and ambience toggles; menu-return fix.
- Original, editable audio samples and reproducible generator `scripts/generate_soundtrack.py`; additional audio tests.


## v2.1.2 — Demo monetization
- 3 persistent attempts with one-life debit for each true defeat, lockout at 0.
- New offline ECHO PAY demo checkout + receipts, 490 ₸ pack of 3 lives, 1490 ₸ Premium Pass with unlimited lives and challenge access.
- SQLite wallet and purchase journal; save reset cannot grant extra attempts.
- Retry, resume, menu and Premium Challenge consistently follow economy rules.
- Does not collect real financial information or charge money.
