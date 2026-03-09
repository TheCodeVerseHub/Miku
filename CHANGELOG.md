# Changelog

All notable changes to Miku will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CONTRIBUTING.md with contribution guidelines
- SECURITY.md with security policy and reporting instructions
- CHANGELOG.md for tracking project changes

## [1.0.0] - 2026-03-06

### Added

- Initial release of Miku Discord Leveling Bot
- XP and leveling system with 15-25 XP per message (60-second cooldown)
- Beautiful rank cards with embeds showing user rank, level, and progress
- Paginated leaderboard system displaying top 50 members
- Hybrid command support for both slash commands (`/`) and prefix commands (`&`)
- SQLite database with async operations for persistent data storage
- User commands:
  - `rank` / `level` - Check user rank and level
  - `leaderboard` / `lb` - View server leaderboard with pagination
  - `xp` - Check detailed XP information
- Admin commands (requires Administrator permission):
  - `setlevel` - Set a user's level
  - `addxp` - Add XP to a user
  - `resetlevel` - Reset a user's level data
  - `resetalllevels` - Reset all server levels (with confirmation)
- Rich embeds with consistent color scheme (#2F3136)
- Progress bar visualization for XP progress
- Ordinal number formatting (1st, 2nd, 3rd) for ranks
- Comprehensive error handling and user feedback
- Custom help command with command categories
- Database utilities for XP management and guild-specific data
- Rank card generator with progress visualization

### Technical Details

- Python 3.14+ support
- discord.py 2.3.2+ integration
- Asynchronous database operations with aiosqlite
- Modular cog-based architecture
- Environment variable configuration
- Proper Discord intents (Message Content, Server Members, Guilds)

### Documentation

- README.md with setup instructions and command reference
- QUICKSTART.md for rapid deployment
- Inline code documentation and docstrings
- MIT License

---

## Release Types

### [MAJOR.MINOR.PATCH] Format

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backwards-compatible)
- **PATCH**: Bug fixes (backwards-compatible)

## Categories

### Added

New features or functionality

### Changed

Changes to existing functionality

### Deprecated

Features that will be removed in future releases

### Removed

Features that have been removed

### Fixed

Bug fixes

### Security

Security vulnerability fixes or improvements

---

## How to Update

To update to the latest version:

```bash
git pull origin main
uv sync
```

## Support

For issues or questions about specific releases, please:

- Check the [README.md](README.md) for documentation
- Open an issue on [GitHub Issues](https://github.com/TheCodeVerseHub/Miku/issues)
- Review the [Contributing Guide](CONTRIBUTING.md)

---

[Unreleased]: https://github.com/TheCodeVerseHub/Miku/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/TheCodeVerseHub/Miku/releases/tag/v1.0.0
