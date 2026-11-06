import express, { Request, Response, NextFunction } from 'express';
import { Pool } from 'pg';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';

// Connection pool tuned for >= 200 concurrent users (NFREQ1)
export const db = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 50,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

const JWT_SECRET = process.env.JWT_SECRET || 'esports-hub-secret-key';
const ALLOWED_EMAIL_DOMAIN = process.env.INSTITUTION_DOMAIN || '.edu';

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  globalRole: 'USER' | 'ADMIN';
  managedGameIds: string[];
  playerTeamIds: string[];
  communityGameIds: string[];
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthUser;
    }
  }
}

// Authentication & Hierarchical RBAC Resolution Middleware (NFREQ4)
export async function authenticate(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Authentication required' });
  }

  try {
    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, JWT_SECRET) as { userId: string };

    const userRes = await db.query(
      `SELECT id, email, username, role, status, email_verified FROM users WHERE id = $1`,
      [decoded.userId]
    );
    const user = userRes.rows[0];

    if (!user || user.status !== 'ACTIVE' || !user.email_verified) {
      return res.status(403).json({ error: 'Account inactive, unverified, or suspended' });
    }

    const [gmRes, playerRes, commRes] = await Promise.all([
      db.query(`SELECT game_id FROM game_managers WHERE user_id = $1`, [user.id]),
      db.query(`SELECT team_id FROM team_rosters WHERE user_id = $1 AND status = 'APPROVED'`, [user.id]),
      db.query(`SELECT game_id FROM community_memberships WHERE user_id = $1`, [user.id]),
    ]);

    req.user = {
      id: user.id,
      email: user.email,
      username: user.username,
      globalRole: user.role,
      managedGameIds: gmRes.rows.map((r) => r.game_id),
      playerTeamIds: playerRes.rows.map((r) => r.team_id),
      communityGameIds: commRes.rows.map((r) => r.game_id),
    };
    next();
  } catch {
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
}

// Role guard helpers enforcing hierarchical & scoped permissions (NFREQ4, UC-4..UC-10, UC-13)
export function requireAdmin(req: Request, res: Response, next: NextFunction) {
  if (req.user?.globalRole !== 'ADMIN') {
    return res.status(403).json({ error: 'Administrator privileges required' });
  }
  next();
}

export function canManageGame(user: AuthUser, gameId: string): boolean {
  return user.globalRole === 'ADMIN' || user.managedGameIds.includes(gameId);
}

export async function canManageTeam(user: AuthUser, teamId: string): Promise<boolean> {
  if (user.globalRole === 'ADMIN') return true;
  const res = await db.query(`SELECT game_id FROM teams WHERE id = $1`, [teamId]);
  if (!res.rowCount) return false;
  return user.managedGameIds.includes(res.rows[0].game_id);
}

export async function canViewTeamPrivateData(user: AuthUser, teamId: string): Promise<boolean> {
  if (user.globalRole === 'ADMIN') return true;
  if (user.playerTeamIds.includes(teamId)) return true;
  return canManageTeam(user, teamId);
}

export const phase1Router = express.Router();

// UC-1: Create Account (FREQ1, FREQ4, NFREQ7)
phase1Router.post('/auth/register', async (req: Request, res: Response) => {
  const { email, fullName, username, password } = req.body;

  if (!email || !fullName || !username || !password || password.length < 8) {
    return res.status(400).json({ error: 'Incomplete or invalid registration information' });
  }
  if (!email.toLowerCase().endsWith(ALLOWED_EMAIL_DOMAIN)) {
    return res.status(400).json({ error: `Official institutional (${ALLOWED_EMAIL_DOMAIN}) email required` });
  }

  const existing = await db.query(`SELECT 1 FROM users WHERE email = $1 OR username = $2`, [
    email.toLowerCase(),
    username,
  ]);
  if (existing.rowCount && existing.rowCount > 0) {
    return res.status(409).json({ error: 'Email or username already in use. Please use a different one.' });
  }

  const passwordHash = await bcrypt.hash(password, 10);
  const verificationToken = crypto.randomBytes(32).toString('hex');
  const firstName = fullName.trim().split(' ')[0];

  const result = await db.query(
    `INSERT INTO users (email, full_name, first_name, username, password_hash, verification_token)
     VALUES ($1, $2, $3, $4, $5, $6) RETURNING id, email, username`,
    [email.toLowerCase(), fullName.trim(), firstName, username.trim(), passwordHash, verificationToken]
  );

  // Simulated email dispatch (FREQ4)
  return res.status(201).json({
    message: 'Account created. Please verify your email address.',
    user: result.rows[0],
    verificationUrl: `/api/auth/verify-email?token=${verificationToken}`,
  });
});

// Verify Email (FREQ4)
phase1Router.get('/auth/verify-email', async (req: Request, res: Response) => {
  const { token } = req.query;
  const result = await db.query(
    `UPDATE users SET email_verified = TRUE, status = 'ACTIVE', verification_token = NULL
     WHERE verification_token = $1 RETURNING id, email`,
    [token]
  );
  if (!result.rowCount) {
    return res.status(400).json({ error: 'Invalid or expired verification token' });
  }
  return res.json({ message: 'Email verified successfully. You may now log in.' });
});

// Login endpoint
phase1Router.post('/auth/login', async (req: Request, res: Response) => {
  const { email, password } = req.body;
  const result = await db.query(`SELECT * FROM users WHERE email = $1`, [email?.toLowerCase()]);
  const user = result.rows[0];

  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }
  if (!user.email_verified) {
    return res.status(403).json({ error: 'Please verify your email address before logging in' });
  }
  if (user.status !== 'ACTIVE') {
    return res.status(403).json({ error: `Account is ${user.status}` });
  }

  const token = jwt.sign({ userId: user.id }, JWT_SECRET, { expiresIn: '12h' });
  return res.json({ token, redirectTo: '/dashboard' });
});

// UC-2: View Own Profile Information (FREQ6, FREQ7, FREQ8)
phase1Router.get('/users/me/profile', authenticate, async (req: Request, res: Response) => {
  const userRes = await db.query(
    `SELECT id, full_name, username, email, discord_username, role FROM users WHERE id = $1`,
    [req.user!.id]
  );
  const rostersRes = await db.query(
    `SELECT t.id AS team_id, t.name AS team_name, g.name AS game_name
     FROM team_rosters tr
     JOIN teams t ON t.id = tr.team_id
     JOIN games g ON g.id = t.game_id
     WHERE tr.user_id = $1 AND tr.status = 'APPROVED'`,
    [req.user!.id]
  );

  return res.json({
    ...userRes.rows[0],
    joinedRosters: rostersRes.rows,
  });
});

// UC-2: View Other User's Profile (FREQ9)
phase1Router.get('/users/:username/profile', authenticate, async (req: Request, res: Response) => {
  const userRes = await db.query(
    `SELECT id, first_name, username, discord_username FROM users WHERE username = $1 AND status = 'ACTIVE'`,
    [req.params.username]
  );
  if (!userRes.rowCount) {
    return res.status(404).json({ error: 'User profile not found' });
  }
  const targetUser = userRes.rows[0];
  const rostersRes = await db.query(
    `SELECT t.id AS team_id, t.name AS team_name, g.name AS game_name
     FROM team_rosters tr
     JOIN teams t ON t.id = tr.team_id
     JOIN games g ON g.id = t.game_id
     WHERE tr.user_id = $1 AND tr.status = 'APPROVED'`,
    [targetUser.id]
  );

  return res.json({
    firstName: targetUser.first_name,
    username: targetUser.username,
    discordUsername: targetUser.discord_username,
    joinedRosters: rostersRes.rows,
  });
});

// UC-3: View Dashboard (FREQ10)
phase1Router.get('/dashboard', authenticate, async (req: Request, res: Response) => {
  const [eventsRes, myTeamsRes, communitiesRes] = await Promise.all([
    db.query(`SELECT * FROM events WHERE end_time >= NOW() ORDER BY start_time ASC LIMIT 10`),
    req.user!.globalRole === 'ADMIN'
      ? db.query(`SELECT t.*, g.name AS game_name FROM teams t JOIN games g ON g.id = t.game_id`)
      : db.query(
          `SELECT DISTINCT t.*, g.name AS game_name
           FROM teams t
           JOIN games g ON g.id = t.game_id
           LEFT JOIN team_rosters tr ON tr.team_id = t.id AND tr.status = 'APPROVED'
           WHERE tr.user_id = $1 OR t.game_id = ANY($2::uuid[])`,
          [req.user!.id, req.user!.managedGameIds]
        ),
    db.query(
      `SELECT g.id, g.name, g.slug FROM games g
       JOIN community_memberships cm ON cm.game_id = g.id WHERE cm.user_id = $1`,
      [req.user!.id]
    ),
  ]);

  return res.json({
    upcomingEvents: eventsRes.rows,
    accessibleTeams: myTeamsRes.rows,
    joinedCommunities: communitiesRes.rows,
    roles: {
      globalRole: req.user!.globalRole,
      managedGameIds: req.user!.managedGameIds,
      playerTeamIds: req.user!.playerTeamIds,
    },
  });
});

// UC-9: Manage User Roles - Grant/Revoke Game Manager & Grant Admin (FREQ32, FREQ33, FREQ34)
phase1Router.post('/admin/users/:userId/game-manager', authenticate, requireAdmin, async (req: Request, res: Response) => {
  const { gameId } = req.body;
  if (!gameId) return res.status(400).json({ error: 'gameId is required' });

  await db.query(
    `INSERT INTO game_managers (user_id, game_id, assigned_by) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING`,
    [req.params.userId, gameId, req.user!.id]
  );
  return res.json({ message: 'Game Manager role granted for specified game' });
});

phase1Router.delete('/admin/users/:userId/game-manager/:gameId', authenticate, requireAdmin, async (req: Request, res: Response) => {
  await db.query(`DELETE FROM game_managers WHERE user_id = $1 AND game_id = $2`, [
    req.params.userId,
    req.params.gameId,
  ]);
  return res.json({ message: 'Game Manager role revoked for specified game' });
});

phase1Router.post('/admin/users/:userId/grant-admin', authenticate, requireAdmin, async (req: Request, res: Response) => {
  const result = await db.query(`UPDATE users SET role = 'ADMIN', updated_at = NOW() WHERE id = $1 RETURNING id, role`, [
    req.params.userId,
  ]);
  if (!result.rowCount) return res.status(404).json({ error: 'User not found' });
  return res.json({ message: 'Administrator role granted', user: result.rows[0] });
});

// UC-10: Moderate User Accounts - Suspend & Remove (FREQ36, FREQ37)
phase1Router.patch('/admin/users/:userId/suspend', authenticate, requireAdmin, async (req: Request, res: Response) => {
  const result = await db.query(
    `UPDATE users SET status = 'SUSPENDED', updated_at = NOW() WHERE id = $1 RETURNING id, status`,
    [req.params.userId]
  );
  if (!result.rowCount) return res.status(404).json({ error: 'User not found' });
  return res.json({ message: 'User account suspended', user: result.rows[0] });
});

phase1Router.delete('/admin/users/:userId', authenticate, requireAdmin, async (req: Request, res: Response) => {
  const result = await db.query(`DELETE FROM users WHERE id = $1 RETURNING id`, [req.params.userId]);
  if (!result.rowCount) return res.status(404).json({ error: 'User not found' });
  return res.json({ message: 'User account removed' });
});
