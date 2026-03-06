# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of Miku seriously. If you discover a security vulnerability, please help us by disclosing it responsibly.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security vulnerabilities through one of the following methods:

1. **GitHub Security Advisories** (Preferred)
   - Navigate to the [Security tab](https://github.com/TheCodeVerseHub/Miku/security/advisories)
   - Click "Report a vulnerability"
   - Fill out the form with details

2. **Email**
   - Send an email to the repository maintainer
   - Include "SECURITY" in the subject line
   - Provide detailed information about the vulnerability

### What to Include

When reporting a vulnerability, please include:

- **Type of vulnerability** (e.g., SQL injection, XSS, privilege escalation)
- **Full paths of source file(s)** related to the vulnerability
- **Location** of the affected source code (tag/branch/commit)
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact** of the vulnerability
- **Potential remediation** suggestions (if any)

### What to Expect

- **Initial Response**: Within 48 hours
- **Progress Updates**: Every 5-7 days until resolved
- **Resolution Timeline**: We aim to patch critical vulnerabilities within 7 days

### Disclosure Policy

- We'll work with you to understand and resolve the issue quickly
- We request that you do not publicly disclose the vulnerability until we've patched it
- Once fixed, we'll publicly acknowledge your contribution (unless you prefer to remain anonymous)
- We'll credit you in the security advisory (if desired)

## Security Best Practices for Users

### Bot Token Security

**NEVER share your Discord bot token publicly!**

- Store your token in environment variables or a `.env` file
- Add `.env` to your `.gitignore` file
- Regenerate your token immediately if accidentally exposed
- Use a secrets manager for production deployments

### Environment Configuration

```bash
# .env example (NEVER commit this file)
DISCORD_TOKEN=your_bot_token_here
```

### File Permissions

Ensure proper file permissions on sensitive files:

```bash
chmod 600 .env
chmod 600 data/*.db
```

### Database Security

- The SQLite database (`data/levels.db`) contains user data
- Keep regular backups of your database
- Restrict file access to the bot's user account only
- Never expose the database file publicly

### Running the Bot

**Development:**
- Use a separate test bot token for development
- Test in a private Discord server
- Don't use production data in development

**Production:**
- Run the bot with minimal privileges
- Use a dedicated user account (not root)
- Keep dependencies updated
- Monitor bot logs for suspicious activity
- Use a process manager (e.g., systemd, PM2)

## Known Security Considerations

### Rate Limiting

The bot implements XP cooldowns (60 seconds) to prevent abuse. This is not a security feature but helps prevent spam.

### Permission Checks

Admin commands require Discord's Administrator permission. Ensure you properly configure role permissions in your server.

### Data Storage

User data is stored locally in SQLite. Consider:
- Regular backups
- Encryption at rest for sensitive deployments
- Compliance with data protection regulations (GDPR, etc.)

### Dependencies

We use several third-party libraries. Security vulnerabilities in dependencies are addressed as follows:

- Regular dependency updates
- Monitoring security advisories
- Automated dependency scanning (Dependabot)

## Security Updates

Security patches are released as soon as possible after a vulnerability is confirmed. Update to the latest version to ensure you have all security fixes.

### Checking for Updates

```bash
git fetch origin
git log HEAD..origin/main --oneline
```

### Updating

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

## Vulnerability Disclosure Timeline

1. **Day 0**: Vulnerability reported
2. **Day 1-2**: Initial assessment and response
3. **Day 3-7**: Develop and test fix
4. **Day 7-14**: Release patch and security advisory
5. **Day 14+**: Public disclosure (if applicable)

## Third-Party Security

If you discover a security vulnerability in a dependency:

1. Report it to the upstream project first
2. Notify us so we can track and update when fixed
3. We'll help coordinate fixes if needed

## Bug Bounty Program

We currently do not offer a bug bounty program. However, we deeply appreciate security researchers' efforts and will publicly acknowledge your contribution.

## Security Hall of Fame

We'd like to thank the following individuals for responsibly disclosing security vulnerabilities:

- *No reports yet*

## Questions?

If you have questions about this security policy, please open a discussion in GitHub Discussions or contact the maintainers.

---

**Last Updated**: March 6, 2026
