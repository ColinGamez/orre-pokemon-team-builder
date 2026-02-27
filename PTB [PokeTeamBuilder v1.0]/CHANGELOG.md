# Changelog

All notable changes to PTB — Pokémon Team Builder are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2025-10-25

### Added

#### GameCube / Orre Theme
- Complete dark UI overhaul inspired by Pokémon Colosseum and XD: Gale of Darkness
- Cipher Corp purple (`#7b2fff`) and Snag Machine cyan (`#00e5ff`) color palette
- Orbitron + Rajdhani fonts for authentic Orre terminal aesthetic
- CRT scanline background texture, corner bracket accents on hero section
- Shadow Pokémon type badge with purple aura glow effect
- `.shadow-aura` CSS class for Shadow Pokémon cards
- `.gc-panel` utility class for Orre-style bordered panels
- Animated cyan glow on hero title, shadow pulse animation on cards
- GameCube-themed navbar, footer ("Snag Machine Active"), and login page

#### Memory Card Support (`src/features/memory_card.py`)
- Full GameCube Memory Card `.gci` file parsing
- Supports Colosseum (GC6E/J/P), XD (GXXE/J/P), and Box (GPXE/J)
- GCI header parsing: game ID detection, timestamp, block count
- Best-effort trainer info extraction (GC 2-byte character encoding)
- Best-effort party Pokémon extraction with shadow flag detection
- PTB native `.ptbmc` format (JSON, human-readable, versioned)
- `MemoryCardManager`: load/save/create/delete/list cards
- `GCIParser`: binary parser with graceful fallback for unknown layouts
- Web UI: import GCI, create virtual cards, view slots, Pokémon detail modal
- API: `/api/memory-card/*` (import, create, load, save, delete, list)

#### GBA Link Cable Support (`src/features/gba_support.py`, `src/trading/gba_trading.py`)
- Full Gen 3 GBA `.sav` file parsing (Ruby/Sapphire/Emerald/FireRed/LeafGreen)
- Dual save slot detection (picks highest save index = most recent)
- Section checksum verification (Gen 3 32-bit folded checksum)
- Gen 3 character table decoding (custom GBA encoding)
- **PK3 decryption**: XOR with `personality_value ^ (trainer_id | secret_id << 16)`
- Substructure reordering by `personality_value % 24` (all 24 GAEM orderings)
- Party parsing from section 1, PC box parsing from sections 5–13
- Complete Gen 3 species names (#1–#386), 354 move names, 262 item names
- Shiny detection, gender calculation, IV/EV extraction, met game/level
- `GBAToGCNTransfer`: transfer validation, PK3→PTB conversion
- Colosseum Shadow Pokémon list (48 Pokémon with trainer names)
- XD Shadow Pokémon list (59 Pokémon including Lugia and legendary birds)
- Version-exclusive Pokémon tracking (Ruby/Sapphire/FR/LG)
- `GBALinkCableTrading`: full trading interface with transfer audit log
- Web UI: import `.sav`, view party/boxes, transfer to GCN, Shadow reference
- API: `/api/gba/*` (import-save, transfer-to-gcn, convert-to-ptb, shadow-list, version-exclusives)

### Fixed

#### Core Bugs
- `MoveEffect.__post_init__` — fixed `NameError` from missing `self.` prefix on `effect_type`, `effect_chance`, `effect_value`
- `Pokemon._get_nature_modifiers()` — replaced broken two-pass `if/elif` chain (which caused natures like BOLD to set `attack=1.1` then immediately overwrite with `attack=0.9`) with a single `NATURE_TABLE` lookup dict
- `PokemonTeam.load_from_file()` — implemented the stub that previously had `pass`; now fully reconstructs `Pokemon` and `ShadowPokemon` objects from JSON
- `TeamAnalyzer._has_type_advantage()` — replaced hardcoded duplicate type chart with `TypeEffectiveness.calculate_effectiveness()` call
- `TeamAnalyzer._get_type_weaknesses()` — replaced hardcoded duplicate type chart with `TypeEffectiveness.get_weaknesses()` call
- `TeamAnalyzer.analyze_era_compatibility()` — fixed Shadow Pokémon/move era check to include `TeamEra.COLOSSEUM` and `TeamEra.XD_GALE` alongside `TeamEra.GAMECUBE`

#### Web Application
- `app.py` — fixed `user` vs `current_user` template variable mismatch; `index()` now passes `users_db`, `teams_db`, `battles_db`, `active_tournaments` to template
- `app.py` — fixed `require_login` decorator missing `@functools.wraps(f)` (caused Flask endpoint name collisions)
- `app.py` — `SECRET_KEY` now reads from `PTB_SECRET_KEY` environment variable instead of regenerating on every startup
- `app.py` — removed duplicate `import sys` and `import os` statements; cleaned up path setup
- `base.html` — replaced three `onclick="alert('...coming soon!')"` nav links with proper `disabled` Bootstrap links
- `index.html` — replaced hardcoded `15` in "Active Tournaments" stat with `{{ active_tournaments|length }}`
- `index.html` — fixed `users_db`, `teams_db`, `battles_db` not being passed to template (caused `UndefinedError`)

#### Code Quality
- `team.py` — removed duplicate `nickname: Custom nickname` and `item: Held item` docstring entries in `add_pokemon()`
- `team.py` — replaced `print(f"Error saving team: {e}")` with `logger.error(...)`, added `import logging`
- `gamecube_trading.py` — replaced all `print()` calls with `logger.info()`/`logger.warning()`

#### Security
- `README.md` — removed hardcoded admin PIN `050270`; now references `ADMIN_PIN` environment variable
- `.env.example` — added `PTB_SECRET_KEY` and `ADMIN_PIN` variables

### Changed

- `README.md` — complete rewrite with accurate project structure, API reference, production deployment guide
- `.env.example` — added all new configuration variables with documentation
- `.gitignore` — added `.ptbmc`, `.sav`, `.gci` files; memory card directories; production secrets
- `requirements.txt` — cleaned up, pinned version ranges, added `gunicorn`, `python-dotenv`, `bcrypt`
- `web/app.py` — added `/health` endpoint, `/robots.txt`, production-ready `__main__` block using env vars
- `web/templates/base.html` — updated branding to "PTB // ORRE REGION", added Memory Card and GBA Link nav items
- `web/templates/index.html` — complete Orre-themed rewrite with Shadow Pokémon callout, system log timeline
- `web/templates/login.html` — Orre terminal aesthetic ("Trainer Authentication", "Access Terminal")
