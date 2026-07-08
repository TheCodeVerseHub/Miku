# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately by opening a security advisory on GitHub:

1. Go to https://github.com/yourusername/miku/security/advisories
2. Click "New draft security advisory"
3. Provide a detailed description, steps to reproduce, and potential impact

Do **not** report security vulnerabilities through public GitHub issues, discussions, or pull requests.

### What to expect

- **Acknowledgment** within 48 hours
- **Assessment** within 5 business days
- **Fix timeline** communicated after assessment

## Security Best Practices

### For Bot Operators

1. **Keep secrets secret** — Never commit `.env` files. Rotate tokens immediately if exposed.
2. **Use least privilege** — Only grant the permissions your bot needs (see [Permissions](#recommended-permissions)).
3. **Regular updates** — Run `uv sync` frequently to receive security patches.
4. **Database security** — Use strong PostgreSQL passwords and restrict network access.
5. **Dashboard HTTPS** — Always use a reverse proxy (nginx, Caddy) with TLS in production.

### Recommended Permissions

The bot requires the following permissions:

- `Send Messages`
- `Embed Links`
- `Read Message History`
- `Manage Roles` (for role rewards)
- `Attach Files` (for rank cards)

### Environment Variables

Never store these values in version control:

```
DISCORD_BOT_TOKEN
DATABASE_URL
DASHBOARD_CLIENT_SECRET
DASHBOARD_SESSION_SECRET
```

## Disclosure Policy

We follow a coordinated disclosure process:

1. Reporter submits vulnerability privately
2. Maintainers triage and develop fix
3. Fix is tested and deployed
4. Vulnerability is publicly disclosed after fix is available

## Security-Related Configuration

See `.env.example` for all configuration options.
