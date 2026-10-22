# Contributing to ECHO

This repository is a course project. Every contribution must correspond to actual work.

## Branches and pull requests
1. Create a task (GitHub Issue) and agree on a result.
2. Create a branch from `main`, e.g. `art/nova-dialogues` or `fix/security-camera`.
3. Change the relevant source files. For graphics, commit both source SVG and exported PNG.
4. Run `python -m unittest discover -s tests -v`.
5. Open a Pull Request, explain what changed, link the Issue, and attach screenshots if relevant.
6. Have the other student review before merging.

## Suggested independent areas for the second participant
- Write and revise real Nova/Alex dialogue in `story/levels.json`.
- Improve vector UI assets in `assets/source_svg/` and export to `assets/sprites/`.
- Playtest the game and report real issues with reproduction steps.
- Produce a player guide and verify the menu / game-over / paywall language.

These are suggestions for future contributions, **not** statements of work already completed.

## Safety and licensing
- Do not commit microphone recordings, secrets, authentication tokens, `.env` files, downloaded Vosk models, local save databases, or friends' personal information.
- Generated source assets should have provenance described. Do not commit unlicensed third-party media.
- Preserve the demo-only nature of in-game checkout; never request real banking information.
