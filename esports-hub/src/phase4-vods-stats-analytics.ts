import express, { Request, Response } from 'express';
import { db, authenticate, canManageTeam, canViewTeamPrivateData } from './phase1-auth-rbac-users';

export const phase4Router = express.Router();

const ALLOWED_VIDEO_MIME_TYPES = ['video/mp4', 'video/webm', 'video/quicktime'];

// Per-game statistics calculation engine (FREQ43)
function calculateGameStatistics(formulaType: string, rawData: Record<string, any>) {
  const matchesPlayed = Number(rawData.matchesPlayed || 1);
  const wins = Number(rawData.wins || 0);
  const kills = Number(rawData.kills || 0);
  const deaths = Math.max(1, Number(rawData.deaths || 1));
  const assists = Number(rawData.assists || 0);
  const pointsScored = Number(rawData.pointsScored || 0);
  const pointsAllowed = Number(rawData.pointsAllowed || 0);

  const winRatePct = Number(((wins / Math.max(1, matchesPlayed)) * 100).toFixed(2));

  if (formulaType === 'SPORTS') {
    return {
      winRatePct,
      avgPointsFor: Number((pointsScored / matchesPlayed).toFixed(2)),
      avgPointsAgainst: Number((pointsAllowed / matchesPlayed).toFixed(2)),
      pointDifferential: pointsScored - pointsAllowed,
    };
  }

  // Default FPS_TAC / MOBA calculations
  return {
    winRatePct,
    kdRatio: Number((kills / deaths).toFixed(2)),
    kdaRatio: Number(((kills + assists) / deaths).toFixed(2)),
    avgKillsPerMatch: Number((kills / matchesPlayed).toFixed(2)),
  };
}

// UC-8: Upload Team VOD with Format Validation (FREQ29)
phase4Router.post('/teams/:teamId/vods', authenticate, async (req: Request, res: Response) => {
  if (!(await canManageTeam(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Unauthorized team access: You do not manage this team' });
  }

  const { title, fileUrl, mimeType, fileSizeBytes } = req.body;
  if (!ALLOWED_VIDEO_MIME_TYPES.includes(mimeType)) {
    return res.status(400).json({
      error: `Unsupported file upload format (${mimeType}). Supported types: ${ALLOWED_VIDEO_MIME_TYPES.join(', ')}`,
    });
  }
  if (!title || !fileUrl) {
    return res.status(400).json({ error: 'VOD title and file URL are required' });
  }

  const result = await db.query(
    `INSERT INTO team_vods (team_id, title, file_url, mime_type, file_size_bytes, uploaded_by)
     VALUES ($1, $2, $3, $4, $5, $6) RETURNING *`,
    [req.params.teamId, title.trim(), fileUrl, mimeType, fileSizeBytes || 0, req.user!.id]
  );

  return res.status(201).json(result.rows[0]);
});

// UC-8: Upload Team Data & Calculate Game-Specific Statistics (FREQ30, FREQ43)
phase4Router.post('/teams/:teamId/statistics', authenticate, async (req: Request, res: Response) => {
  if (!(await canManageTeam(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Unauthorized team access: You do not manage this team' });
  }

  const { matchLabel, rawInputData, initialComment } = req.body;
  if (!matchLabel || !rawInputData || typeof rawInputData !== 'object') {
    return res.status(400).json({ error: 'Match label and valid rawInputData object are required' });
  }

  const gameRes = await db.query(
    `SELECT g.stat_formula_type FROM teams t JOIN games g ON g.id = t.game_id WHERE t.id = $1`,
    [req.params.teamId]
  );
  const formulaType = gameRes.rows[0]?.stat_formula_type || 'FPS_TAC';
  const calculatedMetrics = calculateGameStatistics(formulaType, rawInputData);

  const comments = initialComment
    ? [{ authorId: req.user!.id, authorUsername: req.user!.username, text: initialComment, createdAt: new Date().toISOString() }]
    : [];

  const result = await db.query(
    `INSERT INTO team_statistics (team_id, match_label, raw_input_data, calculated_metrics, manager_comments, uploaded_by)
     VALUES ($1, $2, $3, $4, $5, $6) RETURNING *`,
    [req.params.teamId, matchLabel.trim(), rawInputData, calculatedMetrics, JSON.stringify(comments), req.user!.id]
  );

  return res.status(201).json(result.rows[0]);
});

// UC-8: Analyze Uploaded Team Data by Leaving Comments for Players (FREQ31)
phase4Router.post('/teams/:teamId/statistics/:statId/comments', authenticate, async (req: Request, res: Response) => {
  if (!(await canManageTeam(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Unauthorized team access: Only the team Game Manager can add analysis comments' });
  }

  const { comment } = req.body;
  if (!comment || !comment.trim()) {
    return res.status(400).json({ error: 'Comment text is required' });
  }

  const newComment = {
    authorId: req.user!.id,
    authorUsername: req.user!.username,
    text: comment.trim(),
    createdAt: new Date().toISOString(),
  };

  const result = await db.query(
    `UPDATE team_statistics
     SET manager_comments = manager_comments || $1::jsonb
     WHERE id = $2 AND team_id = $3
     RETURNING *`,
    [JSON.stringify([newComment]), req.params.statId, req.params.teamId]
  );

  if (!result.rowCount) return res.status(404).json({ error: 'Team statistic entry not found' });
  return res.json(result.rows[0]);
});

// UC-13: Player Views Team VODs and Statistics (FREQ45, FREQ46)
phase4Router.get('/teams/:teamId/analytics', authenticate, async (req: Request, res: Response) => {
  if (!(await canViewTeamPrivateData(req.user!, req.params.teamId))) {
    return res.status(403).json({ error: 'Access denied: You are not a member or manager of this team' });
  }

  const [vodsRes, statsRes] = await Promise.all([
    db.query(`SELECT * FROM team_vods WHERE team_id = $1 ORDER BY created_at DESC`, [req.params.teamId]),
    db.query(`SELECT * FROM team_statistics WHERE team_id = $1 ORDER BY created_at DESC`, [req.params.teamId]),
  ]);

  return res.json({
    teamId: req.params.teamId,
    vods: vodsRes.rows,
    vodsMessage: vodsRes.rowCount === 0 ? 'No uploaded VODs available for this team' : undefined,
    statistics: statsRes.rows,
  });
});
