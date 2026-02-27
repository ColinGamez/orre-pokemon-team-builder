# Orre Pokémon Team Builder

> **GameCube × GBA Edition** — The definitive team builder for the Orre region era.
> Full Pokémon Colosseum, XD: Gale of Darkness, and GBA link cable support.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-2.3-green.svg)](https://flask.palletsprojects.com/)
[![GameCube](https://img.shields.io/badge/GameCube-Colosseum%20%7C%20XD-purple.svg)](#gamecube-support)
[![GBA](https://img.shields.io/badge/GBA-Ruby%20%7C%20Sapphire%20%7C%20Emerald%20%7C%20FR%2FLG-gold.svg)](#gba-link-cable)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What Is This?

The **Orre Pokémon Team Builder** is a comprehensive team building and analysis platform built around the **GameCube era** of Pokémon games — specifically Pokémon Colosseum and XD: Gale of Darkness — with full GBA link cable integration for Ruby, Sapphire, Emerald, FireRed, and LeafGreen.

It also supports all other generations (DS through Switch), but the **GameCube/GBA connection is the heart of this project**.

---

## GameCube Support

### Pokémon Colosseum & XD: Gale of Darkness

The GameCube games had unique mechanics that no other Pokémon games have replicated:

| Feature | Details |
|---------|---------|
| **Shadow Pokémon** | 48 in Colosseum, 59 in XD — corrupted Pokémon with closed hearts |
| **Shadow Moves** | Exclusive moves only Shadow Pokémon can use |
| **Purification** | Multi-step process: battles, walking, Relic Stone |
| **Snag Machine** | Wes/Michael's device to capture other trainers' Pokémon |
| **Cipher** | The villain faction creating Shadow Pokémon |
| **Orre Region** | A desert region with no wild Pokémon — all obtained via Snagging or GBA trade |

This tool implements all of these mechanics:
- Shadow Pokémon tracking with shadow level (1–5) and purification progress
- Shadow move availability per shadow level
- Purification Chamber simulation (XD)
- Full Colosseum and XD Shadow Pokémon rosters with trainer locations

### Memory Card Support

Import and manage GameCube Memory Card save files:

```
Supported formats:
  .gci   — Single-game GCI export (Colosseum GC6E/J/P, XD GXXE/J/P, Box GPXE/J)
  .ptbmc — PTB's own JSON-based memory card format
```

**Features:**
- Parse `.gci` files: trainer name, ID, play time, party Pokémon, Shadow Pokémon detection
- Create virtual memory cards with custom labels and sizes (59/251/1019 blocks)
- View all save slots, party Pokémon, and Shadow Pokémon in the web UI
- Export/save cards in `.ptbmc` format (human-readable JSON)

---

## GBA Link Cable

### How It Worked in the Original Games

The GameCube connected to the GBA via an official link cable. This allowed:
1. **Colosseum/XD reading your GBA party and boxes** — you could trade Pokémon between the two systems
2. **Purified Shadow Pokémon going back to GBA** — after purification in Colosseum/XD
3. **Pokémon Box storing GBA Pokémon** on the GameCube Memory Card

### What This Tool Implements

Full Gen 3 GBA save file parsing with **complete PK3 binary decryption**:

```
Supported games:
  Pokémon Ruby      (AXV — US/EU/JP)
  Pokémon Sapphire  (AXP — US/EU/JP)
  Pokémon Emerald   (BPE — US/EU/JP)
  Pokémon FireRed   (BPR — US/EU/JP)
  Pokémon LeafGreen (BPG — US/EU/JP)
```

**Technical implementation:**
- Dual save slot detection (picks highest save index = most recent)
- Section checksum verification (Gen 3 32-bit folded checksum)
- Gen 3 character table decoding (custom GBA encoding, not ASCII)
- **PK3 decryption**: XOR with `personality_value ^ (trainer_id | secret_id << 16)`
- Substructure reordering by `personality_value % 24` (all 24 GAEM orderings)
- Party parsing from section 1, PC box parsing from sections 5–13 (14 boxes × 30 slots)
- Shiny detection, gender calculation, IV/EV extraction, met game/level
- Complete Gen 3 species names (#1–#386), 354 move names, 262 item names

**Transfer validation:**
- GBA→GCN compatibility checking (species range, EVs, eggs, shadow status)
- Version-exclusive Pokémon tracking (Ruby/Sapphire/FR/LG exclusives)
- Shadow Pokémon blocked from transfer until purified

---

## All Supported Games

| Platform | Games |
|----------|-------|
| **GameCube** ⭐ | Pokémon Colosseum, XD: Gale of Darkness, Pokémon Box |
| **GBA** ⭐ | Ruby, Sapphire, Emerald, FireRed, LeafGreen |
| **Wii** | Pokémon Battle Revolution, Pokémon Ranch |
| **DS** | Diamond/Pearl/Platinum, HeartGold/SoulSilver, Black/White, B2/W2 |
| **3DS** | X/Y, ORAS, Sun/Moon, USUM |
| **Switch** | Let's Go, Sword/Shield, BDSP, Legends Arceus, Scarlet/Violet |

⭐ = Primary focus with deep feature support

---

## Features

### Core Team Builder
- Advanced stat calculations with correct Gen 3 formulas
- Nature optimization (all 25 natures with correct stat modifiers)
- Move selection with Gen 3 move database
- Type coverage analysis using the complete type chart (all generations + Shadow type)
- Weakness/resistance analysis, synergy scoring, stat balance

### Shadow Pokémon System
- Full Colosseum roster: 48 Shadow Pokémon with trainer locations
- Full XD roster: 59 Shadow Pokémon including Lugia and the legendary birds
- Shadow level tracking (1–5) with stat reduction calculation
- Purification progress tracking
- Shadow move availability per shadow level
- Relic Stone purification simulation

### Memory Card Manager
- Import `.gci` files from real GameCube saves
- Create virtual memory cards
- View trainer data, party Pokémon, Shadow Pokémon
- Save/load in `.ptbmc` format

### GBA Link Cable
- Parse `.sav` files from all Gen 3 GBA games
- Full PK3 binary decryption
- View party and all 14 PC boxes (30 slots each)
- Transfer validation (GBA→GCN and GCN→GBA)
- Shadow Pokémon reference lists

### Additional Features
- Battle simulator with damage calculations
- Breeding calculator (IV inheritance, nature passing, egg groups)
- Tournament system (bracket management, multiple formats)
- Social hub (user profiles, team sharing)
- Admin panel (user management, analytics)
- Desktop GUI (tkinter)
- Mobile app (React Native)

---

## Installation

### Prerequisites
- Python 3.8 or higher

### Quick Start

```bash
# Clone the repository
git clone https://github.com/ColinGamez/orre-pokemon-team-builder.git
cd "orre-pokemon-team-builder/PTB [PokeTeamBuilder v1.0]"

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env — set PTB_SECRET_KEY and ADMIN_PIN at minimum

# Initialize databases
python initialize_databases.py

# Run the web app
cd web
python app.py
```

Open `http://localhost:5000` in your browser.

### Desktop GUI

```bash
python run_gui.py
```

---

## Configuration

Copy `.env.example` to `.env`:

```env
# Required
PTB_SECRET_KEY=generate-with-python-secrets-module
ADMIN_PIN=your-secure-pin

# Optional — email verification
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password

# Server
HOST=0.0.0.0
PORT=5000
DEBUG=False
```

---

## Project Structure

```
PTB [PokeTeamBuilder v1.0]/
├── src/
│   ├── core/
│   │   ├── pokemon.py      # Pokemon, ShadowPokemon, stats, natures
│   │   ├── types.py        # Type chart (all gens + Shadow type)
│   │   └── moves.py        # Move system
│   ├── features/
│   │   ├── memory_card.py  # GameCube Memory Card (.gci / .ptbmc)
│   │   └── gba_support.py  # GBA save parser, PK3 decryption, GBA→GCN
│   ├── trading/
│   │   ├── gamecube_trading.py  # Colosseum/XD/Box trading
│   │   └── gba_trading.py       # GBA link cable interface
│   └── teambuilder/
│       ├── team.py         # PokemonTeam, TeamEra, GameSpecificFeatures
│       └── analyzer.py     # Type coverage, weaknesses, synergy
├── web/
│   ├── app.py              # Flask web application
│   ├── static/css/style.css     # GameCube/Orre dark theme
│   └── templates/
│       ├── base.html            # Orre navigation
│       ├── index.html           # Home (Orre-themed)
│       ├── memory_card.html     # Memory Card manager
│       └── gba_support.html     # GBA Link Cable interface
├── data/                   # Pokémon database (JSON)
├── .env.example            # Configuration template
└── requirements.txt        # Python dependencies
```

---

## API Reference

### Memory Card
```
POST /api/memory-card/import-gci   — Import a .gci file
POST /api/memory-card/create       — Create a virtual card
POST /api/memory-card/load         — Load a .ptbmc file
POST /api/memory-card/save         — Save card to .ptbmc
POST /api/memory-card/delete       — Delete a card
GET  /api/memory-card/list         — List saved cards
```

### GBA Link Cable
```
POST /api/gba/import-save          — Parse a GBA .sav file
POST /api/gba/transfer-to-gcn      — Validate GBA→GCN transfer
POST /api/gba/convert-to-ptb       — Convert PK3 to PTB format
GET  /api/gba/shadow-list          — Shadow Pokémon list (Colosseum/XD)
GET  /api/gba/version-exclusives   — Version-exclusive Pokémon
```

### Health
```
GET  /health                       — Service health check
GET  /robots.txt                   — Robots exclusion
```

---

## Production Deployment

```bash
# Install production server
pip install gunicorn

# Run with gunicorn
cd web
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Set `PTB_SECRET_KEY` to a strong random value in production:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of changes.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Disclaimer

This is a fan-made tool. Not affiliated with Nintendo, Game Freak, or The Pokémon Company.
Pokémon and all related names are trademarks of their respective owners.
