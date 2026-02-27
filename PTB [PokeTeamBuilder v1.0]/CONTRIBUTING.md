# Contributing to PTB — Pokémon Team Builder

Thank you for your interest in contributing! This document outlines how to get started.

---

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/yourusername/ptb-poketeambuilder.git
   cd "PTB [PokeTeamBuilder v1.0]"
   ```
3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

---

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Run tests: `pytest tests/`
4. Commit with a clear message: `git commit -m "feat: add XYZ feature"`
5. Push and open a Pull Request

---

## Code Style

- Follow **PEP 8** for Python code
- Use **type hints** for all function signatures
- Write **docstrings** for all public classes and methods
- Use `logging` instead of `print()` for all output
- Keep lines under **120 characters**

### Commit Message Format

```
type: short description

Optional longer description.
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

---

## Project Structure

See [README.md](README.md) for the full project structure.

Key areas:
- `src/core/` — Core Pokémon mechanics (types, moves, stats)
- `src/features/` — Feature modules (memory card, GBA support, etc.)
- `src/trading/` — Trading interfaces
- `web/` — Flask web application
- `web/templates/` — Jinja2 HTML templates
- `web/static/` — CSS and JavaScript

---

## Adding Game Support

To add support for a new game era:

1. Add the era to `TeamEra` enum in `src/teambuilder/team.py`
2. Add era features to `GameSpecificFeatures.get_era_features()`
3. Add era compatibility validation in `GameSpecificFeatures.validate_era_compatibility()`
4. Update `TeamAnalyzer.analyze_era_compatibility()` if needed

---

## Reporting Bugs

Please open a GitHub Issue with:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error message / stack trace (if applicable)

---

## Security

**Do not** open public issues for security vulnerabilities. Instead, email the maintainers directly.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
