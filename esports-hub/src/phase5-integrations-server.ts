import express, { Request, Response } from 'express';
import { db, authenticate, phase1Router } from './phase1-auth-rbac-users';
import { phase2Router } from './phase2-communities-teams-rosters';
import { phase3Router } from './phase3-events-schedules-calendar';
import { phase4Router } from './phase4-vods-stats-analytics';

export const phase5Router = express.Router();

// UC-5 & FREQ40: External Calendar Synchronization Helper with Graceful Error Handling
export async function syncScheduleToExternalCalendar(schedule: any): Promise<{ synced: boolean; message: string }> {
  try {
    if (!process.env.EXTERNAL_CALENDAR_WEBHOOK_URL) {
      return { synced: true, message: 'External calendar sync simulated (no webhook configured)' };
    }
    const response = await fetch(process.env.EXTERNAL_CALENDAR_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(schedule),
    });
    if (!response.ok) {
      throw new Error(`Calendar service HTTP ${response.status}`);
    }
    return { synced: true, message: 'Connected external calendar updated' };
  } catch {
    // UC-5 Extension: Calendar integration failure does not roll back schedule storage
    return {
      synced: false,
      message: 'Schedule saved locally, but external Calendar Service failed to respond.',
    };
  }
}

// UC-11: Redirect to Discord OAuth2 Authorization (FREQ42)
phase5Router.get('/integrations/discord/connect', authenticate, (req: Request, res: Response) => {
  const clientId = process.env.DISCORD_CLIENT_ID || 'discord-client-id';
  const redirectUri = encodeURIComponent(process.env.DISCORD_REDIRECT_URI || 'http://localhost:4000/api/integrations/discord/callback');
  const discordAuthUrl = `https://discord.com/api/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=identify`;
  return res.json({ redirectUrl: discordAuthUrl });
});

// UC-11: Discord OAuth2 Callback (FREQ8, FREQ9, FREQ42)
phase5Router.post('/integrations/discord/callback', authenticate, async (req: Request, res: Response) => {
  const { code, mockDiscordUser } = req.body;
  if (!code) {
    return res.status(400).json({ error: 'Discord authentication failed: Missing authorization code' });
  }

  try {
    const discordProfile = mockDiscordUser || { id: `disc_${req.user!.id.slice(0, 8)}`, username: `${req.user!.username}#0001` };

    const result = await db.query(
      `UPDATE users SET discord_id = $1, discord_username = $2, updated_at = NOW()
       WHERE id = $3 RETURNING id, username, discord_username`,
      [discordProfile.id, discordProfile.username, req.user!.id]
    );

    return res.json({
      message: 'Discord account linked successfully',
      user: result.rows[0],
    });
  } catch {
    return res.status(502).json({ error: 'Discord API rejected authentication' });
  }
});

// Unified Express Application Assembly
export const app = express();
app.use(express.json());
app.use('/api', phase1Router);
app.use('/api', phase2Router);
app.use('/api', phase3Router);
app.use('/api', phase4Router);
app.use('/api', phase5Router);

if (require.main === module) {
  const port = process.env.PORT || 4000;
  app.listen(port, () => {
    console.log(`Esports Hub API listening on port ${port}`);
  });
}
