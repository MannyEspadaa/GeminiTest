import express, { Request, Response } from 'express';
import { db, authenticate, requireAdmin, canManageGame, canManageTeam, canViewTeamPrivateData } from './phase1-auth-rbac-users';

export const phase2Router = express.Router();

// Admin: Create Game Community (Use Case 11)
phase2Router.post('/games', authenticate, requireAdmin, async (req: Request, res: Response) => {
  const { name, slug, description, statFormulaType } = req.body;
  if (!name || !slug) return res.status(400).json({ error: 'Game name and slug are required' });

  const result = await db.query(
    `INSERT INTO games (name, slug, description, stat_formula_type) VALUES ($1, $2, $3, $4) RETURNING *`,
    [name, slug.toLowerCase(), description || '', statFormulaType || 'FPS_TAC']
  );
  return res.status(201).json(result.rows[0]);
});

// User: Join Game Community to become a Community Member (Use Case 2)
phase2Router.post('/games/:gameId/join-community', authenticate, async (req: Request, res: Response) => {
  await db.query(
    `INSERT INTO community_memberships (user_id, game_id) VALUES ($1, $2) ON CONFLICT DO NOTHING`,
    [req.user!.id, req.params.gameId]
  );
  return res.json({ message: 'Joined game community as a Community Member' });
});

// Game Manager: View Team Management Page for Assigned Game (FREQ44, Use Case 15)
phase2Router.get('/games/:gameId/team-management', authenticate, async (req: Request, res: Response) => {
  if (!canManageGame(req.user!, req.params.gameId)) {
    return res.status(403).json({ error: 'Unauthorized: You are not assigned as Game Manager for this game' });
  }

  const teamsRes = await db.query(
    `SELECT t.*,
       COALESCE(json_agg(json_build_object(
         'userId', u.id, 'username', u.username, 'status', tr.status
       )) FILTER (WHERE tr.id IS NOT NULL), '[]') AS roster_members
     FROM teams t
     LEFT JOIN team_rosters tr ON tr.team_id = t.id
     LEFT JOIN users u ON u.id = tr.user_id
     WHERE t.game_id = $1
     GROUP BY t.id`,
    [req.params.gameId]
  );

  return res.json({ gameId: req.params.gameId, teams: teamsRes.rows });
});

// UC-7: Create Shell Team (FREQ26)
phase2Router.post('/games/:gameId/teams', authenticate, async (req: Request, res: Response) => {
  if (!canManageGame(req.user!, req.params.gameId)) {
    return res.status(403).json({ error: 'Unauthorized game management attempt' });
  }

  const { name, maxCapacity } = req.body;
  if (!name || !name.trim()) {
    return res.status(400).json({ error: 'Invalid team information: Team name is required' });
  }

  const result = await db.query(
    `INSERT INTO teams (game_id, name, max_capacity, is_shell, created_by)
     VALUES ($1, $2, $3, TRUE, $4) RETURNING *`,
    [req.params.gameId, name.trim(), maxCapacity || 10, req.user!.id]
  );
  return res.status(201).json(result.rows[0]);
});

// UC-7: Modify Team (FREQ27)
phase2Router.put('/teams/:teamId', authenticate, async (req: Request, res: Response) => {
  if (!(await canManageTeam(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Unauthorized game management attempt' });
  }

  const { name, maxCapacity, isShell } = req.body;
  if (!name || !name.trim()) {
    return res.status(400).json({ error: 'Invalid team information: Team name is required' });
  }

  const result = await db.query(
    `UPDATE teams SET name = $1, max_capacity = COALESCE($2, max_capacity), is_shell = COALESCE($3, is_shell)
     WHERE id = $4 RETURNING *`,
    [name.trim(), maxCapacity, isShell, req.params.teamId]
  );
  return res.json(result.rows[0]);
});

// UC-7: Delete Shell Team (FREQ28)
phase2Router.delete('/teams/:teamId', authenticate, async (req: Request, res: Response) => {
  if (!(await canManageTeam(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Unauthorized game management attempt' });
  }

  const result = await db.query(`DELETE FROM teams WHERE id = $1 AND is_shell = TRUE RETURNING id`, [
    req.params.teamId,
  ]);
  if (!result.rowCount) {
    return res.status(400).json({ error: 'Team not found or is no longer a shell team' });
  }
  return res.json({ message: 'Shell team deleted successfully' });
});

// View Team Information & Roster (Use Case 14, Use Case 15, userContext visibility rules)
phase2Router.get('/teams/:teamId', authenticate, async (req: Request, res: Response) => {
  if (!(await canViewTeamPrivateData(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Access denied: You can only view teams you belong to or manage' });
  }

  const [teamRes, rosterRes] = await Promise.all([
    db.query(`SELECT * FROM teams WHERE id = $1`, [req.params.teamId]),
    db.query(
      `SELECT u.id, u.username, u.full_name, u.discord_username, tr.status
       FROM team_rosters tr JOIN users u ON u.id = tr.user_id
       WHERE tr.team_id = $1 AND tr.status = 'APPROVED'`,
      [req.params.teamId]
    ),
  ]);

  return res.json({ team: teamRes.rows[0], roster: rosterRes.rows });
});

// UC-6: Community Member Requests to Join Roster (FREQ20)
phase2Router.post('/teams/:teamId/roster/join', authenticate, async (req: Request, res: Response) => {
  const teamRes = await db.query(`SELECT id, game_id, max_capacity FROM teams WHERE id = $1`, [req.params.teamId]);
  if (!teamRes.rowCount) return res.status(404).json({ error: 'Team not found' });
  const team = teamRes.rows[0];

  // Precondition: User must belong to the game's community
  if (!req.user!.communityGameIds.includes(team.game_id) && req.user!.globalRole !== 'ADMIN') {
    return res.status(403).json({ error: 'You must join this game community before requesting to join its team roster' });
  }

  // Extension: Check if roster capacity is reached
  const countRes = await db.query(
    `SELECT COUNT(*)::int AS active_count FROM team_rosters WHERE team_id = $1 AND status = 'APPROVED'`,
    [team.id]
  );
  if (countRes.rows[0].active_count >= team.max_capacity) {
    return res.status(409).json({ error: 'Roster capacity reached. Request denied.' });
  }

  const result = await db.query(
    `INSERT INTO team_rosters (team_id, user_id, status)
     VALUES ($1, $2, 'PENDING')
     ON CONFLICT (team_id, user_id) DO UPDATE SET status = 'PENDING', updated_at = NOW()
     RETURNING *`,
    [team.id, req.user!.id]
  );

  return res.status(201).json({ message: 'Roster join request submitted for Game Manager approval', request: result.rows[0] });
});

// UC-6 & Use Case 5: Game Manager Approves Roster Request / Promotes Community Member to Player
phase2Router.patch('/teams/:teamId/roster/:userId/approve', authenticate, async (req: Request, res: Response) => {
  if (!(await canManageTeam(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Unauthorized: Only the assigned Game Manager or Admin can approve roster changes' });
  }

  const teamRes = await db.query(`SELECT max_capacity FROM teams WHERE id = $1`, [req.params.teamId]);
  const countRes = await db.query(
    `SELECT COUNT(*)::int AS active_count FROM team_rosters WHERE team_id = $1 AND status = 'APPROVED'`,
    [req.params.teamId]
  );
  if (countRes.rows[0].active_count >= teamRes.rows[0].max_capacity) {
    return res.status(409).json({ error: 'Roster capacity reached' });
  }

  // Approve membership & transition team out of shell state once populated
  const result = await db.query(
    `UPDATE team_rosters SET status = 'APPROVED', approved_by = $1, updated_at = NOW()
     WHERE team_id = $2 AND user_id = $3 RETURNING *`,
    [req.user!.id, req.params.teamId, req.params.userId]
  );
  await db.query(`UPDATE teams SET is_shell = FALSE WHERE id = $1`, [req.params.teamId]);

  return res.json({
    message: 'Community Member approved on team roster and promoted to Player for this team',
    membership: result.rows[0],
  });
});

// UC-6: Community Member / Player Leaves Roster (FREQ22)
phase2Router.post('/teams/:teamId/roster/leave', authenticate, async (req: Request, res: Response) => {
  const result = await db.query(
    `UPDATE team_rosters SET status = 'LEFT', updated_at = NOW()
     WHERE team_id = $1 AND user_id = $2 RETURNING *`,
    [req.params.teamId, req.user!.id]
  );
  if (!result.rowCount) return res.status(404).json({ error: 'Active roster membership not found' });
  return res.json({ message: 'Successfully left the team roster' });
});
