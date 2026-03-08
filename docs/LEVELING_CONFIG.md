# Leveling Configuration Feature

This feature allows server administrators to configure the leveling system through the Miku dashboard.

## Features Implemented

### 1. **Level-Up Announcement Channel**
- Configure a specific channel for level-up messages
- If no channel is set, messages appear in the current channel where the user is chatting
- Set via dashboard or Discord command: `&setlevelchannel #channel-name`

### 2. **Role Rewards**
- Assign roles automatically when users reach specific levels
- Multiple role rewards can be configured for different levels
- Managed through the dashboard or Discord commands:
  - `&addrole <level> @role` - Add a role reward
  - `&removerole <level>` - Remove a role reward
  - `&rolerewards` - View all configured role rewards

## How to Use

### Via Dashboard

1. Navigate to your server's dashboard at `/server/{serverId}`
2. Click the "⚙️ Leveling Settings" button
3. Configure your preferences:
   - **Level-Up Channel**: Select a channel from the dropdown
   - **Role Rewards**: Add level-role pairs
4. Click "💾 Save Settings" to apply changes

### Via Discord Commands

**Set Level-Up Channel:**
```
&setlevelchannel #announcements
```

**Add Role Reward:**
```
&addrole 10 @Bronze
&addrole 25 @Silver
&addrole 50 @Gold
```

**Remove Role Reward:**
```
&removerole 10
```

**List Role Rewards:**
```
&rolerewards
```

## Database Schema

### guild_settings Table
- `guild_id` (INTEGER, PRIMARY KEY) - Discord server ID
- `levelup_channel_id` (INTEGER) - Channel ID for level-up messages
- `updated_at` (REAL) - Last update timestamp

### role_rewards Table
- `guild_id` (INTEGER) - Discord server ID
- `level` (INTEGER) - Level required
- `role_id` (INTEGER) - Role ID to assign
- PRIMARY KEY: (guild_id, level)

## Important Notes

1. **Bot Permissions**: The bot must have permission to:
   - Send messages in the configured level-up channel
   - Manage roles (assign role rewards)

2. **Role Hierarchy**: The bot's role must be positioned **higher** than the roles it needs to assign

3. **Role Rewards**: 
   - Automatically assigned when a user levels up
   - Only triggered on new level-ups (not retroactive)
   - Previous roles are NOT removed when earning new ones

4. **Changes Take Effect Immediately**: No bot restart required

## API Endpoints

### GET `/api/server/[serverId]/settings`
Fetches current guild settings including:
- Level-up channel configuration
- All role rewards with role names and colors

### POST `/api/server/[serverId]/settings`
Updates guild settings with:
- `levelupChannelId`: Channel ID or null
- `roleRewards`: Array of `{ level, roleId }` objects

### GET `/api/server/[serverId]/guild-data`
Fetches available channels and roles for the guild

## Files Modified/Created

### Bot Files
- `src/utils/database.py` - Added guild_settings and role_rewards tables + functions
- `src/cogs/leveling.py` - Updated to use settings and assign role rewards

### Dashboard Files
- `dash/src/pages/api/server/[serverId]/settings.ts` - API for settings
- `dash/src/pages/api/server/[serverId]/guild-data.ts` - API for guild data
- `dash/src/pages/server/[serverId]/settings.tsx` - Settings UI page
- `dash/src/pages/server/[serverId].tsx` - Added settings button
- `dash/src/types/index.ts` - Added new type definitions

## Testing

1. **Test Level-Up Channel**:
   - Set a channel via dashboard
   - Send messages to level up
   - Verify message appears in configured channel

2. **Test Role Rewards**:
   - Add a role reward for a low level (e.g., level 1 or 2)
   - Use `&addxp @user 1000` to quickly level up
   - Verify role is automatically assigned

3. **Test Dashboard**:
   - Open settings page
   - Add/remove role rewards
   - Change level-up channel
   - Save and verify changes persist
