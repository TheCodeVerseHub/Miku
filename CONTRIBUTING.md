# Contributing to Miku

Thank you for your interest in contributing to Miku! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Project Structure](#project-structure)

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. Fork the repository
2. Create a new branch for your feature/fix
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.14+
- PostgreSQL 16+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
# Clone your fork
git clone https://github.com/yourusername/miku.git
cd miku

# Install dependencies
uv sync --group dev

# Copy environment file
cp .env.example .env

# Edit .env with your credentials
# Required: DISCORD_BOT_TOKEN, DATABASE_URL
```

### Running Locally

```bash
# Start the bot
uv run python main.py

# Start the dashboard (separate terminal)
uv run uvicorn dashboard.backend.main:app --reload
```

## Coding Standards

### Python

- **Python 3.14+** — Use modern Python features (pattern matching, type hints)
- **Type Hints** — All functions must have type annotations
- **Async/Await** — Use async/await for all I/O operations
- **Logging** — Use the `logging` module, not `print()`

### Style

- **Formatter:** [Ruff](https://docs.astral.sh/ruff/formatter/) — run `uv run ruff format .`
- **Linter:** [Ruff](https://docs.astral.sh/ruff/) — run `uv run ruff check .`
- **Line Length:** 100 characters
- **Quotes:** Double quotes (`"`) for strings

### Naming Conventions

- **Classes:** `PascalCase` — `LevelService`, `MikuBot`
- **Functions:** `snake_case` — `get_user_data`, `award_message_xp`
- **Variables:** `snake_case` — `user_data`, `guild_id`
- **Constants:** `UPPER_SNAKE_CASE` — `EMBED_COLOR`, `MAX_XP`
- **Private:** Prefix with `_` — `_pool`, `_send()`

### Code Organization

```
src/
├── bot.py              # Bot initialization
├── cogs/               # Discord command handlers
├── services/           # Business logic layer
└── utils/              # Utilities (database, images, API clients)
```

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `refactor` | Code restructuring |
| `docs` | Documentation changes |
| `style` | Formatting changes |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |

### Examples

```
feat(leveling): add /clean-lb command
fix(dashboard): handle empty leaderboard state
refactor(database): extract migration logic
docs(readme): add quick start guide
```

## Pull Request Process

1. Create a branch from `main`
2. Make your changes
3. Run linting and formatting checks
4. Write or update tests if applicable
5. Submit a PR with a clear description
6. Ensure CI passes
7. Request review from maintainers

### PR Requirements

- [ ] Code follows project style (ruff passes)
- [ ] Types are annotated
- [ ] No breaking changes without discussion
- [ ] Related issues are referenced

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=term-missing
```

### Test Guidelines

- Write tests for new features
- Tests should be async where applicable
- Use pytest fixtures for database setup
- Mock external APIs (Discord, GitHub)

## Project Structure

```
miku/
├── main.py                 # Entry point
├── src/                    # Modern codebase
│   ├── bot.py              # Bot class
│   ├── cogs/               # Discord commands
│   ├── services/           # Business logic
│   └── utils/              # Utilities
├── dashboard/              # Web dashboard
│   ├── backend/            # FastAPI app
│   └── static/             # Frontend assets
├── bot/                    # Legacy code (see migration)
├── docs/                   # Documentation
└── .github/                # CI/CD
```

---

Thank you for contributing! 🚀
