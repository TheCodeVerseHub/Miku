/* Miku Dashboard - API client */

const API = {
    async fetch(url, opts = {}) {
        const resp = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...opts.headers },
            ...opts,
        });
        if (resp.status === 401) {
            window.location.href = '/auth/login';
            return null;
        }
        if (resp.status === 403) {
            window.location.href = '/dashboard';
            return null;
        }
        return resp.json();
    },

    me() {
        return this.fetch('/api/me');
    },

    getSettings(guildId) {
        return this.fetch(`/api/guilds/${guildId}/settings`);
    },

    updateSettings(guildId, data) {
        return this.fetch(`/api/guilds/${guildId}/settings`, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    getRewards(guildId) {
        return this.fetch(`/api/guilds/${guildId}/rewards`);
    },

    addReward(guildId, level, roleId) {
        return this.fetch(`/api/guilds/${guildId}/rewards`, {
            method: 'POST',
            body: JSON.stringify({ level, role_id: roleId }),
        });
    },

    removeReward(guildId, level) {
        return this.fetch(`/api/guilds/${guildId}/rewards/${level}`, {
            method: 'DELETE',
        });
    },

    getLeaderboard(guildId, limit = 10, offset = 0, search = '') {
        let url = `/api/guilds/${guildId}/leaderboard?limit=${limit}&offset=${offset}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        return this.fetch(url);
    },

    getUserProfile(guildId, userId) {
        return this.fetch(`/api/guilds/${guildId}/users/${userId}`);
    },

    getAnalytics(guildId) {
        return this.fetch(`/api/guilds/${guildId}/analytics`);
    },

    getBotStats() {
        return this.fetch('/api/bot/stats');
    },

    setLevel(guildId, userId, level) {
        return this.fetch(`/api/guilds/${guildId}/users/${userId}/setlevel`, {
            method: 'POST',
            body: JSON.stringify({ level }),
        });
    },

    addXp(guildId, userId, amount) {
        return this.fetch(`/api/guilds/${guildId}/users/${userId}/addxp`, {
            method: 'POST',
            body: JSON.stringify({ amount }),
        });
    },

    resetUser(guildId, userId) {
        return this.fetch(`/api/guilds/${guildId}/users/${userId}`, {
            method: 'DELETE',
        });
    },

    resetAll(guildId) {
        return this.fetch(`/api/guilds/${guildId}/levels`, {
            method: 'DELETE',
        });
    },
};

/* Toast notification */
function showToast(message, type = 'success') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/* Format helpers */
function fmtNum(n) {
    return Number(n).toLocaleString();
}

function fmtDate(ts) {
    if (!ts) return 'N/A';
    return new Date(ts).toLocaleDateString();
}
