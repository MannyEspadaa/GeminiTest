import express, { Request, Response } from 'express';
import { db, authenticate, canManageGame } from './phase1-auth-rbac-users';
import { syncScheduleToExternalCalendar } from './phase5-integrations-server';

export const phase3Router = express.Router();

// Read-through memory cache to guarantee < 3s response for logged-out landing calendar (NFREQ8)
let publicCalendarCache: { data: any; expiresAt: number } | null = null;
const CACHE_TTL_MS = 15_000;

function invalidateCalendarCache() {
  publicCalendarCache = null;
}

// UC-12 & NFREQ8: Public Landing Calendar & Upcoming Events (FREQ18, FREQ19, NFREQ8)
phase3Router.get('/calendar/public', async (_req: Request, res: Response) => {
  if (publicCalendarCache && Date.now() < publicCalendarCache.expiresAt) {
    return res.json(publicCalendarCache.data);
  }

  const [eventsRes, schedulesRes] = await Promise.all([
    db.query(`SELECT id, game_id, name, location, event_date, start_time, end_time FROM events WHERE end_time >= NOW() ORDER BY start_time ASC`),
    db.query(
      `SELECT gs.id, gs.game_id, g.name AS game_name, gs.title, gs.start_time, gs.end_time
       FROM game_schedules gs
       JOIN games g ON g.id = gs.game_id
       WHERE gs.visibility = 'PUBLIC' AND gs.end_time >= NOW()
       ORDER BY gs.start_time ASC`
    ),
  ]);

  const payload = {
    events: eventsRes.rows,
    schedules: schedulesRes.rows,
    message:
      eventsRes.rowCount === 0 && schedulesRes.rowCount === 0
        ? 'No scheduled events available'
        : undefined,
  };

  publicCalendarCache = { data: payload, expiresAt: Date.now() + CACHE_TTL_MS };
  return res.json(payload);
});

// FREQ38 & UC-12: Roster-Scoped Calendar View for Community Members and Players
phase3Router.get('/games/:gameId/calendar', authenticate, async (req: Request, res: Response) => {
  const { gameId } = req.params;
  const isMemberOrManager =
    req.user!.globalRole === 'ADMIN' ||
    req.user!.managedGameIds.includes(gameId) ||
    req.user!.communityGameIds.includes(gameId);

  if (!isMemberOrManager) {
    return res.status(403).json({ error: 'Join this game community or roster to access its calendar view' });
  }

  const schedulesRes = await db.query(
    `SELECT * FROM game_schedules
     WHERE game_id = $1
       AND (visibility = 'PUBLIC' OR team_id IS NULL OR team_id = ANY($2::uuid[]))
     ORDER BY start_time ASC`,
    [gameId, req.user!.playerTeamIds]
  );

  return res.json({
    gameId,
    schedules: schedulesRes.rows,
    message: schedulesRes.rowCount === 0 ? 'No scheduled events available' : undefined,
  });
});

// UC-4: Create Event (FREQ11, FREQ12, FREQ13)
phase3Router.post('/events', authenticate, async (req: Request, res: Response) => {
  const { gameId, name, location, eventDate, startTime, endTime } = req.body;

  const isAuthorized =
    req.user!.globalRole === 'ADMIN' || (gameId && canManageGame(req.user!, gameId));
  if (!isAuthorized) {
    return res.status(403).json({ error: 'Unauthorized access attempt: Game Manager or Admin permissions required' });
  }

  if (!name || !location || !eventDate || !startTime || !endTime || new Date(endTime) <= new Date(startTime)) {
    return res.status(400).json({ error: 'Invalid event information: name, location, date, and valid start/end times are required' });
  }

  const result = await db.query(
    `INSERT INTO events (game_id, name, location, event_date, start_time, end_time, created_by)
     VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *`,
    [gameId || null, name.trim(), location.trim(), eventDate, startTime, endTime, req.user!.id]
  );

  invalidateCalendarCache();
  return res.status(201).json(result.rows[0]);
});

// UC-4: Edit Event
phase3Router.put('/events/:eventId', authenticate, async (req: Request, res: Response) => {
  const existing = await db.query(`SELECT * FROM events WHERE id = $1`, [req.params.eventId]);
  if (!existing.rowCount) return res.status(404).json({ error: 'Event not found' });

  const event = existing.rows[0];
  if (req.user!.globalRole !== 'ADMIN' && (!event.game_id || !canManageGame(req.user!, event.game_id))) {
    return res.status(403).json({ error: 'Unauthorized access attempt' });
  }

  const { name, location, eventDate, startTime, endTime } = req.body;
  const result = await db.query(
    `UPDATE events SET name = $1, location = $2, event_date = $3, start_time = $4, end_time = $5
     WHERE id = $6 RETURNING *`,
    [name, location, eventDate, startTime, endTime, req.params.eventId]
  );

  invalidateCalendarCache();
  return res.json(result.rows[0]);
});

// UC-4: Delete Event (FREQ15)
phase3Router.delete('/events/:eventId', authenticate, async (req: Request, res: Response) => {
  const existing = await db.query(`SELECT * FROM events WHERE id = $1`, [req.params.eventId]);
  if (!existing.rowCount) return res.status(404).json({ error: 'Event not found' });

  const event = existing.rows[0];
  if (req.user!.globalRole !== 'ADMIN' && (!event.game_id || !canManageGame(req.user!, event.game_id))) {
    return res.status(403).json({ error: 'Unauthorized access attempt' });
  }

  await db.query(`DELETE FROM events WHERE id = $1`, [req.params.eventId]);
  invalidateCalendarCache();
  return res.json({ message: 'Event deleted successfully' });
});

// UC-5: Create Game Schedule with Conflict Detection & External Calendar Sync (FREQ16, FREQ40)
phase3Router.post('/games/:gameId/schedules', authenticate, async (req: Request, res: Response) => {
  const { gameId } = req.params;
  if (!canManageGame(req.user!, gameId)) {
    return res.status(403).json({ error: 'Unauthorized: Only assigned Game Managers or Admins can manage schedules' });
  }

  const { teamId, title, startTime, endTime, visibility, forceIgnoreConflict } = req.body;
  if (!title || !startTime || !endTime || new Date(endTime) <= new Date(startTime)) {
    return res.status(400).json({ error: 'Invalid schedule information' });
  }

  // UC-5 Extension: Schedule conflict detection
  const conflictRes = await db.query(
    `SELECT id, title, start_time, end_time FROM game_schedules
     WHERE game_id = $1 AND ($2::uuid IS NULL OR team_id = $2)
       AND start_time < $4 AND end_time > $3`,
    [gameId, teamId || null, startTime, endTime]
  );

  if (conflictRes.rowCount && conflictRes.rowCount > 0 && !forceIgnoreConflict) {
    return res.status(409).json({
      warning: 'Scheduling conflict detected with an existing schedule.',
      conflicts: conflictRes.rows,
    });
  }

  const insertRes = await db.query(
    `INSERT INTO game_schedules (game_id, team_id, title, start_time, end_time, visibility, created_by)
     VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *`,
    [gameId, teamId || null, title.trim(), startTime, endTime, visibility || 'PUBLIC', req.user!.id]
  );
  const schedule = insertRes.rows[0];
  invalidateCalendarCache();

  // UC-5 Step 6 & Extension: Update external calendar service and handle integration failure gracefully
  const syncStatus = await syncScheduleToExternalCalendar(schedule);
  return res.status(201).json({
    schedule,
    externalCalendarSync: syncStatus,
  });
});

// UC-5: Edit Game Schedule (FREQ17)
phase3Router.put('/schedules/:scheduleId', authenticate, async (req: Request, res: Response) => {
  const existing = await db.query(`SELECT * FROM game_schedules WHERE id = $1`, [req.params.scheduleId]);
  if (!existing.rowCount) return res.status(404).json({ error: 'Schedule not found' });

  const current = existing.rows[0];
  if (!canManageGame(req.user!, current.game_id)) {
    return res.status(403).json({ error: 'Unauthorized access attempt' });
  }

  const { title, startTime, endTime, visibility } = req.body;
  const updated = await db.query(
    `UPDATE game_schedules SET title = $1, start_time = $2, end_time = $3, visibility = $4, updated_at = NOW()
     WHERE id = $5 RETURNING *`,
    [title, startTime, endTime, visibility || current.visibility, req.params.scheduleId]
  );
  invalidateCalendarCache();

  const syncStatus = await syncScheduleToExternalCalendar(updated.rows[0]);
  return res.json({ schedule: updated.rows[0], externalCalendarSync: syncStatus });
});
