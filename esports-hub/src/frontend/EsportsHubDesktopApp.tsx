import React, { useEffect, useState } from 'react';

interface PublicCalendarData {
  events: Array<{ id: string; name: string; location: string; event_date: string; start_time: string; end_time: string }>;
  schedules: Array<{ id: string; game_name: string; title: string; start_time: string; end_time: string }>;
  message?: string;
}

export const EsportsHubDesktopApp: React.FC = () => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('esports_token'));
  const [activeTab, setActiveTab] = useState<'DASHBOARD' | 'CALENDAR' | 'TEAMS' | 'ANALYTICS' | 'PROFILE' | 'ADMIN'>('CALENDAR');
  const [publicCalendar, setPublicCalendar] = useState<PublicCalendarData>({ events: [], schedules: [] });
  const [dashboard, setDashboard] = useState<any>(null);
  const [profile, setProfile] = useState<any>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string>('');
  const [teamAnalytics, setTeamAnalytics] = useState<any>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');

  // Load public calendar immediately on arrival for logged-out & logged-in users (<3s SLA, NFREQ8)
  useEffect(() => {
    fetch('/api/calendar/public')
      .then((r) => r.json())
      .then(setPublicCalendar)
      .catch(() => setStatusMessage('Failed to load public calendar'));
  }, []);

  // Load authenticated dashboard and profile when logged in (UC-2, UC-3)
  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    Promise.all([
      fetch('/api/dashboard', { headers }).then((r) => r.json()),
      fetch('/api/users/me/profile', { headers }).then((r) => r.json()),
    ]).then(([dashData, profData]) => {
      setDashboard(dashData);
      setProfile(profData);
      if (dashData.accessibleTeams?.length > 0) {
        setSelectedTeamId(dashData.accessibleTeams[0].id);
      }
      setActiveTab('DASHBOARD');
    });
  }, [token]);

  const loadTeamAnalytics = async (teamId: string) => {
    if (!token || !teamId) return;
    const res = await fetch(`/api/teams/${teamId}/analytics`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      setTeamAnalytics(await res.json());
    } else {
      const err = await res.json();
      setStatusMessage(err.error || 'Access denied');
    }
  };

  return (
    <div style={{ minWidth: '1024px', maxWidth: '1440px', margin: '0 auto', padding: '24px', fontFamily: 'system-ui, sans-serif' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid #e2e8f0', paddingBottom: '16px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '24px' }}>Esports Program Central Hub</h1>
          <span style={{ fontSize: '14px', color: '#64748b' }}>
            {profile ? `Signed in as ${profile.username} (${profile.role})` : 'Public Visitor View'}
          </span>
        </div>
        <nav style={{ display: 'flex', gap: '12px' }}>
          <button onClick={() => setActiveTab('CALENDAR')}>Public Calendar & Events</button>
          {token && (
            <>
              <button onClick={() => setActiveTab('DASHBOARD')}>Dashboard</button>
              <button onClick={() => setActiveTab('TEAMS')}>Teams & Rosters</button>
              <button onClick={() => { setActiveTab('ANALYTICS'); loadTeamAnalytics(selectedTeamId); }}>VODs & Statistics</button>
              <button onClick={() => setActiveTab('PROFILE')}>My Profile</button>
              {dashboard?.roles?.globalRole === 'ADMIN' && (
                <button onClick={() => setActiveTab('ADMIN')}>Admin Console</button>
              )}
              <button onClick={() => { localStorage.removeItem('esports_token'); setToken(null); setDashboard(null); setProfile(null); setActiveTab('CALENDAR'); }}>
                Sign Out
              </button>
            </>
          )}
        </nav>
      </header>

      {statusMessage && (
        <div style={{ background: '#fef2f2', color: '#991b1b', padding: '12px', marginTop: '16px', borderRadius: '6px' }}>
          {statusMessage}
        </div>
      )}

      {/* Public Calendar Interface (NFREQ8, FREQ18, FREQ19, UC-12) */}
      {activeTab === 'CALENDAR' && (
        <section style={{ marginTop: '24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <div>
            <h2>Upcoming Program Events</h2>
            {publicCalendar.events.length === 0 ? (
              <p>No scheduled events available.</p>
            ) : (
              publicCalendar.events.map((ev) => (
                <div key={ev.id} style={{ border: '1px solid #cbd5e1', borderRadius: '8px', padding: '12px', marginBottom: '12px' }}>
                  <strong>{ev.name}</strong>
                  <div>Location: {ev.location}</div>
                  <div>{new Date(ev.start_time).toLocaleString()} – {new Date(ev.end_time).toLocaleTimeString()}</div>
                </div>
              ))
            )}
          </div>
          <div>
            <h2>Game Schedules</h2>
            {publicCalendar.schedules.length === 0 ? (
              <p>No scheduled games available.</p>
            ) : (
              publicCalendar.schedules.map((sc) => (
                <div key={sc.id} style={{ border: '1px solid #cbd5e1', borderRadius: '8px', padding: '12px', marginBottom: '12px' }}>
                  <strong>[{sc.game_name}] {sc.title}</strong>
                  <div>{new Date(sc.start_time).toLocaleString()} – {new Date(sc.end_time).toLocaleTimeString()}</div>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {/* Authenticated Landing Dashboard (FREQ10, UC-3) */}
      {activeTab === 'DASHBOARD' && dashboard && (
        <section style={{ marginTop: '24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <div>
            <h2>My Accessible Teams</h2>
            {dashboard.accessibleTeams.map((t: any) => (
              <div key={t.id} style={{ border: '1px solid #cbd5e1', padding: '12px', borderRadius: '8px', marginBottom: '8px' }}>
                <strong>{t.name}</strong> ({t.game_name}) {t.is_shell ? '— [Shell Team]' : ''}
              </div>
            ))}
          </div>
          <div>
            <h2>My Joined Game Communities</h2>
            {dashboard.joinedCommunities.map((c: any) => (
              <div key={c.id} style={{ border: '1px solid #cbd5e1', padding: '12px', borderRadius: '8px', marginBottom: '8px' }}>
                {c.name}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Team VODs & Statistics Portal (FREQ45, FREQ46, UC-13) */}
      {activeTab === 'ANALYTICS' && (
        <section style={{ marginTop: '24px' }}>
          <div style={{ marginBottom: '16px' }}>
            <label>Select Team: </label>
            <select
              value={selectedTeamId}
              onChange={(e) => { setSelectedTeamId(e.target.value); loadTeamAnalytics(e.target.value); }}
            >
              {dashboard?.accessibleTeams?.map((t: any) => (
                <option key={t.id} value={t.id}>{t.name} ({t.game_name})</option>
              ))}
            </select>
          </div>
          {teamAnalytics && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              <div>
                <h3>Team VODs</h3>
                {teamAnalytics.vods.length === 0 ? (
                  <p>{teamAnalytics.vodsMessage || 'No VODs uploaded.'}</p>
                ) : (
                  teamAnalytics.vods.map((v: any) => (
                    <div key={v.id} style={{ border: '1px solid #cbd5e1', padding: '12px', borderRadius: '8px', marginBottom: '8px' }}>
                      <strong>{v.title}</strong>
                      <div><a href={v.file_url} target="_blank" rel="noreferrer">Watch VOD ({v.mime_type})</a></div>
                    </div>
                  ))
                )}
              </div>
              <div>
                <h3>Calculated Team Statistics & Manager Comments</h3>
                {teamAnalytics.statistics.map((s: any) => (
                  <div key={s.id} style={{ border: '1px solid #cbd5e1', padding: '12px', borderRadius: '8px', marginBottom: '12px' }}>
                    <strong>{s.match_label}</strong>
                    <pre style={{ background: '#f8fafc', padding: '8px' }}>{JSON.stringify(s.calculated_metrics, null, 2)}</pre>
                    <h4>Game Manager Analysis Comments:</h4>
                    {s.manager_comments.map((c: any, idx: number) => (
                      <div key={idx} style={{ fontSize: '14px', borderLeft: '3px solid #3b82f6', paddingLeft: '8px', marginBottom: '6px' }}>
                        <strong>{c.authorUsername}:</strong> {c.text}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* User Profile & Discord Integration (FREQ6, FREQ7, FREQ8, FREQ42, UC-2, UC-11) */}
      {activeTab === 'PROFILE' && profile && (
        <section style={{ marginTop: '24px' }}>
          <h2>My Profile</h2>
          <p><strong>Full Name:</strong> {profile.full_name}</p>
          <p><strong>Username:</strong> {profile.username}</p>
          <p><strong>Institutional Email:</strong> {profile.email}</p>
          <p><strong>Discord Account:</strong> {profile.discord_username || 'Not connected'}</p>
          <h3>Joined Game Rosters</h3>
          <ul>
            {profile.joinedRosters?.map((r: any) => (
              <li key={r.team_id}>{r.team_name} — {r.game_name}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};
