# Esports Program Central Hub

A full-stack TypeScript, Express, PostgreSQL, and React application built as a central hub for an esports program supporting **Users**, **Community Members**, **Players**, **Game Managers**, and **Administrators**.

## Quick Start in VS Code

1. Extract this archive and open the `esports-hub` folder directly in VS Code.
2. Copy `.env.example` to `.env` and configure your PostgreSQL connection string:
   ```bash
   cp .env.example .env
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Initialize the PostgreSQL database schema:
   ```bash
   npm run db:init
   ```
5. Start the development server (or press `F5` in VS Code to launch with the debugger):
   ```bash
   npm run dev
   ```

## Project Structure

- `db/schema.sql` — PostgreSQL schema with UUID keys, role enums, scoped memberships, and calendar indexes.
- `src/phase1-auth-rbac-users.ts` — Institutional registration, email verification, hierarchical/scoped RBAC middleware, user profiles, dashboard, and Admin moderation.
- `src/phase2-communities-teams-rosters.ts` — Game community memberships, Game Manager team management portal, shell team CRUD, and roster join/leave/promotion workflows.
- `src/phase3-events-schedules-calendar.ts` — Event CRUD, game schedule management with conflict detection, roster-scoped calendar views, and in-memory read-through caching (<3s SLA).
- `src/phase4-vods-stats-analytics.ts` — Team VOD uploads with MIME validation, per-game statistics calculation engine, manager analysis comments, and team-scoped Player analytics.
- `src/phase5-integrations-server.ts` — Discord OAuth2 linking, external calendar webhook sync with graceful fallback, and Express server entry point.
- `src/frontend/EsportsHubDesktopApp.tsx` — Desktop-first React SPA covering public calendar, dashboard, team analytics, and profile views.
- `.vscode/` — Preconfigured VS Code workspace settings and Node debugger launch configuration.
