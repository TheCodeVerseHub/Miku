# Contributing to Miku

Thank you for your interest in contributing to Miku! We welcome contributions from the community to make this Discord leveling bot even better.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. We expect all contributors to:

- Be respectful and considerate of others
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards other community members

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:

   ```sh
   git clone https://github.com/your-username/Miku.git
   cd Miku
   ```

3. **Create a branch** for your changes:

   ```sh
   git checkout -b feature/your-feature-name
   ```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes** - Fix issues or bugs in the code
- **New features** - Add new commands or functionality
- **Documentation** - Improve or expand documentation
- **UI/UX improvements** - Enhance rank cards or embed designs
- **Performance** - Optimize code efficiency
- **Tests** - Add or improve test coverage

## Development Setup

1. **Install Python 3.14+**

2. **Install dependencies**:

   ```sh
   uv sync
   ```

3. **Set up environment variables**:
   Create a `.env` file in the root directory:

   ```env
   DISCORD_TOKEN=your_bot_token_here
   ```

4. **Run the bot**:

   ```sh
   uv run main.py
   ```

## Coding Standards

### Python Style Guide

- Format all code files with isort Black (in that specific order)
- Use 4 spaces for indentation (no tabs)
- Maximum line length of 120 characters
- Use descriptive variable and function names

### Code Organization

- Place bot commands in appropriate cog files under `src/cogs/`
- Utility functions go in `src/utils/`
- Keep database operations in `src/utils/database.py`
- Add doc-strings to functions and classes

### Example Code Style

```python
async def example_function(user_id: int, amount: int) -> bool:
    """
    Brief description of what the function does.

    Args:
        user_id: The Discord user ID
        amount: The amount to add

    Returns:
        True if successful, False otherwise

    Raises:
        ValueError: If amount is less than 0.
    """
    ... # Implementation
```

### Commit Messages

Write clear, concise commit messages:

- Use present tense ("Add feature" not "Added feature")
- First line should be 50 characters or less
- Add detailed description after a blank line if needed
- Reference issue numbers when applicable

**Good commit messages:**

```md
Add pagination to leaderboard command

- Implement page navigation with reactions
- Display 10 users per page
- Fixes #123
```

## Pull Request Process

1. **Update documentation** if you're changing functionality
2. **Test your changes** thoroughly
3. **Update the CHANGELOG.md** with your changes
4. **Ensure your code follows** the coding standards
5. **Submit the pull request** with a clear description

### PR Description Template

```markdown
## Description

Brief description of what this PR does

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing

Describe how you tested these changes

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have tested my changes
- [ ] I have updated the documentation
- [ ] I have updated the CHANGELOG.md
```

## Reporting Bugs

Before creating a bug report, please:

1. **Check existing issues** to avoid duplicates
2. **Collect information** about the bug:
   - Python version
   - Discord.py version
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Error messages or logs

### Bug Report Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:

1. Use command '...'
2. See error

**Expected behavior**
What you expected to happen.

**Screenshots/Logs**
If applicable, add screenshots or error logs.

**Environment:**

- OS: [e.g., Windows 11, Ubuntu 22.04]
- Python Version: [e.g., 3.14]
- discord.py Version: [e.g., 2.3.2]
```

## Feature Requests

We love hearing new ideas! When suggesting a feature:

1. **Check existing feature requests** first
2. **Describe the problem** your feature would solve
3. **Describe your solution** in detail
4. **Consider alternatives** you've thought about
5. **Provide examples** of how it would work

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions you've thought about.

**Additional context**
Any other context, mockups, or examples.
```

## Questions?

If you have questions about contributing, feel free to:

- Open an issue with the `question` label
- Start a discussion in the GitHub Discussions

## License

By contributing to Miku, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Miku!
