/* Esports Program Central Hub Client Application */

let currentUser = null;
let authToken = localStorage.getItem('esports_token') || null;
let currentView = 'home';
let calendarFilter = 'all';
let cachedCalendarData = { events: [], schedules: [] };
let cachedGames = [];
let cachedTeams = [];
let activeAnalyticsTeamId = null;

// Initialization
document.addEventListener('DOMContentLoaded', async () => {
  await checkAuth();
  await loadGames();
  await loadCalendar();
});

// Toast System
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// API Fetch Helper
async function api(endpoint, method = 'GET', data = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  const opts = { method, headers };
  if (data && (method === 'POST' || method === 'PUT')) {
    opts.body = JSON.stringify(data);
  }
  try {
    const res = await fetch(endpoint, opts);
    const json = await res.json();
    return json;
  } catch (err) {
    console.error('API Request failed:', err);
    return { success: false, error: 'Network communication failure.' };
  }
}

// Authentication Checking
async function checkAuth() {
  if (!authToken) {
    currentUser = null;
    updateNavState();
    return;
  }
  const res = await api('/api/me');
  if (res && res.authenticated) {
    currentUser = res.user;
  } else {
    currentUser = null;
    authToken = null;
    localStorage.removeItem('esports_token');
  }
  updateNavState();
}

function updateNavState() {
  const authContainer = document.getElementById('nav-auth-container');
  const navDash = document.getElementById('nav-dashboard');
  const navTeams = document.getElementById('nav-teams');
  const navAnalytics = document.getElementById('nav-analytics');
  const navAdmin = document.getElementById('nav-admin');
  const heroJoinBtn = document.getElementById('hero-join-btn');
  const calAdminControls = document.getElementById('calendar-admin-controls');

  if (currentUser) {
    const roles = currentUser.roles || [];
    const isGM = roles.includes('game_manager');
    const isPlayer = roles.includes('player');
    const isAdmin = roles.includes('admin');

    if (heroJoinBtn) heroJoinBtn.style.display = 'none';

    // Role-dependent tab display
    navDash.style.display = 'inline-block';
    navTeams.style.display = (isGM || isPlayer || isAdmin) ? 'inline-block' : 'none';
    navAnalytics.style.display = (isGM || isPlayer || isAdmin) ? 'inline-block' : 'none';
    navAdmin.style.display = isAdmin ? 'inline-block' : 'none';

    // Calendar management controls
    if (calAdminControls) {
      calAdminControls.style.display = (isGM || isAdmin) ? 'flex' : 'none';
    }

    const primaryRole = isAdmin ? 'Admin' : (isGM ? 'Game Manager' : (isPlayer ? 'Player' : (roles.includes('community_member') ? 'Community Member' : 'Student')));
    const badgeColor = isAdmin ? 'badge-crimson' : (isGM ? 'badge-cyan' : (isPlayer ? 'badge-green' : 'badge-purple'));

    authContainer.innerHTML = `
      <div class="user-badge" onclick="openProfileModal(${currentUser.id})" title="Click to view profile">
        <div class="user-avatar">${currentUser.username.substring(0, 1).toUpperCase()}</div>
        <div>
          <span style="font-weight: 600; font-size: 0.85rem;">${currentUser.username}</span>
          <span class="badge ${badgeColor}" style="margin-left: 4px; font-size: 0.65rem;">${primaryRole}</span>
        </div>
      </div>
      <button class="btn btn-xs btn-outline" onclick="handleLogout()">Sign Out</button>
    `;

    if (currentView === 'dashboard') {
      renderDashboard();
    }
  } else {
    if (heroJoinBtn) heroJoinBtn.style.display = 'inline-block';
    navDash.style.display = 'none';
    navTeams.style.display = 'none';
    navAnalytics.style.display = 'none';
    navAdmin.style.display = 'none';
    if (calAdminControls) calAdminControls.style.display = 'none';

    authContainer.innerHTML = `
      <button class="btn btn-sm btn-outline" onclick="openLoginModal()">Sign In</button>
      <button class="btn btn-sm btn-primary" onclick="openRegisterModal()">Register</button>
    `;

    if (['dashboard', 'teams', 'analytics', 'admin'].includes(currentView)) {
      navigateTo('home');
    }
  }
}

// Navigation Router
function navigateTo(viewName) {
  currentView = viewName;

  // Toggle views
  document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
  const target = document.getElementById(`view-${viewName}`);
  if (target) target.classList.add('active');

  // Update navbar buttons
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewName);
  });

  // Load specific view data
  if (viewName === 'home') loadCalendar();
  if (viewName === 'dashboard') renderDashboard();
  if (viewName === 'games') loadGames();
  if (viewName === 'teams') loadTeams();
  if (viewName === 'analytics') loadAnalytics();
  if (viewName === 'admin') loadAdminUsers();

  // Close mobile menu if open
  document.getElementById('main-nav').classList.remove('mobile-open');
}

function toggleMobileMenu() {
  document.getElementById('main-nav').classList.toggle('mobile-open');
}

// Modal Helpers
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('active');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('active');
}

// Quick Login (Demo Switcher)
async function quickLogin(username) {
  const res = await api('/api/login', 'POST', {
    username_or_email: username,
    password: 'Password123!'
  });
  if (res.success) {
    authToken = res.token;
    currentUser = res.user;
    localStorage.setItem('esports_token', authToken);
    updateNavState();
    showToast(`Signed in as ${res.user.full_name} (${username})`, 'success');
    navigateTo('dashboard');
  } else {
    showToast(res.error || 'Quick login failed', 'error');
  }
}

// Auth Handlers
function openLoginModal() {
  closeModal('modal-register');
  closeModal('modal-verify');
  openModal('modal-login');
}

function openRegisterModal() {
  closeModal('modal-login');
  closeModal('modal-verify');
  openModal('modal-register');
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const username = document.getElementById('login-username').value;
  const password = document.getElementById('login-password').value;

  const res = await api('/api/login', 'POST', { username_or_email: username, password });
  if (res.success) {
    authToken = res.token;
    currentUser = res.user;
    localStorage.setItem('esports_token', authToken);
    closeModal('modal-login');
    updateNavState();
    showToast(`Welcome back, ${res.user.full_name}!`, 'success');
    navigateTo('dashboard');
  } else {
    showToast(res.error || 'Authentication failed', 'error');
  }
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  const full_name = document.getElementById('reg-fullname').value;
  const username = document.getElementById('reg-username').value;
  const email = document.getElementById('reg-email').value;
  const password = document.getElementById('reg-password').value;

  const res = await api('/api/register', 'POST', { full_name, username, email, password });
  if (res.success) {
    closeModal('modal-register');
    document.getElementById('verify-token-input').value = res.verification_token;
    openModal('modal-verify');
    showToast('Registration successful! Complete token verification below.', 'success');
  } else {
    showToast(res.error || 'Registration failed', 'error');
  }
}

async function handleVerifySubmit(e) {
  e.preventDefault();
  const token = document.getElementById('verify-token-input').value;
  const res = await api('/api/verify', 'POST', { token });
  if (res.success) {
    closeModal('modal-verify');
    showToast(res.message, 'success');
    openLoginModal();
  } else {
    showToast(res.error || 'Verification failed', 'error');
  }
}

async function handleLogout() {
  if (authToken) {
    await api('/api/logout', 'POST', {});
  }
  authToken = null;
  currentUser = null;
  localStorage.removeItem('esports_token');
  updateNavState();
  showToast('Logged out successfully.', 'info');
  navigateTo('home');
}

// Calendar & Events
async function loadCalendar() {
  const container = document.getElementById('calendar-feed');
  const res = await api('/api/calendar');
  if (res.success) {
    cachedCalendarData = res;
    renderCalendarFeed();

    const evCount = document.getElementById('stat-event-count');
    const scCount = document.getElementById('stat-sched-count');
    if (evCount) evCount.textContent = res.events.length;
    if (scCount) scCount.textContent = res.schedules.length;
  } else {
    container.innerHTML = `<div class="card text-center text-muted">Unable to load calendar.</div>`;
  }
}

function filterCalendar(type, pillEl) {
  calendarFilter = type;
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  if (pillEl) pillEl.classList.add('active');
  renderCalendarFeed();
}

function renderCalendarFeed() {
  const container = document.getElementById('calendar-feed');
  let items = [];

  // Map events
  cachedCalendarData.events.forEach(e => {
    items.push({
      id: e.id,
      title: e.name,
      type: 'event',
      kind: 'Event',
      date: e.date,
      start_time: e.start_time,
      end_time: e.end_time,
      venue: e.location,
      badgeClass: 'badge-cyan',
      visibility: e.visibility,
      game_name: e.game_name || 'General Campus Event',
      can_delete: (currentUser && (currentUser.roles.includes('admin') || currentUser.roles.includes('game_manager')))
    });
  });

  // Map schedules
  cachedCalendarData.schedules.forEach(s => {
    const badgeColor = s.event_type === 'match' ? 'badge-crimson' : (s.event_type === 'tournament' ? 'badge-purple' : 'badge-orange');
    items.push({
      id: s.id,
      title: s.title,
      type: s.event_type,
      kind: s.event_type.toUpperCase(),
      date: s.date,
      start_time: s.start_time,
      end_time: s.end_time,
      venue: s.location_or_venue || 'Online Arena',
      opponent: s.opponent,
      badgeClass: badgeColor,
      game_name: s.game_name,
      team_name: s.team_name,
      can_delete: (currentUser && (currentUser.roles.includes('admin') || currentUser.roles.includes('game_manager')))
    });
  });

  // Apply filter
  if (calendarFilter !== 'all') {
    items = items.filter(it => it.type === calendarFilter);
  }

  // Sort by date and start_time
  items.sort((a, b) => (a.date + a.start_time).localeCompare(b.date + b.start_time));

  if (items.length === 0) {
    container.innerHTML = `
      <div class="card text-center py-4 text-muted">
        <h3>No scheduled events or fixtures in this view.</h3>
        <p class="text-sm">Check back soon or switch filters to view all entries.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(it => {
    const d = new Date(it.date + 'T00:00:00');
    const month = d.toLocaleDateString('en-US', { month: 'short' });
    const day = d.getDate();

    return `
      <div class="feed-item">
        <div style="display: flex; align-items: center;">
          <div class="feed-date-badge">
            <div class="feed-date-day">${day}</div>
            <div class="feed-date-month">${month}</div>
          </div>
          <div class="feed-details">
            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
              <span class="badge ${it.badgeClass}">${it.kind}</span>
              <span class="badge badge-purple" style="font-size: 0.65rem;">${it.game_name}</span>
              ${it.team_name ? `<span class="badge badge-green" style="font-size: 0.65rem;">${it.team_name}</span>` : ''}
              ${it.visibility ? `<span class="text-xs text-muted">(${it.visibility})</span>` : ''}
            </div>
            <div class="feed-title mt-2">${it.title}</div>
            <div class="feed-meta">
              <span>🕒 ${it.start_time} - ${it.end_time}</span>
              <span>📍 ${it.venue}</span>
              ${it.opponent ? `<span>⚔️ Opponent: <strong>${it.opponent}</strong></span>` : ''}
            </div>
          </div>
        </div>
        ${it.can_delete ? `
          <div>
            <button class="btn btn-xs btn-danger-outline" onclick="deleteCalendarItem('${it.type}', ${it.id})">Delete</button>
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

async function deleteCalendarItem(type, id) {
  if (!confirm('Are you sure you want to delete this schedule or event item?')) return;
  const endpoint = type === 'event' ? `/api/events/${id}/delete` : `/api/schedules/${id}/delete`;
  const res = await api(endpoint, 'POST');
  if (res.success) {
    showToast(res.message, 'success');
    loadCalendar();
  } else {
    showToast(res.error || 'Failed to delete item', 'error');
  }
}

function downloadICS() {
  window.open('/api/calendar/export.ics', '_blank');
}

// Games & Rosters
async function loadGames() {
  const container = document.getElementById('games-container');
  const homeMiniList = document.getElementById('home-games-list');
  const res = await api('/api/games');

  if (res.success) {
    cachedGames = res.games;
    const countEl = document.getElementById('stat-game-count');
    if (countEl) countEl.textContent = res.games.length;

    if (homeMiniList) {
      homeMiniList.innerHTML = res.games.map(g => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid var(--border-color);">
          <span style="font-weight: 600; font-size: 0.85rem;">${g.name}</span>
          <button class="btn btn-xs btn-outline" onclick="navigateTo('games')">View Roster</button>
        </div>
      `).join('');
    }

    if (container) {
      // Fetch roster membership for logged-in user if available
      let userRosterIds = [];
      if (currentUser) {
        const prof = await api(`/api/profile/${currentUser.id}`);
        if (prof.success && prof.profile.joined_rosters) {
          userRosterIds = prof.profile.joined_rosters.map(r => r.id);
        }
      }

      container.innerHTML = res.games.map(g => {
        const isJoined = userRosterIds.includes(g.id);
        return `
          <div class="game-card">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <span class="badge badge-cyan">${g.code}</span>
                <span class="text-xs text-muted">Official Collegiate Title</span>
              </div>
              <h3 class="card-title mt-2">${g.name}</h3>
              <p class="text-sm text-secondary mt-2">${g.description}</p>
            </div>
            <div class="mt-4 pt-3 border-top" style="display: flex; gap: 0.5rem; justify-content: space-between; align-items: center;">
              <button class="btn btn-sm btn-outline" onclick="inspectRosterMembers(${g.id}, '${g.name}')">View Members</button>
              ${currentUser ? (
                isJoined ? 
                  `<button class="btn btn-sm btn-danger-outline" onclick="leaveRoster(${g.id})">Leave Roster</button>` :
                  `<button class="btn btn-sm btn-primary" onclick="joinRoster(${g.id})">Join Community</button>`
              ) : `
                <button class="btn btn-sm btn-secondary" onclick="openLoginModal()">Sign in to Join</button>
              `}
            </div>
          </div>
        `;
      }).join('');
    }
  }
}

async function joinRoster(gameId) {
  const res = await api('/api/roster/join', 'POST', { game_id: gameId });
  if (res.success) {
    showToast(res.message, 'success');
    await checkAuth();
    loadGames();
  } else {
    showToast(res.error || 'Failed to join roster', 'error');
  }
}

async function leaveRoster(gameId) {
  const res = await api('/api/roster/leave', 'POST', { game_id: gameId });
  if (res.success) {
    showToast(res.message, 'success');
    await checkAuth();
    loadGames();
  } else {
    showToast(res.error || 'Failed to leave roster', 'error');
  }
}

async function inspectRosterMembers(gameId, gameName) {
  const res = await api(`/api/roster/members/${gameId}`);
  const modal = document.getElementById('modal-profile');
  const title = document.getElementById('profile-modal-title');
  const body = document.getElementById('profile-modal-body');

  title.textContent = `${gameName} Community Roster`;

  if (res.success && res.members.length > 0) {
    body.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Member</th>
              <th>Username</th>
              <th>Discord</th>
              <th>Joined Date</th>
            </tr>
          </thead>
          <tbody>
            ${res.members.map(m => `
              <tr style="cursor: pointer;" onclick="openProfileModal(${m.id})">
                <td><strong>${m.full_name}</strong></td>
                <td>@${m.username}</td>
                <td>${m.discord_username ? `🎮 ${m.discord_username}` : '<span class="text-muted">Not linked</span>'}</td>
                <td>${m.joined_at ? m.joined_at.split(' ')[0] : 'N/A'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else {
    body.innerHTML = `<div class="text-center py-4 text-muted">No members have joined this game roster yet.</div>`;
  }
  openModal('modal-profile');
}

// Teams Management
async function loadTeams() {
  const container = document.getElementById('teams-container');
  const headerActions = document.getElementById('teams-header-actions');
  const subtitle = document.getElementById('teams-subtitle');

  if (!currentUser) return;
  const roles = currentUser.roles || [];
  const isAdmin = roles.includes('admin');
  const isGM = roles.includes('game_manager');

  subtitle.textContent = isAdmin ? 
    "Administrator view: displaying all teams across all titles." :
    (isGM ? "Game Manager view: displaying shell teams and rosters for your assigned titles." : "Player view: displaying your assigned team rosters.");

  if (isAdmin || isGM) {
    headerActions.innerHTML = `<button class="btn btn-sm btn-primary" onclick="openCreateTeamModal()">+ Create Shell Team</button>`;
  } else {
    headerActions.innerHTML = '';
  }

  const res = await api('/api/teams');
  if (res.success) {
    cachedTeams = res.teams;
    if (res.teams.length === 0) {
      container.innerHTML = `<div class="card text-center py-4 text-muted">No teams found for your role and assignments.</div>`;
      return;
    }

    container.innerHTML = res.teams.map(t => `
      <div class="team-card">
        <div>
          <div class="team-card-header">
            <div>
              <span class="badge badge-purple">${t.game_name}</span>
              <h3 class="card-title mt-2">${t.name}</h3>
            </div>
            <span class="badge badge-cyan">${t.member_count} Members</span>
          </div>
          <div class="text-xs text-muted mt-2">Created: ${t.created_at ? t.created_at.split(' ')[0] : 'N/A'}</div>
        </div>
        <div class="mt-4 pt-3 border-top" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
          <button class="btn btn-sm btn-outline" onclick="inspectTeamDetails(${t.id})">Roster & Details</button>
          ${(isAdmin || isGM) ? `
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn btn-xs btn-primary" onclick="openAddMemberModal(${t.id}, ${t.game_id})">+ Add Player</button>
              <button class="btn btn-xs btn-danger-outline" onclick="deleteTeam(${t.id})">Delete</button>
            </div>
          ` : ''}
        </div>
      </div>
    `).join('');
  }
}

function openCreateTeamModal() {
  const select = document.getElementById('team-game-select');
  select.innerHTML = cachedGames.map(g => `<option value="${g.id}">${g.name}</option>`).join('');
  openModal('modal-create-team');
}

async function handleCreateTeamSubmit(e) {
  e.preventDefault();
  const game_id = document.getElementById('team-game-select').value;
  const team_name = document.getElementById('team-name-input').value;

  const res = await api('/api/teams/create', 'POST', { game_id, team_name });
  if (res.success) {
    closeModal('modal-create-team');
    showToast(res.message, 'success');
    loadTeams();
  } else {
    showToast(res.error || 'Failed to create team', 'error');
  }
}

async function deleteTeam(teamId) {
  if (!confirm('Are you sure you want to delete this shell team?')) return;
  const res = await api(`/api/teams/${teamId}/delete`, 'POST');
  if (res.success) {
    showToast(res.message, 'success');
    loadTeams();
  } else {
    showToast(res.error || 'Failed to delete team', 'error');
  }
}

async function inspectTeamDetails(teamId) {
  const res = await api(`/api/teams/${teamId}`);
  if (!res.success) {
    showToast(res.error || 'Failed to fetch team details', 'error');
    return;
  }
  const t = res.team;
  const modal = document.getElementById('modal-profile');
  const title = document.getElementById('profile-modal-title');
  const body = document.getElementById('profile-modal-body');

  title.textContent = `${t.name} (${t.game_name})`;
  body.innerHTML = `
    <div style="margin-bottom: 1rem;">
      <h4>Assigned Roster Members</h4>
      <p class="text-sm text-muted">Athletes holding Player status for this team.</p>
    </div>
    ${t.members.length === 0 ? '<div class="text-muted text-sm">No players currently assigned to this team.</div>' : `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Athlete</th>
              <th>Username</th>
              <th>Position / Role</th>
              <th>Discord</th>
              ${t.can_manage ? '<th>Actions</th>' : ''}
            </tr>
          </thead>
          <tbody>
            ${t.members.map(m => `
              <tr>
                <td><strong>${m.full_name}</strong></td>
                <td>@${m.username}</td>
                <td><span class="badge badge-green">${m.role_in_team || 'Player'}</span></td>
                <td>${m.discord_username ? `🎮 ${m.discord_username}` : 'N/A'}</td>
                ${t.can_manage ? `
                  <td>
                    <button class="btn btn-xs btn-danger-outline" onclick="removeMemberFromTeam(${t.id}, ${m.user_id})">Remove</button>
                  </td>
                ` : ''}
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `}
  `;
  openModal('modal-profile');
}

async function openAddMemberModal(teamId, gameId) {
  document.getElementById('add-member-team-id').value = teamId;
  const userSelect = document.getElementById('add-member-user-select');

  // Fetch roster members from game community
  const res = await api(`/api/roster/members/${gameId}`);
  if (res.success && res.members.length > 0) {
    userSelect.innerHTML = res.members.map(m => `
      <option value="${m.id}">${m.full_name} (@${m.username})</option>
    `).join('');
  } else {
    userSelect.innerHTML = `<option value="">No community members in this roster</option>`;
  }
  openModal('modal-add-member');
}

async function handleAddMemberSubmit(e) {
  e.preventDefault();
  const teamId = document.getElementById('add-member-team-id').value;
  const userId = document.getElementById('add-member-user-select').value;
  const roleInTeam = document.getElementById('add-member-role-input').value;

  if (!userId) {
    showToast('Please select a member.', 'error');
    return;
  }

  const res = await api(`/api/teams/${teamId}/add_member`, 'POST', {
    user_id: userId,
    role_in_team: roleInTeam
  });

  if (res.success) {
    closeModal('modal-add-member');
    showToast(res.message, 'success');
    loadTeams();
  } else {
    showToast(res.error || 'Failed to add member', 'error');
  }
}

async function removeMemberFromTeam(teamId, userId) {
  if (!confirm('Remove athlete from this team?')) return;
  const res = await api(`/api/teams/${teamId}/remove_member`, 'POST', { user_id: userId });
  if (res.success) {
    showToast(res.message, 'success');
    closeModal('modal-profile');
    loadTeams();
  } else {
    showToast(res.error || 'Failed to remove player', 'error');
  }
}

// Analytics & VODs
async function loadAnalytics() {
  const teamSelect = document.getElementById('analytics-team-select');
  const gmControls = document.getElementById('analytics-gm-controls');

  if (!currentUser) return;
  const roles = currentUser.roles || [];
  const isGM = roles.includes('game_manager');
  const isAdmin = roles.includes('admin');

  if (gmControls) {
    gmControls.style.display = (isGM || isAdmin) ? 'flex' : 'none';
  }

  // Populate team selector
  const res = await api('/api/teams');
  if (res.success && res.teams.length > 0) {
    teamSelect.innerHTML = res.teams.map(t => `<option value="${t.id}">${t.name} (${t.game_name})</option>`).join('');
    activeAnalyticsTeamId = res.teams[0].id;
    teamSelect.value = activeAnalyticsTeamId;
    loadTeamAnalyticsData(activeAnalyticsTeamId);
  } else {
    teamSelect.innerHTML = `<option value="">No authorized teams</option>`;
  }
}

function onAnalyticsTeamChange(teamId) {
  activeAnalyticsTeamId = teamId;
  loadTeamAnalyticsData(teamId);
}

async function loadTeamAnalyticsData(teamId) {
  if (!teamId) return;

  // 1. Fetch VODs
  const vodContainer = document.getElementById('vods-list');
  const vodRes = await api(`/api/teams/${teamId}/vods`);

  if (vodRes.success) {
    if (vodRes.vods.length === 0) {
      vodContainer.innerHTML = `<div class="text-muted text-sm py-3 text-center">No VODs uploaded for this team yet.</div>`;
    } else {
      vodContainer.innerHTML = vodRes.vods.map(v => {
        // Embed YouTube video
        let embedUrl = v.youtube_url;
        if (v.youtube_url.includes('watch?v=')) {
          const vidId = v.youtube_url.split('watch?v=')[1].split('&')[0];
          embedUrl = `https://www.youtube.com/embed/${vidId}`;
        }
        return `
          <div class="vod-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
              <h4 style="font-size: 1rem;">${v.title}</h4>
              <span class="text-xs text-muted">${v.created_at ? v.created_at.split(' ')[0] : ''}</span>
            </div>
            <div class="vod-player-box">
              <iframe src="${embedUrl}" allowfullscreen loading="lazy"></iframe>
            </div>
            ${v.notes ? `<p class="text-sm text-secondary"><strong>Notes:</strong> ${v.notes}</p>` : ''}
            
            <div class="mt-2 pt-2 border-top">
              <span class="text-xs text-muted"><strong>Coaching Notes:</strong></span>
              ${v.comments && v.comments.length > 0 ? v.comments.map(c => `
                <div class="comment-bubble">
                  <strong>${c.author_name}:</strong> ${c.comment}
                </div>
              `).join('') : '<div class="text-xs text-muted">No comments yet.</div>'}

              ${(currentUser && (currentUser.roles.includes('game_manager') || currentUser.roles.includes('admin'))) ? `
                <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                  <input type="text" id="comment-vod-${v.id}" class="form-input" style="padding: 0.35rem 0.5rem; font-size: 0.8rem;" placeholder="Add coach feedback...">
                  <button class="btn btn-xs btn-primary" onclick="postVODComment(${teamId}, ${v.id})">Post</button>
                </div>
              ` : ''}
            </div>
          </div>
        `;
      }).join('');
    }
  } else {
    vodContainer.innerHTML = `<div class="text-crimson text-sm">${vodRes.error || 'Access denied'}</div>`;
  }

  // 2. Fetch CSV Datasets & Calculated Stats
  const dataContainer = document.getElementById('datasets-list');
  const statRes = await api(`/api/teams/${teamId}/stats`);

  if (statRes.success) {
    const datasets = statRes.datasets;
    if (datasets.length === 0) {
      dataContainer.innerHTML = `<div class="text-muted text-sm py-3 text-center">No performance data ingested yet.</div>`;
      resetStatCards();
    } else {
      const latest = datasets[0];
      // Update top stat cards with latest calculated dataset metrics
      document.getElementById('stat-win-rate').textContent = `${latest.win_rate}%`;
      document.getElementById('stat-record').textContent = `${latest.wins} Wins / ${latest.losses} Losses`;
      document.getElementById('stat-kd-ratio').textContent = latest.kd_ratio;
      document.getElementById('stat-total-kills').textContent = `${latest.total_kills} Kills / ${latest.total_deaths} Deaths`;
      document.getElementById('stat-avg-kills').textContent = latest.avg_kills;
      document.getElementById('stat-avg-deaths').textContent = latest.avg_deaths;

      dataContainer.innerHTML = datasets.map(d => `
        <div class="dataset-card">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="badge badge-cyan">${d.filename}</span>
            <span class="text-xs text-muted">Uploaded by ${d.uploader_name}</span>
          </div>
          <div class="mt-2 text-sm" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; background: rgba(0,0,0,0.3); padding: 0.5rem; border-radius: 4px;">
            <div>Matches: <strong>${d.total_matches}</strong></div>
            <div>Win Rate: <strong>${d.win_rate}%</strong></div>
            <div>K/D: <strong>${d.kd_ratio}</strong></div>
          </div>

          <div class="mt-2 pt-2 border-top">
            <span class="text-xs text-muted"><strong>Manager Analysis:</strong></span>
            ${d.comments && d.comments.length > 0 ? d.comments.map(c => `
              <div class="comment-bubble">
                <strong>${c.author_name}:</strong> ${c.comment}
              </div>
            `).join('') : '<div class="text-xs text-muted">No analysis comments yet.</div>'}

            ${(currentUser && (currentUser.roles.includes('game_manager') || currentUser.roles.includes('admin'))) ? `
              <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                <input type="text" id="comment-data-${d.id}" class="form-input" style="padding: 0.35rem 0.5rem; font-size: 0.8rem;" placeholder="Add team commentary...">
                <button class="btn btn-xs btn-primary" onclick="postDatasetComment(${teamId}, ${d.id})">Post</button>
              </div>
            ` : ''}
          </div>
        </div>
      `).join('');
    }
  } else {
    dataContainer.innerHTML = `<div class="text-crimson text-sm">${statRes.error || 'Access denied'}</div>`;
    resetStatCards();
  }
}

function resetStatCards() {
  document.getElementById('stat-win-rate').textContent = '--%';
  document.getElementById('stat-record').textContent = '0 Wins / 0 Losses';
  document.getElementById('stat-kd-ratio').textContent = '--';
  document.getElementById('stat-total-kills').textContent = '0 Kills / 0 Deaths';
  document.getElementById('stat-avg-kills').textContent = '--';
  document.getElementById('stat-avg-deaths').textContent = '--';
}

function openUploadVODModal() {
  document.getElementById('vod-team-id').value = activeAnalyticsTeamId;
  openModal('modal-upload-vod');
}

async function handleUploadVODSubmit(e) {
  e.preventDefault();
  const team_id = document.getElementById('vod-team-id').value;
  const title = document.getElementById('vod-title-input').value;
  const youtube_url = document.getElementById('vod-url-input').value;
  const notes = document.getElementById('vod-notes-input').value;

  const res = await api('/api/vods/upload', 'POST', { team_id, title, youtube_url, notes });
  if (res.success) {
    closeModal('modal-upload-vod');
    showToast(res.message, 'success');
    loadTeamAnalyticsData(activeAnalyticsTeamId);
  } else {
    showToast(res.error || 'VOD upload failed', 'error');
  }
}

function openUploadCSVModal() {
  document.getElementById('csv-team-id').value = activeAnalyticsTeamId;
  openModal('modal-upload-csv');
}

async function handleUploadCSVSubmit(e) {
  e.preventDefault();
  const team_id = document.getElementById('csv-team-id').value;
  const filename = document.getElementById('csv-filename-input').value;
  const csv_text = document.getElementById('csv-content-input').value;

  const res = await api('/api/stats/upload_csv', 'POST', { team_id, filename, csv_text });
  if (res.success) {
    closeModal('modal-upload-csv');
    showToast(res.message, 'success');
    loadTeamAnalyticsData(activeAnalyticsTeamId);
  } else {
    showToast(res.error || 'CSV upload failed', 'error');
  }
}

async function postVODComment(teamId, vodId) {
  const input = document.getElementById(`comment-vod-${vodId}`);
  if (!input || !input.value.trim()) return;

  const res = await api('/api/comments/create', 'POST', {
    team_id: teamId,
    vod_id: vodId,
    comment: input.value.trim()
  });

  if (res.success) {
    showToast(res.message, 'success');
    loadTeamAnalyticsData(teamId);
  } else {
    showToast(res.error || 'Failed to post comment', 'error');
  }
}

async function postDatasetComment(teamId, dataId) {
  const input = document.getElementById(`comment-data-${dataId}`);
  if (!input || !input.value.trim()) return;

  const res = await api('/api/comments/create', 'POST', {
    team_id: teamId,
    team_data_id: dataId,
    comment: input.value.trim()
  });

  if (res.success) {
    showToast(res.message, 'success');
    loadTeamAnalyticsData(teamId);
  } else {
    showToast(res.error || 'Failed to post comment', 'error');
  }
}

// Schedule & Event Modals
function openCreateScheduleModal() {
  const gameSelect = document.getElementById('sched-game-select');
  gameSelect.innerHTML = cachedGames.map(g => `<option value="${g.id}">${g.name}</option>`).join('');
  if (cachedGames.length > 0) {
    populateSchedTeamSelect(cachedGames[0].id);
  }
  openModal('modal-create-schedule');
}

function populateSchedTeamSelect(gameId) {
  const teamSelect = document.getElementById('sched-team-select');
  const matching = cachedTeams.filter(t => t.game_id == gameId);
  teamSelect.innerHTML = '<option value="">-- All / General Game Schedule --</option>' +
    matching.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
}

async function handleCreateScheduleSubmit(e) {
  e.preventDefault();
  const game_id = document.getElementById('sched-game-select').value;
  const team_id = document.getElementById('sched-team-select').value || null;
  const title = document.getElementById('sched-title-input').value;
  const event_type = document.getElementById('sched-type-select').value;
  const opponent = document.getElementById('sched-opponent-input').value;
  const date = document.getElementById('sched-date-input').value;
  const start_time = document.getElementById('sched-start-input').value;
  const end_time = document.getElementById('sched-end-input').value;
  const location_or_venue = document.getElementById('sched-venue-input').value;

  const res = await api('/api/schedules/create', 'POST', {
    game_id, team_id, title, event_type, opponent, date, start_time, end_time, location_or_venue
  });

  if (res.success) {
    closeModal('modal-create-schedule');
    showToast(res.message, 'success');
    loadCalendar();
  } else {
    if (res.conflict) {
      if (confirm(`${res.error}\n\nDo you want to override and save anyway?`)) {
        const overrideRes = await api('/api/schedules/create', 'POST', {
          game_id, team_id, title, event_type, opponent, date, start_time, end_time, location_or_venue,
          allow_conflict: true
        });
        if (overrideRes.success) {
          closeModal('modal-create-schedule');
          showToast(overrideRes.message, 'success');
          loadCalendar();
          return;
        }
      }
    }
    showToast(res.error || 'Failed to create schedule', 'error');
  }
}

function openCreateEventModal() {
  openModal('modal-create-event');
}

async function handleCreateEventSubmit(e) {
  e.preventDefault();
  const name = document.getElementById('event-name-input').value;
  const date = document.getElementById('event-date-input').value;
  const start_time = document.getElementById('event-start-input').value;
  const end_time = document.getElementById('event-end-input').value;
  const location = document.getElementById('event-location-input').value;
  const visibility = document.getElementById('event-vis-select').value;

  const res = await api('/api/events/create', 'POST', {
    name, date, start_time, end_time, location, visibility
  });

  if (res.success) {
    closeModal('modal-create-event');
    showToast(res.message, 'success');
    loadCalendar();
  } else {
    showToast(res.error || 'Failed to create event', 'error');
  }
}

// User Dashboard View (FREQ10)
async function renderDashboard() {
  if (!currentUser) return;
  document.getElementById('dash-welcome').textContent = `Welcome Back, ${currentUser.full_name}!`;
  
  const roles = currentUser.roles || [];
  const primaryRole = roles.includes('admin') ? 'Administrator' : (roles.includes('game_manager') ? 'Game Manager' : (roles.includes('player') ? 'Player' : (roles.includes('community_member') ? 'Community Member' : 'Student User')));
  document.getElementById('dash-role-badge').textContent = primaryRole;

  // 1. Fetch own profile rosters and teams
  const prof = await api(`/api/profile/${currentUser.id}`);
  const rosterDiv = document.getElementById('dash-rosters-list');
  const teamDiv = document.getElementById('dash-teams-list');

  if (prof.success) {
    const rosters = prof.profile.joined_rosters || [];
    rosterDiv.innerHTML = `
      <div class="text-xs text-muted mb-2"><strong>Joined Game Communities (${rosters.length}):</strong></div>
      ${rosters.length === 0 ? '<div class="text-sm text-muted">You have not joined any game communities yet.</div>' : `
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
          ${rosters.map(r => `<span class="badge badge-purple">${r.name}</span>`).join('')}
        </div>
      `}
    `;

    const teams = prof.profile.teams || [];
    teamDiv.innerHTML = `
      <div class="text-xs text-muted mb-2"><strong>Team Lineups (${teams.length}):</strong></div>
      ${teams.length === 0 ? '<div class="text-sm text-muted">You are not currently assigned to any shell teams.</div>' : `
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
          ${teams.map(t => `<span class="badge badge-green">${t.name} (${t.game})</span>`).join('')}
        </div>
      `}
    `;
  }

  // 2. Dashboard Upcoming Calendar items
  const schedDiv = document.getElementById('dash-schedules-list');
  const calRes = await api('/api/calendar');
  if (calRes.success) {
    const items = [...calRes.schedules, ...calRes.events].slice(0, 4);
    if (items.length === 0) {
      schedDiv.innerHTML = `<div class="text-sm text-muted">No commitments scheduled in the near term.</div>`;
    } else {
      schedDiv.innerHTML = items.map(it => `
        <div style="padding: 0.5rem 0; border-bottom: 1px solid var(--border-color);">
          <div style="font-weight: 600; font-size: 0.85rem;">${it.title || it.name}</div>
          <div class="text-xs text-muted">📅 ${it.date} (${it.start_time} - ${it.end_time})</div>
        </div>
      `).join('');
    }
  }

  // 3. Operational Action Links
  const actionDiv = document.getElementById('dash-role-actions');
  const isGM = roles.includes('game_manager');
  const isAdmin = roles.includes('admin');
  const isPlayer = roles.includes('player');

  let actionsHtml = `
    <button class="btn btn-sm btn-outline" onclick="navigateTo('games')">🎮 Browse Games & Join Rosters</button>
  `;
  if (isPlayer || isGM || isAdmin) {
    actionsHtml += `
      <button class="btn btn-sm btn-outline" onclick="navigateTo('teams')">👥 View Team Rosters</button>
      <button class="btn btn-sm btn-outline" onclick="navigateTo('analytics')">🎥 Access Team VODs & Analytics</button>
    `;
  }
  if (isGM || isAdmin) {
    actionsHtml += `
      <button class="btn btn-sm btn-primary" onclick="openCreateScheduleModal()">📅 Schedule Match / Practice</button>
      <button class="btn btn-sm btn-secondary" onclick="openCreateEventModal()">🏆 Create Program Event</button>
    `;
  }
  if (isAdmin) {
    actionsHtml += `
      <button class="btn btn-sm btn-danger" onclick="navigateTo('admin')">👑 Admin Management Console</button>
    `;
  }
  actionDiv.innerHTML = actionsHtml;
}

// Administrator User Management (FREQ32-34, FREQ36-37)
async function loadAdminUsers() {
  if (!currentUser || !currentUser.roles.includes('admin')) return;
  const tbody = document.getElementById('admin-users-body');
  const res = await api('/api/admin/users');

  if (res.success) {
    tbody.innerHTML = res.users.map(u => {
      const isSuspended = u.status === 'suspended';
      const isDeactivated = u.status === 'deactivated';
      const statusBadge = isSuspended ? 'badge-orange' : (isDeactivated ? 'badge-crimson' : 'badge-green');

      return `
        <tr>
          <td><strong>#${u.id}</strong></td>
          <td>${u.full_name}</td>
          <td>@${u.username}</td>
          <td>${u.email}</td>
          <td>${u.discord_username ? `🎮 ${u.discord_username}` : '<span class="text-muted">None</span>'}</td>
          <td>
            ${u.roles.map(r => `<span class="badge badge-purple" style="font-size: 0.65rem; margin-right: 2px;">${r}</span>`).join('')}
            ${u.assigned_games && u.assigned_games.length > 0 ? `
              <div class="text-xs text-cyan mt-1">Games: ${u.assigned_games.map(g => g.name).join(', ')}</div>
            ` : ''}
          </td>
          <td><span class="badge ${statusBadge}">${u.status}</span></td>
          <td>
            <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
              <button class="btn btn-xs btn-outline" onclick="openGrantRoleModal(${u.id}, '${u.username}')">Role</button>
              ${isSuspended ? `
                <button class="btn btn-xs btn-primary" onclick="unsuspendUser(${u.id})">Unsuspend</button>
              ` : `
                <button class="btn btn-xs btn-danger-outline" onclick="suspendUser(${u.id})">Suspend</button>
              `}
              ${!isDeactivated ? `
                <button class="btn btn-xs btn-danger-outline" onclick="removeUser(${u.id})">Remove</button>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } else {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-crimson py-4">${res.error || 'Access denied'}</td></tr>`;
  }
}

function openGrantRoleModal(userId, username) {
  document.getElementById('role-target-user-id').value = userId;
  document.getElementById('role-target-username').value = username;

  const gameSelect = document.getElementById('role-game-select');
  gameSelect.innerHTML = cachedGames.map(g => `<option value="${g.id}">${g.name}</option>`).join('');
  toggleGameAssignmentSelect('game_manager');

  openModal('modal-grant-role');
}

function toggleGameAssignmentSelect(role) {
  const group = document.getElementById('role-game-group');
  group.style.display = role === 'game_manager' ? 'block' : 'none';
}

async function handleGrantRoleSubmit(e) {
  e.preventDefault();
  const target_user_id = document.getElementById('role-target-user-id').value;
  const role = document.getElementById('role-select').value;
  const game_id = role === 'game_manager' ? document.getElementById('role-game-select').value : null;

  const res = await api('/api/admin/roles/grant', 'POST', { target_user_id, role, game_id });
  if (res.success) {
    closeModal('modal-grant-role');
    showToast(res.message, 'success');
    loadAdminUsers();
  } else {
    showToast(res.error || 'Failed to grant role', 'error');
  }
}

async function suspendUser(userId) {
  if (!confirm('Are you sure you want to suspend this user? They will not be able to log in.')) return;
  const res = await api(`/api/admin/users/${userId}/suspend`, 'POST');
  if (res.success) {
    showToast(res.message, 'success');
    loadAdminUsers();
  } else {
    showToast(res.error || 'Failed to suspend user', 'error');
  }
}

async function unsuspendUser(userId) {
  const res = await api(`/api/admin/users/${userId}/unsuspend`, 'POST');
  if (res.success) {
    showToast(res.message, 'success');
    loadAdminUsers();
  } else {
    showToast(res.error || 'Failed to lift suspension', 'error');
  }
}

async function removeUser(userId) {
  if (!confirm('Are you sure you want to deactivate/remove this account?')) return;
  const res = await api(`/api/admin/users/${userId}/remove`, 'POST');
  if (res.success) {
    showToast(res.message, 'success');
    loadAdminUsers();
  } else {
    showToast(res.error || 'Failed to remove user', 'error');
  }
}

// Profile & Discord
async function openProfileModal(userId) {
  const res = await api(`/api/profile/${userId}`);
  if (!res.success) {
    showToast(res.error || 'Failed to load profile', 'error');
    return;
  }
  const p = res.profile;
  const title = document.getElementById('profile-modal-title');
  const body = document.getElementById('profile-modal-body');

  title.textContent = p.is_own_profile ? 'My Profile' : `${p.first_name}'s Profile`;
  body.innerHTML = `
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;">
      <div class="user-avatar" style="width: 52px; height: 52px; font-size: 1.5rem;">
        ${p.username ? p.username.substring(0, 1).toUpperCase() : 'U'}
      </div>
      <div>
        <h3 style="font-size: 1.3rem;">${p.is_own_profile ? p.full_name : p.first_name}</h3>
        <div class="text-sm text-cyan">@${p.username}</div>
        ${p.is_own_profile ? `<div class="text-xs text-muted">${p.email}</div>` : ''}
      </div>
    </div>

    <div class="form-group">
      <label>Discord Tag:</label>
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <span>${p.discord_username ? `🎮 <strong>${p.discord_username}</strong>` : '<span class="text-muted">Not connected</span>'}</span>
        ${p.is_own_profile ? `<button class="btn btn-xs btn-outline" onclick="openDiscordModal()">Edit Tag</button>` : ''}
      </div>
    </div>

    <div class="form-group mt-3 pt-2 border-top">
      <label>Joined Game Rosters:</label>
      ${p.joined_rosters && p.joined_rosters.length > 0 ? `
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.35rem;">
          ${p.joined_rosters.map(r => `<span class="badge badge-purple">${r.name}</span>`).join('')}
        </div>
      ` : '<div class="text-sm text-muted">No rosters joined.</div>'}
    </div>

    <div class="form-group mt-3 pt-2 border-top">
      <label>Assigned Teams:</label>
      ${p.teams && p.teams.length > 0 ? `
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.35rem;">
          ${p.teams.map(t => `<span class="badge badge-green">${t.name} (${t.game})</span>`).join('')}
        </div>
      ` : '<div class="text-sm text-muted">No team assignments.</div>'}
    </div>
  `;
  openModal('modal-profile');
}

function openDiscordModal() {
  closeModal('modal-profile');
  if (currentUser && currentUser.discord_username) {
    document.getElementById('discord-input').value = currentUser.discord_username;
  }
  openModal('modal-discord');
}

async function handleDiscordSubmit(e) {
  e.preventDefault();
  const discord_username = document.getElementById('discord-input').value;
  const res = await api('/api/discord', 'POST', { discord_username });

  if (res.success) {
    closeModal('modal-discord');
    showToast(res.message, 'success');
    await checkAuth();
  } else {
    showToast(res.error || 'Failed to update Discord username', 'error');
  }
}
