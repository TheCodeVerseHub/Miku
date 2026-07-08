/* Miku Dashboard — Enhanced API Client */

const API = {
    async fetch(url, opts = {}) {
        try {
            const resp = await fetch(url, {
                headers: { 'Content-Type': 'application/json', ...opts.headers },
                ...opts,
            });
            if (resp.status === 401) { window.location.href = '/auth/login'; return null; }
            if (resp.status === 403) { window.location.href = '/dashboard'; return null; }
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }
            return resp.json();
        } catch (e) {
            if (e.message !== 'Failed to fetch') showToast(e.message, 'error');
            throw e;
        }
    },

    me() { return this.fetch('/api/me'); },
    getSettings(guildId) { return this.fetch(`/api/guilds/${guildId}/settings`); },
    updateSettings(guildId, data) { return this.fetch(`/api/guilds/${guildId}/settings`, { method: 'POST', body: JSON.stringify(data) }); },
    getRewards(guildId) { return this.fetch(`/api/guilds/${guildId}/rewards`); },
    addReward(guildId, level, roleId) { return this.fetch(`/api/guilds/${guildId}/rewards`, { method: 'POST', body: JSON.stringify({ level, role_id: roleId }) }); },
    removeReward(guildId, level) { return this.fetch(`/api/guilds/${guildId}/rewards/${level}`, { method: 'DELETE' }); },
    getRoles(guildId) { return this.fetch(`/api/guilds/${guildId}/roles`); },
    getBotStats() { return this.fetch('/api/bot/stats'); },

    getLeaderboard(guildId, limit = 10, offset = 0, search = '') {
        let url = `/api/guilds/${guildId}/leaderboard?limit=${limit}&offset=${offset}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        return this.fetch(url);
    },

    getAnalytics(guildId) { return this.fetch(`/api/guilds/${guildId}/analytics`); },

    getStatsOverview(guildId) { return this.fetch(`/api/guilds/${guildId}/stats/overview`); },

    getExtendedAnalytics(guildId) { return this.fetch(`/api/guilds/${guildId}/analytics/extended`); },

    getUserHistory(guildId, userId, limit = 50, offset = 0) {
        return this.fetch(`/api/guilds/${guildId}/users/${userId}/history?limit=${limit}&offset=${offset}`);
    },

    getUserProfile(guildId, userId) { return this.fetch(`/api/guilds/${guildId}/users/${userId}`); },
    setLevel(guildId, userId, level) { return this.fetch(`/api/guilds/${guildId}/users/${userId}/setlevel`, { method: 'POST', body: JSON.stringify({ level }) }); },
    addXp(guildId, userId, amount) { return this.fetch(`/api/guilds/${guildId}/users/${userId}/addxp`, { method: 'POST', body: JSON.stringify({ amount }) }); },
    resetUser(guildId, userId) { return this.fetch(`/api/guilds/${guildId}/users/${userId}`, { method: 'DELETE' }); },
    resetAll(guildId) { return this.fetch(`/api/guilds/${guildId}/levels`, { method: 'DELETE' }); },
};

/* ─── Toast Notifications ─── */
function showToast(message, type = 'success', duration = 3500) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || ''}</span><span>${message}</span>`;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* ─── Confirmation Dialog ─── */
function confirmDialog(message, title = 'Confirm Action') {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay active';
        overlay.innerHTML = `
            <div class="modal confirm-dialog">
                <div class="icon">⚠️</div>
                <h2>${title}</h2>
                <p>${message}</p>
                <div class="modal-actions" style="justify-content: center;">
                    <button class="btn btn-ghost" id="confirm-cancel">Cancel</button>
                    <button class="btn btn-danger" id="confirm-ok">Confirm</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.querySelector('#confirm-cancel').onclick = () => { overlay.remove(); resolve(false); };
        overlay.querySelector('#confirm-ok').onclick = () => { overlay.remove(); resolve(true); };
        overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(false); } };
    });
}

/* ─── Format Helpers ─── */
function fmtNum(n) { return Number(n).toLocaleString(); }

function getAvatarColor(id) {
    let hash = 0;
    const str = String(id);
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    const colors = ['#5865f2','#ed4245','#3ecf8e','#fee75c','#eb459e','#00b0f4','#95e57a','#ff73fa','#43b581','#faa61a','#9b59b6','#1abc9c','#e91e63','#00bcd4','#ff5722','#607d8b'];
    return colors[Math.abs(hash) % colors.length];
}

function fmtDate(ts) { if (!ts) return 'N/A'; return new Date(ts).toLocaleDateString(); }
function fmtDateTime(ts) { if (!ts) return 'N/A'; return new Date(ts).toLocaleString(); }
function fmtRelative(ts) {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return fmtDate(ts);
}

function xpForLevel(lvl) {
    let total = 0;
    for (let i = 1; i <= lvl; i++) total += 5 * (i ** 2) + (50 * i) + 100;
    return total;
}

function xpPct(u) {
    const xp = u.xp || 0;
    const lvl = u.level || 0;
    const cur = xpForLevel(lvl);
    const nxt = xpForLevel(lvl + 1);
    const progress = xp - cur;
    const needed = nxt - cur;
    return needed > 0 ? Math.min(100, (progress / needed) * 100) : 0;
}

function onAvatarError(event, userId) {
    const el = event.target;
    const parent = el.parentElement;
    const initial = String(userId).charAt(0).toUpperCase();
    parent.innerHTML = `<span style="color:white;font-weight:700;font-size:14px;">${initial}</span>`;
    parent.style.background = getAvatarColor(userId);
}
