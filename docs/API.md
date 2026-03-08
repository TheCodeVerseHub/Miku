# API Documentation

This document describes the API endpoints exposed by the Miku bot.

## Base URL

Production: `https://miku-fjwa.onrender.com`  
Development: `http://localhost:8000`

## Authentication

The dashboard API uses Discord OAuth2 for authentication. Bot API endpoints are publicly accessible for read operations.

---

## Bot API Endpoints

### Server Statistics

#### `GET /api/server/{guild_id}/stats`

Get server statistics including total members, XP, and top user.

**Response:**
```json
{
  "totalMembers": 150,
  "totalXP": 25000,
  "activeUsers": 45,
  "averageLevel": 5.2,
  "topUser": {
    "userId": "123456789",
    "username": "TopUser",
    "level": 15,
    "xp": 5000
  }
}
```

### Leaderboard

#### `GET /api/server/{guild_id}/leaderboard?page=1`

Get server leaderboard with pagination.

**Query Parameters:**
- `page` (optional): Page number, default 1
- `limit` (optional): Results per page, default 50

**Response:**
```json
{
  "data": [
    {
      "rank": 1,
      "userId": "123456789",
      "username": "User#1234",
      "level": 15,
      "xp": 5000,
      "totalXp": 5000,
      "messages": 250
    }
  ],
  "page": 1,
  "totalPages": 3,
  "total": 150
}
```

### Guild Settings

#### `GET /api/server/{guild_id}/settings`

Get guild leveling settings.

**Response:**
```json
{
  "levelupChannelId": "987654321",
  "roleRewards": [
    {
      "level": 5,
      "roleId": "111222333"
    },
    {
      "level": 10,
      "roleId": "444555666"
    }
  ]
}
```

#### `POST /api/server/{guild_id}/settings`

Update guild leveling settings (requires authentication via dashboard).

**Request Body:**
```json
{
  "levelupChannelId": "987654321",
  "roleRewards": [
    {
      "level": 5,
      "roleId": "111222333"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings updated successfully"
}
```

---

## Dashboard API Endpoints

All dashboard endpoints require Discord OAuth2 authentication and proper server permissions.

### Guilds

#### `GET /api/guilds`

Get list of guilds the authenticated user can manage.

**Headers:**
- `Cookie`: Session cookie (handled automatically)

**Response:**
```json
[
  {
    "id": "123456789",
    "name": "My Server",
    "icon": "a_1234567890abcdef",
    "hasMiku": true,
    "memberCount": 150
  }
]
```

### Server Data

#### `GET /api/server/{guild_id}/guild-data`

Get guild channels and roles for configuration.

**Response:**
```json
{
  "channels": [
    {
      "id": "987654321",
      "name": "general",
      "position": 0
    }
  ],
  "roles": [
    {
      "id": "111222333",
      "name": "Level 5",
      "color": 3447003,
      "position": 5
    }
  ]
}
```

---

## Error Responses

All endpoints return standard HTTP status codes:

### 400 Bad Request
```json
{
  "error": "Invalid server ID"
}
```

### 401 Unauthorized
```json
{
  "error": "Unauthorized"
}
```

### 403 Forbidden
```json
{
  "error": "You do not have permission to manage this server"
}
```

### 404 Not Found
```json
{
  "error": "Server not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```

### 504 Gateway Timeout
```json
{
  "error": "Request timed out - API may be on cold start. Please try again."
}
```

---

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Discord API**: Follows Discord's rate limits
- **Bot API**: No strict limits, but excessive requests may be throttled
- **Dashboard API**: 100 requests per minute per user

---

## Webhooks

Currently, Miku does not support webhooks. This may be added in future versions.

---

## CORS

The API supports CORS for the dashboard:

- **Allowed Origins**: Vercel deployment domain
- **Allowed Methods**: GET, POST
- **Allowed Headers**: Content-Type, Authorization

---

## Best Practices

1. **Cache responses** when possible
2. **Handle timeouts** gracefully (cold start may take 10-30 seconds)
3. **Check HTTP status codes** before parsing responses
4. **Use pagination** for large leaderboards
5. **Respect rate limits**

---

## Support

For API issues or questions:
- GitHub Issues: [TheCodeVerseHub/Miku](https://github.com/TheCodeVerseHub/Miku/issues)
- Documentation: [/docs](../docs/)
