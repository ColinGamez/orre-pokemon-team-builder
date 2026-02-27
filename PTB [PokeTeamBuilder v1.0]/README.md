# PTB — Pokémon Team Builder v1.0

> **Orre Region Edition** — Full GameCube era support with Shadow Pokémon mechanics, GBA link cable integration, and Memory Card management.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-2.3-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

PTB is a comprehensive Pokémon team building and analysis platform supporting games from the **GameCube era through modern Switch titles**. It features a full web interface, desktop GUI, and mobile app, with deep support for the GameCube era's unique mechanics.

### Highlights

- 🎮 **GameCube-era focus** — Shadow Pokémon, purification, Colosseum/XD mechanics
- 💾 **Memory Card support** — Import `.gci` files, manage virtual memory cards (`.ptbmc`)
- 🔗 **GBA Link Cable** — Parse Gen 3 `.sav` files (Ruby/Sapphire/Emerald/FR/LG), full PK3 decryption
- 🌐 **Web interface** — Orre-themed dark UI with real-time features via Socket.IO
- 📊 **Team analysis** — Type coverage, weakness analysis, synergy scoring, stat balance
- 🏆 **Tournaments** — Bracket management, multiple formats, leaderboards

---

## Features

### Game Support

| Platform | Games |
|----------|-------|
| **GameCube** | Pokémon Colosseum, XD: Gale of Darkness, Pokémon Box |
| **GBA** | Ruby, Sapphire, Emerald, FireRed, LeafGreen |
| **Wii** | Pokémon Battle Revolution, Pokémon Ranch |
| **DS** | Diamond/Pearl/Platinum, HeartGold/SoulSilver, Black/White, B2/W2 |
| **3DS** | X/Y, ORAS, Sun/Moon, USUM |
| **Switch** | Let's Go, Sword/Shield, BDSP, Legends Arceus, Scarlet/Violet |

### Core Features

- **Team Builder** — Advanced stat calculations, nature optimization, move selection
- **Team Analyzer** — Type coverage, weakness/resistance analysis, synergy scoring
- **Battle Simulator** — Damage calculations, AI opponents
- **Breeding Calculator** — IV inheritance, nature passing, egg group compatibility
- **Shadow Pokémon System** — Full Colosseum/XD mechanics (shadow levels, purification, Relic Stone)
- **Memory Card Manager** — Import `.gci` files, create virtual memory cards, manage save slots
- **GBA Link Cable** — Parse Gen 3 saves, PK3 decryption, GBA→GCN transfer validation
- **Tournament System** — Bracket management, multiple formats
- **Social Hub** — User profiles, team sharing, community features
- **Admin Panel** — User management, content moderation, analytics

---

## Installation

### Prerequisites

- Python 3.8 or higher
- pip

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/ptb-poketeambuilder.git
cd "PTB [PokeTeamBuilder v1.0]"

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize databases
python initialize_databases.py
python initialize_social_database.py  # Optional: social features

# Run the web application
cd web
python app.py
```

The web app will be available at `http://localhost:5000`.

### Desktop GUI

```bash
python run_gui.py
```

### Backend Server (Email Verification)

```bash
# Demo mode (no SMTP required — emails saved to logs/)
python start_backend.py

# Production mode (configure .env first)
python start_backend.py --production
```

---

## Configuration

Copy `.env.example` to `.env` and configure:

```env
# Flask secret key (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
PTB_SECRET_KEY=your-secret-key-here

# Admin panel PIN (keep secure, do not commit)
ADMIN_PIN=your-admin-pin-here

# Email (optional — for verification features)
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
│   ├── core/           # Core Pokémon classes and mechanics
│   │   ├── pokemon.py  # Pokemon, ShadowPokemon, stats, natures
│   │   ├── types.py    # Type effectiveness (all generations + Shadow)
│   │   ├── moves.py    # Move system with PK3 decryption support
│   │   └── abilities.py
│   ├── battle/         # Battle engine and AI
│   ├── config/         # Game configuration and database paths
│   ├── features/       # Advanced features
│   │   ├── memory_card.py      # GameCube Memory Card (.gci/.ptbmc)
│   │   ├── gba_support.py      # GBA save parser, PK3 format, GBA→GCN
│   │   ├── breeding_calculator.py
│   │   ├── tournament_system.py
│   │   └── save_file_importer.py
│   ├── gui/            # Desktop GUI (tkinter)
│   ├── teambuilder/    # Team management, analysis, validation
│   │   ├── team.py     # PokemonTeam, TeamEra, GameSpecificFeatures
│   │   ├── analyzer.py # TeamAnalyzer (type coverage, weaknesses, synergy)
│   │   ├── validator.py
│   │   └── optimizer.py
│   ├── trading/        # Trading system
│   │   ├── gamecube_trading.py # Colosseum/XD/Box trading
│   │   ├── gba_trading.py      # GBA link cable interface
│   │   ├── ds_trading.py
│   │   ├── switch_trading.py
│   │   └── trading_hub.py
│   └── utils/          # Logging, performance, sprite management
├── web/
│   ├── app.py          # Flask web application (main entry point)
│   ├── static/
│   │   ├── css/style.css       # GameCube/Orre theme
│   │   └── js/main.js
│   └── templates/
│       ├── base.html           # Base template with Orre navigation
│       ├── index.html          # Home page
│       ├── login.html          # Trainer authentication
│       ├── dashboard.html      # User dashboard
│       ├── memory_card.html    # Memory Card manager
│       └── gba_support.html    # GBA Link Cable interface
├── mobile/             # React Native mobile app
├── data/               # Pokémon database (JSON)
│   ├── pokemon.json
│   ├── moves.json
│   └── abilities.json
├── .env.example        # Environment variable template
├── requirements.txt    # Python dependencies
├── run_gui.py          # Desktop GUI entry point
└── start_backend.py    # Backend server entry point
```

---

## Memory Card Support

PTB supports GameCube Memory Card save files:

### Supported Formats
- **`.gci`** — Single-game GCI export (Colosseum, XD, Box — all regions)
- **`.ptbmc`** — PTB's own JSON-based memory card format

### Features
- Import `.gci` files and view trainer data, party Pokémon, and Shadow Pokémon
- Create virtual memory cards with custom labels and sizes
- Export/save cards in `.ptbmc` format
- Shadow Pokémon detection with purification progress tracking

### Usage
Navigate to **Memory Card** in the web interface, or use the API:
```
POST /api/memory-card/import-gci   — Import a .gci file
POST /api/memory-card/create       — Create a new virtual card
GET  /api/memory-card/list         — List saved cards
```

---

## GBA Link Cable Support

PTB implements the full Gen 3 GBA save file format:

### Supported Games
- Pokémon Ruby / Sapphire / Emerald
- Pokémon FireRed / LeafGreen
- All regions (US, EU, JP)

### Features
- Full PK3 binary decryption (personality value XOR encryption, substructure reordering)
- Party and PC box parsing (14 boxes × 30 slots)
- Shiny detection, gender calculation, IV extraction
- GBA→GCN transfer compatibility validation
- Shadow Pokémon reference lists (Colosseum: 48 Pokémon, XD: 59 Pokémon)
- Version-exclusive Pokémon tracking

### Usage
Navigate to **GBA Link** in the web interface, or use the API:
```
POST /api/gba/import-save          — Parse a .sav file
POST /api/gba/transfer-to-gcn      — Validate GBA→GCN transfer
GET  /api/gba/shadow-list          — Get Shadow Pokémon list
GET  /api/gba/version-exclusives   — Get version exclusives
```

---

## Admin Panel

Access via the **🔒 Admin Panel** button in the desktop GUI.

**PIN:** Set via `ADMIN_PIN` environment variable (see `.env.example`).

**Features:**
- 📊 Dashboard with system statistics
- 👥 User management (search, verify, delete, ban)
- 📝 Content moderation
- 📈 Detailed analytics
- 💾 Database backup and maintenance
- ⚙️ System settings

See [ADMIN_PANEL_GUIDE.md](ADMIN_PANEL_GUIDE.md) for full documentation.

---

## API Reference

### Team Builder
```
GET  /api/pokemon/search           — Search Pokémon by name/ID
POST /api/teams                    — Create a new team
GET  /api/teams                    — List user's teams
POST /api/teams/<id>/analyze       — Analyze a team
```

### Battle
```
POST /api/battle/create            — Create a battle
GET  /api/battle/<id>              — Get battle state
POST /api/battle/<id>/move         — Make a move
```

### Tournaments
```
GET  /api/tournaments              — List tournaments
POST /api/tournaments              — Create a tournament
POST /api/tournaments/<id>/join    — Join a tournament
```

### Memory Card
```
POST /api/memory-card/import-gci   — Import .gci file
POST /api/memory-card/create       — Create virtual card
POST /api/memory-card/load         — Load .ptbmc file
POST /api/memory-card/save         — Save card to .ptbmc
POST /api/memory-card/delete       — Delete a card
GET  /api/memory-card/list         — List saved cards
```

### GBA Link Cable
```
POST /api/gba/import-save          — Parse GBA .sav file
POST /api/gba/transfer-to-gcn      — Validate transfer
POST /api/gba/convert-to-ptb       — Convert PK3 to PTB format
GET  /api/gba/shadow-list          — Shadow Pokémon list
GET  /api/gba/version-exclusives   — Version exclusives
```

---

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
cd web
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Using Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENV PTB_SECRET_KEY=change-me-in-production
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "web/app:app"]
```

### Environment Variables (Production)

| Variable | Description | Required |
|----------|-------------|----------|
| `PTB_SECRET_KEY` | Flask session secret key | **Yes** |
| `ADMIN_PIN` | Admin panel PIN | **Yes** |
| `SMTP_SERVER` | SMTP server for emails | No |
| `SMTP_PORT` | SMTP port (default: 587) | No |
| `SENDER_EMAIL` | Sender email address | No |
| `SENDER_PASSWORD` | SMTP password/app password | No |
| `HOST` | Server host (default: 0.0.0.0) | No |
| `PORT` | Server port (default: 5000) | No |
| `DEBUG` | Debug mode (default: False) | No |

---

## Development

### Running Tests

```bash
pip install pytest pytest-flask
pytest tests/
```

### Code Style

This project follows PEP 8. Use `flake8` for linting:
```bash
pip install flake8
flake8 src/ web/
```

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of changes.

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

## Disclaimer

This project is a fan-made tool and is not affiliated with, endorsed by, or connected to Nintendo, Game Freak, or The Pokémon Company. Pokémon and all related names are trademarks of their respective owners.
