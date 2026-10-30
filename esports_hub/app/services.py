import csv
import io
import re
from datetime import datetime
from app.database import get_db
from app.auth import has_role_permission

# Helper for time conflict
def times_overlap(date1, start1, end1, date2, start2, end2):
    if date1 != date2:
        return False
    # Format HH:MM
    return max(start1, start2) < min(end1, end2)

# ----------------- Profile Service -----------------
def get_user_profile(target_user_id: int, viewer: dict = None, db_path=None) -> dict:
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, username, email, discord_username, status, created_at FROM users WHERE id = ?", (target_user_id,))
    target = cur.fetchone()
    if not target:
        conn.close()
        return {"success": False, "error": "User not found."}

    # Fetch joined rosters
    cur.execute("""
        SELECT g.id, g.name, g.code
        FROM game_rosters gr
        JOIN games g ON gr.game_id = g.id
        WHERE gr.user_id = ?
    """, (target_user_id,))
    rosters = [{"id": r["id"], "name": r["name"], "code": r["code"]} for r in cur.fetchall()]

    # Fetch teams
    cur.execute("""
        SELECT t.id, t.name, g.name as game_name
        FROM team_members tm
        JOIN teams t ON tm.team_id = t.id
        JOIN games g ON t.game_id = g.id
        WHERE tm.user_id = ?
    """, (target_user_id,))
    teams = [{"id": r["id"], "name": r["name"], "game": r["game_name"]} for r in cur.fetchall()]

    is_own_profile = viewer and viewer.get("id") == target["id"]
    is_admin = viewer and "admin" in viewer.get("roles", [])

    conn.close()

    if is_own_profile or is_admin:
        # Full profile: full name, username, email, rosters, discord
        return {
            "success": True,
            "profile": {
                "id": target["id"],
                "full_name": target["full_name"],
                "first_name": target["full_name"].split()[0] if target["full_name"] else "",
                "username": target["username"],
                "email": target["email"],
                "discord_username": target["discord_username"],
                "joined_rosters": rosters,
                "teams": teams,
                "status": target["status"],
                "is_own_profile": is_own_profile
            }
        }
    else:
        # Public profile: first name, username, joined game rosters, discord name if applicable
        first_name = target["full_name"].split()[0] if target["full_name"] else ""
        return {
            "success": True,
            "profile": {
                "id": target["id"],
                "first_name": first_name,
                "username": target["username"],
                "discord_username": target["discord_username"],
                "joined_rosters": rosters,
                "teams": teams,
                "is_own_profile": False
            }
        }

def update_discord_username(user_id: int, discord_username: str, db_path=None) -> dict:
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET discord_username = ? WHERE id = ?", (discord_username.strip() if discord_username else None, user_id))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Discord username updated successfully."}


# ----------------- Game & Roster Service -----------------
def list_games(db_path=None) -> list:
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, code, description FROM games ORDER BY name ASC")
    games = [dict(r) for r in cur.fetchall()]
    conn.close()
    return games

def join_game_roster(user: dict, game_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id FROM games WHERE id = ?", (game_id,))
    if not cur.fetchone():
        conn.close()
        return {"success": False, "error": "Game not found."}

    cur.execute("SELECT id FROM game_rosters WHERE user_id = ? AND game_id = ?", (user["id"], game_id))
    if cur.fetchone():
        conn.close()
        return {"success": True, "message": "Already a member of this game roster."}

    cur.execute("INSERT INTO game_rosters (game_id, user_id) VALUES (?, ?)", (game_id, user["id"]))
    
    # Ensure role 'community_member' is present
    cur.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, 'community_member')", (user["id"],))

    conn.commit()
    conn.close()
    return {"success": True, "message": "Successfully joined the game community roster."}

def leave_game_roster(user: dict, game_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    conn = get_db(db_path)
    cur = conn.cursor()

    cur.execute("DELETE FROM game_rosters WHERE user_id = ? AND game_id = ?", (user["id"], game_id))
    
    # Check if user has any other rosters
    cur.execute("SELECT COUNT(*) as count FROM game_rosters WHERE user_id = ?", (user["id"],))
    remaining = cur.fetchone()["count"]
    if remaining == 0:
        # Check if user has team memberships
        cur.execute("SELECT COUNT(*) as count FROM team_members WHERE user_id = ?", (user["id"],))
        if cur.fetchone()["count"] == 0:
            cur.execute("DELETE FROM user_roles WHERE user_id = ? AND role = 'community_member'", (user["id"],))

    conn.commit()
    conn.close()
    return {"success": True, "message": "Successfully left the game community roster."}

def get_roster_members(game_id: int, db_path=None) -> list:
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.full_name, u.username, u.discord_username, gr.joined_at
        FROM game_rosters gr
        JOIN users u ON gr.user_id = u.id
        WHERE gr.game_id = ?
        ORDER BY gr.joined_at ASC
    """, (game_id,))
    members = [dict(r) for r in cur.fetchall()]
    conn.close()
    return members


# ----------------- Team Management Service -----------------
def is_game_manager_for_game(user: dict, game_id: int, db_path=None) -> bool:
    if not user:
        return False
    if "admin" in user.get("roles", []):
        return True
    if "game_manager" not in user.get("roles", []):
        return False
    
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM game_manager_assignments WHERE user_id = ? AND game_id = ?", (user["id"], game_id))
    allowed = cur.fetchone() is not None
    conn.close()
    return allowed

def create_shell_team(user: dict, game_id: int, team_name: str, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    if not team_name or not team_name.strip():
        return {"success": False, "error": "Team name is required."}
    if not is_game_manager_for_game(user, game_id, db_path):
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO teams (name, game_id, created_by) VALUES (?, ?, ?)", (team_name.strip(), game_id, user["id"]))
    team_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "team_id": team_id, "message": f"Shell team '{team_name.strip()}' created successfully."}

def modify_team(user: dict, team_id: int, new_name: str, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    if not new_name or not new_name.strip():
        return {"success": False, "error": "Team name cannot be blank."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    if not is_game_manager_for_game(user, team["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    cur.execute("UPDATE teams SET name = ? WHERE id = ?", (new_name.strip(), team_id))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Team modified successfully."}

def delete_shell_team(user: dict, team_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id, name FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    if not is_game_manager_for_game(user, team["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    cur.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Team '{team['name']}' deleted successfully."}

def add_player_to_team(user: dict, team_id: int, target_user_id: int, role_in_team: str = "player", db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    if not is_game_manager_for_game(user, team["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    # Verify target user exists
    cur.execute("SELECT id, full_name FROM users WHERE id = ?", (target_user_id,))
    target = cur.fetchone()
    if not target:
        conn.close()
        return {"success": False, "error": "Target user not found."}

    # Add to team
    cur.execute("""
        INSERT OR REPLACE INTO team_members (team_id, user_id, role_in_team)
        VALUES (?, ?, ?)
    """, (team_id, target_user_id, role_in_team))

    # Promote to Player role in role hierarchy
    cur.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, 'player')", (target_user_id,))
    cur.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, 'community_member')", (target_user_id,))
    
    # Also ensure user is in game community roster if not already
    cur.execute("INSERT OR IGNORE INTO game_rosters (game_id, user_id) VALUES (?, ?)", (team["game_id"], target_user_id))

    conn.commit()
    conn.close()
    return {"success": True, "message": f"User {target['full_name']} promoted and assigned to team."}

def remove_player_from_team(user: dict, team_id: int, target_user_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    if not is_game_manager_for_game(user, team["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    cur.execute("DELETE FROM team_members WHERE team_id = ? AND user_id = ?", (team_id, target_user_id))

    # Check if target user has any other teams
    cur.execute("SELECT COUNT(*) as count FROM team_members WHERE user_id = ?", (target_user_id,))
    if cur.fetchone()["count"] == 0:
        cur.execute("DELETE FROM user_roles WHERE user_id = ? AND role = 'player'", (target_user_id,))

    conn.commit()
    conn.close()
    return {"success": True, "message": "Player removed from team."}

def list_teams_for_user(user: dict, db_path=None) -> list:
    """Admin sees all teams; Game Manager sees assigned game teams; Player sees their teams."""
    if not user:
        return []
    conn = get_db(db_path)
    cur = conn.cursor()
    roles = user.get("roles", [])

    if "admin" in roles:
        cur.execute("""
            SELECT t.id, t.name, t.game_id, g.name as game_name, t.created_at,
                   (SELECT COUNT(*) FROM team_members WHERE team_id = t.id) as member_count
            FROM teams t
            JOIN games g ON t.game_id = g.id
            ORDER BY g.name ASC, t.name ASC
        """)
    elif "game_manager" in roles:
        cur.execute("""
            SELECT t.id, t.name, t.game_id, g.name as game_name, t.created_at,
                   (SELECT COUNT(*) FROM team_members WHERE team_id = t.id) as member_count
            FROM teams t
            JOIN games g ON t.game_id = g.id
            JOIN game_manager_assignments gma ON g.id = gma.game_id
            WHERE gma.user_id = ?
            ORDER BY g.name ASC, t.name ASC
        """, (user["id"],))
    else:
        # Player or member: only teams they belong to
        cur.execute("""
            SELECT t.id, t.name, t.game_id, g.name as game_name, t.created_at,
                   (SELECT COUNT(*) FROM team_members WHERE team_id = t.id) as member_count
            FROM teams t
            JOIN games g ON t.game_id = g.id
            JOIN team_members tm ON t.id = tm.team_id
            WHERE tm.user_id = ?
            ORDER BY g.name ASC, t.name ASC
        """, (user["id"],))

    teams = [dict(r) for r in cur.fetchall()]
    conn.close()
    return teams

def get_team_details(user: dict, team_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.name, t.game_id, g.name as game_name, t.created_at
        FROM teams t
        JOIN games g ON t.game_id = g.id
        WHERE t.id = ?
    """, (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    # Check permission: Admin, GM of game, or member of team
    is_admin = "admin" in user.get("roles", [])
    is_gm = is_game_manager_for_game(user, team["game_id"], db_path)
    
    cur.execute("SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?", (team_id, user["id"]))
    is_member = cur.fetchone() is not None

    if not (is_admin or is_gm or is_member):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not have access to this team."}

    cur.execute("""
        SELECT tm.user_id, u.full_name, u.username, u.discord_username, tm.role_in_team, tm.assigned_at
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        WHERE tm.team_id = ?
        ORDER BY tm.assigned_at ASC
    """, (team_id,))
    members = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {
        "success": True,
        "team": {
            "id": team["id"],
            "name": team["name"],
            "game_id": team["game_id"],
            "game_name": team["game_name"],
            "members": members,
            "can_manage": is_admin or is_gm
        }
    }


# ----------------- Events & Calendar Service -----------------
def create_event(user: dict, name: str, date: str, start_time: str, end_time: str, location: str,
                 visibility: str = "public", game_id: int = None, team_id: int = None, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    if not name or not name.strip():
        return {"success": False, "error": "Event name is required."}
    if not date or not date.strip():
        return {"success": False, "error": "Date is required."}
    if not start_time or not start_time.strip() or not end_time or not end_time.strip():
        return {"success": False, "error": "Start and end times are required."}
    if not location or not location.strip():
        return {"success": False, "error": "Location is required."}

    # Auth check: Game Manager or Admin
    roles = user.get("roles", [])
    if "admin" not in roles and "game_manager" not in roles:
        return {"success": False, "error": "Permission denied: Only Game Managers and Admins can create events."}

    if "admin" not in roles and game_id and not is_game_manager_for_game(user, game_id, db_path):
        return {"success": False, "error": "Permission denied: You are not a Game Manager for this game."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO events (name, date, start_time, end_time, location, visibility, game_id, team_id, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name.strip(), date.strip(), start_time.strip(), end_time.strip(), location.strip(), visibility, game_id, team_id, user["id"]))
    event_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "event_id": event_id, "message": "Event created successfully."}

def delete_event(user: dict, event_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    roles = user.get("roles", [])
    if "admin" not in roles and "game_manager" not in roles:
        return {"success": False, "error": "Permission denied: Only Game Managers and Admins can delete events."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM events WHERE id = ?", (event_id,))
    ev = cur.fetchone()
    if not ev:
        conn.close()
        return {"success": False, "error": "Event not found."}

    if "admin" not in roles and ev["game_id"] and not is_game_manager_for_game(user, ev["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Event deleted successfully."}

def create_schedule(user: dict, game_id: int, title: str, event_type: str, date: str, start_time: str,
                    end_time: str, team_id: int = None, location_or_venue: str = "", opponent: str = "",
                    allow_conflict: bool = False, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    if not is_game_manager_for_game(user, game_id, db_path):
        return {"success": False, "error": "Permission denied: You do not manage this game."}
    if not title or not title.strip():
        return {"success": False, "error": "Title is required."}
    if not date or not start_time or not end_time:
        return {"success": False, "error": "Date, start time, and end time are required."}

    conn = get_db(db_path)
    cur = conn.cursor()

    # Check for schedule conflicts on same game/team or venue
    cur.execute("""
        SELECT id, title, start_time, end_time, location_or_venue
        FROM schedules
        WHERE game_id = ? AND date = ?
    """, (game_id, date))
    existing = cur.fetchall()

    for item in existing:
        if times_overlap(date, start_time, end_time, date, item["start_time"], item["end_time"]):
            if not allow_conflict:
                conn.close()
                return {
                    "success": False,
                    "error": f"Scheduling conflict detected with existing schedule '{item['title']}' ({item['start_time']} - {item['end_time']}).",
                    "conflict": True,
                    "conflicting_item": dict(item)
                }

    cur.execute("""
        INSERT INTO schedules (game_id, team_id, title, event_type, date, start_time, end_time, location_or_venue, opponent, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (game_id, team_id, title.strip(), event_type.strip(), date.strip(), start_time.strip(), end_time.strip(), location_or_venue.strip(), opponent.strip(), user["id"]))
    sched_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "schedule_id": sched_id, "message": "Schedule created successfully."}

def edit_schedule(user: dict, schedule_id: int, title: str = None, event_type: str = None, date: str = None,
                  start_time: str = None, end_time: str = None, location_or_venue: str = None,
                  opponent: str = None, team_id: int = None, allow_conflict: bool = False, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        return {"success": False, "error": "Schedule not found."}

    if not is_game_manager_for_game(user, item["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    new_title = title if title is not None else item["title"]
    new_event_type = event_type if event_type is not None else item["event_type"]
    new_date = date if date is not None else item["date"]
    new_start = start_time if start_time is not None else item["start_time"]
    new_end = end_time if end_time is not None else item["end_time"]
    new_venue = location_or_venue if location_or_venue is not None else item["location_or_venue"]
    new_opp = opponent if opponent is not None else item["opponent"]
    new_team = team_id if team_id is not None else item["team_id"]

    # Conflict check
    if not allow_conflict:
        cur.execute("SELECT id, title, start_time, end_time FROM schedules WHERE game_id = ? AND date = ? AND id != ?",
                    (item["game_id"], new_date, schedule_id))
        others = cur.fetchall()
        for o in others:
            if times_overlap(new_date, new_start, new_end, new_date, o["start_time"], o["end_time"]):
                conn.close()
                return {
                    "success": False,
                    "error": f"Scheduling conflict detected with existing schedule '{o['title']}' ({o['start_time']} - {o['end_time']}).",
                    "conflict": True
                }

    cur.execute("""
        UPDATE schedules
        SET title = ?, event_type = ?, date = ?, start_time = ?, end_time = ?, location_or_venue = ?, opponent = ?, team_id = ?
        WHERE id = ?
    """, (new_title, new_event_type, new_date, new_start, new_end, new_venue, new_opp, new_team, schedule_id))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Schedule updated successfully."}

def delete_schedule(user: dict, schedule_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM schedules WHERE id = ?", (schedule_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        return {"success": False, "error": "Schedule not found."}

    if not is_game_manager_for_game(user, item["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this game."}

    cur.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Schedule deleted successfully."}

def get_visible_calendar(viewer: dict = None, db_path=None) -> dict:
    """Returns combined list of visible events and schedules based on user role and memberships."""
    conn = get_db(db_path)
    cur = conn.cursor()

    is_admin = viewer and "admin" in viewer.get("roles", [])
    user_id = viewer.get("id") if viewer else None

    # Get user roster memberships
    user_roster_game_ids = set()
    user_team_ids = set()
    user_gm_game_ids = set()

    if user_id:
        cur.execute("SELECT game_id FROM game_rosters WHERE user_id = ?", (user_id,))
        user_roster_game_ids = {r["game_id"] for r in cur.fetchall()}

        cur.execute("SELECT team_id FROM team_members WHERE user_id = ?", (user_id,))
        user_team_ids = {r["team_id"] for r in cur.fetchall()}

        cur.execute("SELECT game_id FROM game_manager_assignments WHERE user_id = ?", (user_id,))
        user_gm_game_ids = {r["game_id"] for r in cur.fetchall()}

    # 1. Fetch Events
    cur.execute("""
        SELECT e.id, e.name, e.date, e.start_time, e.end_time, e.location, e.visibility,
               e.game_id, g.name as game_name, e.team_id, t.name as team_name, 'event' as kind
        FROM events e
        LEFT JOIN games g ON e.game_id = g.id
        LEFT JOIN teams t ON e.team_id = t.id
        ORDER BY e.date ASC, e.start_time ASC
    """)
    all_events = [dict(r) for r in cur.fetchall()]

    visible_events = []
    for ev in all_events:
        if is_admin:
            visible_events.append(ev)
        elif ev["visibility"] == "public":
            visible_events.append(ev)
        elif ev["visibility"] == "roster":
            if ev["game_id"] in user_roster_game_ids or ev["game_id"] in user_gm_game_ids:
                visible_events.append(ev)
        elif ev["visibility"] == "team":
            if ev["team_id"] in user_team_ids or ev["game_id"] in user_gm_game_ids:
                visible_events.append(ev)

    # 2. Fetch Schedules
    cur.execute("""
        SELECT s.id, s.title, s.event_type, s.date, s.start_time, s.end_time,
               s.location_or_venue, s.opponent, s.game_id, g.name as game_name,
               s.team_id, t.name as team_name, 'schedule' as kind
        FROM schedules s
        JOIN games g ON s.game_id = g.id
        LEFT JOIN teams t ON s.team_id = t.id
        ORDER BY s.date ASC, s.start_time ASC
    """)
    all_schedules = [dict(r) for r in cur.fetchall()]

    visible_schedules = []
    for s in all_schedules:
        # FREQ18: All users can view game schedules.
        # FREQ38: Calendar view for game schedules to Community Members and Players within game's roster.
        # Restricted schedules (team-specific practices) scoped to team/roster
        if is_admin:
            visible_schedules.append(s)
        elif s["team_id"] is None:
            # Game level schedule: visible to all users (FREQ18)
            visible_schedules.append(s)
        else:
            # Team level schedule
            if s["team_id"] in user_team_ids or s["game_id"] in user_roster_game_ids or s["game_id"] in user_gm_game_ids:
                visible_schedules.append(s)

    conn.close()
    return {
        "success": True,
        "events": visible_events,
        "schedules": visible_schedules
    }

def export_calendar_ics(viewer: dict = None, db_path=None) -> str:
    cal_data = get_visible_calendar(viewer, db_path)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Esports Program Central Hub//Calendar Adapter//EN",
        "CALSCALE:GREGORIAN"
    ]
    for ev in cal_data["events"]:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:event-{ev['id']}@esports.hub")
        dt_start = ev['date'].replace('-', '') + 'T' + ev['start_time'].replace(':', '') + '00'
        dt_end = ev['date'].replace('-', '') + 'T' + ev['end_time'].replace(':', '') + '00'
        lines.append(f"DTSTART:{dt_start}")
        lines.append(f"DTEND:{dt_end}")
        lines.append(f"SUMMARY:{ev['name']}")
        lines.append(f"LOCATION:{ev['location']}")
        lines.append(f"DESCRIPTION:Visibility: {ev['visibility']}")
        lines.append("END:VEVENT")

    for sc in cal_data["schedules"]:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:schedule-{sc['id']}@esports.hub")
        dt_start = sc['date'].replace('-', '') + 'T' + sc['start_time'].replace(':', '') + '00'
        dt_end = sc['date'].replace('-', '') + 'T' + sc['end_time'].replace(':', '') + '00'
        lines.append(f"DTSTART:{dt_start}")
        lines.append(f"DTEND:{dt_end}")
        lines.append(f"SUMMARY:[{sc['game_name']}] {sc['title']}")
        lines.append(f"LOCATION:{sc.get('location_or_venue') or 'Online'}")
        lines.append(f"DESCRIPTION:Type: {sc['event_type']} vs {sc.get('opponent') or 'N/A'}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


# ----------------- Analytics & VOD Service -----------------
def upload_vod(user: dict, team_id: int, title: str, youtube_url: str, notes: str = "", db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    if not title or not title.strip():
        return {"success": False, "error": "VOD title is required."}
    if not youtube_url or not youtube_url.strip():
        return {"success": False, "error": "YouTube URL is required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    if not is_game_manager_for_game(user, team["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this team."}

    cur.execute("""
        INSERT INTO vods (team_id, title, youtube_url, notes, uploaded_by)
        VALUES (?, ?, ?, ?, ?)
    """, (team_id, title.strip(), youtube_url.strip(), notes.strip() if notes else "", user["id"]))
    vod_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "vod_id": vod_id, "message": "VOD uploaded successfully."}

def parse_and_upload_csv_stats(user: dict, team_id: int, filename: str, csv_text: str, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    if not csv_text or not csv_text.strip():
        return {"success": False, "error": "CSV data is empty."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    if not is_game_manager_for_game(user, team["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not manage this team."}

    # Parse CSV and calculate statistics (FREQ43)
    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        total_matches = 0
        wins = 0
        losses = 0
        total_kills = 0
        total_deaths = 0
        total_assists = 0

        for row in reader:
            total_matches += 1
            result = str(row.get("result", "") or row.get("outcome", "")).strip().upper()
            if result.startswith("W") or result == "WIN":
                wins += 1
            elif result.startswith("L") or result == "LOSS":
                losses += 1

            try:
                total_kills += int(row.get("kills", 0) or 0)
                total_deaths += int(row.get("deaths", 0) or 0)
                total_assists += int(row.get("assists", 0) or 0)
            except ValueError:
                pass

        if total_matches == 0:
            conn.close()
            return {"success": False, "error": "CSV must contain at least one valid match record."}

        win_rate = round((wins / total_matches) * 100, 1) if total_matches > 0 else 0.0
        kd_ratio = round(total_kills / max(1, total_deaths), 2)
        avg_kills = round(total_kills / total_matches, 1)
        avg_deaths = round(total_deaths / total_matches, 1)

        cur.execute("""
            INSERT INTO team_data (team_id, filename, raw_csv, total_matches, wins, losses, win_rate,
                                  total_kills, total_deaths, total_assists, kd_ratio, avg_kills, avg_deaths, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (team_id, filename or "stats.csv", csv_text, total_matches, wins, losses, win_rate,
              total_kills, total_deaths, total_assists, kd_ratio, avg_kills, avg_deaths, user["id"]))
        data_id = cur.lastrowid
        conn.commit()
        conn.close()

        return {
            "success": True,
            "data_id": data_id,
            "statistics": {
                "total_matches": total_matches,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_kills": total_kills,
                "total_deaths": total_deaths,
                "total_assists": total_assists,
                "kd_ratio": kd_ratio,
                "avg_kills": avg_kills,
                "avg_deaths": avg_deaths
            },
            "message": "Team statistics uploaded and calculated successfully."
        }
    except Exception as e:
        conn.close()
        return {"success": False, "error": f"Failed to parse CSV: {str(e)}"}

def add_analytics_comment(user: dict, team_id: int, comment: str, team_data_id: int = None, vod_id: int = None, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}
    if not comment or not comment.strip():
        return {"success": False, "error": "Comment cannot be blank."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    if not is_game_manager_for_game(user, team["game_id"], db_path):
        conn.close()
        return {"success": False, "error": "Permission denied: Only Game Managers can leave coaching comments."}

    cur.execute("""
        INSERT INTO analytics_comments (team_id, team_data_id, vod_id, author_id, comment)
        VALUES (?, ?, ?, ?, ?)
    """, (team_id, team_data_id, vod_id, user["id"], comment.strip()))
    comment_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"success": True, "comment_id": comment_id, "message": "Comment posted successfully."}

def get_team_vods(user: dict, team_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    is_admin = "admin" in user.get("roles", [])
    is_gm = is_game_manager_for_game(user, team["game_id"], db_path)

    cur.execute("SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?", (team_id, user["id"]))
    is_member = cur.fetchone() is not None

    if not (is_admin or is_gm or is_member):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not belong to this team."}

    cur.execute("""
        SELECT v.id, v.title, v.youtube_url, v.notes, v.created_at, u.full_name as uploader_name
        FROM vods v
        JOIN users u ON v.uploaded_by = u.id
        WHERE v.team_id = ?
        ORDER BY v.created_at DESC
    """, (team_id,))
    vods = [dict(r) for r in cur.fetchall()]

    # Fetch comments for each VOD
    for v in vods:
        cur.execute("""
            SELECT c.id, c.comment, c.created_at, u.full_name as author_name
            FROM analytics_comments c
            JOIN users u ON c.author_id = u.id
            WHERE c.vod_id = ?
            ORDER BY c.created_at ASC
        """, (v["id"],))
        v["comments"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {"success": True, "vods": vods, "team_name": team["name"]}

def get_team_statistics(user: dict, team_id: int, db_path=None) -> dict:
    if not user:
        return {"success": False, "error": "Authentication required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, name, game_id FROM teams WHERE id = ?", (team_id,))
    team = cur.fetchone()
    if not team:
        conn.close()
        return {"success": False, "error": "Team not found."}

    is_admin = "admin" in user.get("roles", [])
    is_gm = is_game_manager_for_game(user, team["game_id"], db_path)

    cur.execute("SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?", (team_id, user["id"]))
    is_member = cur.fetchone() is not None

    if not (is_admin or is_gm or is_member):
        conn.close()
        return {"success": False, "error": "Permission denied: You do not belong to this team."}

    cur.execute("""
        SELECT d.*, u.full_name as uploader_name
        FROM team_data d
        JOIN users u ON d.uploaded_by = u.id
        WHERE d.team_id = ?
        ORDER BY d.uploaded_at DESC
    """, (team_id,))
    datasets = [dict(r) for r in cur.fetchall()]

    # Fetch comments for datasets
    for d in datasets:
        cur.execute("""
            SELECT c.id, c.comment, c.created_at, u.full_name as author_name
            FROM analytics_comments c
            JOIN users u ON c.author_id = u.id
            WHERE c.team_data_id = ?
            ORDER BY c.created_at ASC
        """, (d["id"],))
        d["comments"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {"success": True, "datasets": datasets, "team_name": team["name"]}


# ----------------- Administrator Service -----------------
def admin_list_users(admin_user: dict, db_path=None) -> dict:
    if not admin_user or "admin" not in admin_user.get("roles", []):
        return {"success": False, "error": "Permission denied: Administrator role required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.full_name, u.username, u.email, u.status, u.is_verified, u.discord_username, u.created_at
        FROM users u
        ORDER BY u.id ASC
    """)
    users = [dict(r) for r in cur.fetchall()]

    for u in users:
        cur.execute("SELECT role FROM user_roles WHERE user_id = ?", (u["id"],))
        u["roles"] = [r["role"] for r in cur.fetchall()]

        cur.execute("""
            SELECT g.id, g.name
            FROM game_manager_assignments gma
            JOIN games g ON gma.game_id = g.id
            WHERE gma.user_id = ?
        """, (u["id"],))
        u["assigned_games"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {"success": True, "users": users}

def admin_grant_role(admin_user: dict, target_user_id: int, role: str, game_id: int = None, db_path=None) -> dict:
    if not admin_user or "admin" not in admin_user.get("roles", []):
        return {"success": False, "error": "Permission denied: Administrator role required."}

    valid_roles = ["admin", "game_manager", "player", "community_member", "user"]
    if role not in valid_roles:
        return {"success": False, "error": f"Invalid role: {role}"}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = ?", (target_user_id,))
    if not cur.fetchone():
        conn.close()
        return {"success": False, "error": "Target user not found."}

    cur.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (target_user_id, role))

    if role == "game_manager" and game_id:
        cur.execute("INSERT OR IGNORE INTO game_manager_assignments (user_id, game_id) VALUES (?, ?)", (target_user_id, game_id))

    conn.commit()
    conn.close()
    return {"success": True, "message": f"Role '{role}' successfully granted."}

def admin_revoke_role(admin_user: dict, target_user_id: int, role: str, game_id: int = None, db_path=None) -> dict:
    if not admin_user or "admin" not in admin_user.get("roles", []):
        return {"success": False, "error": "Permission denied: Administrator role required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM user_roles WHERE user_id = ? AND role = ?", (target_user_id, role))

    if role == "game_manager":
        if game_id:
            cur.execute("DELETE FROM game_manager_assignments WHERE user_id = ? AND game_id = ?", (target_user_id, game_id))
        else:
            cur.execute("DELETE FROM game_manager_assignments WHERE user_id = ?", (target_user_id,))

    conn.commit()
    conn.close()
    return {"success": True, "message": f"Role '{role}' successfully revoked."}

def admin_suspend_user(admin_user: dict, target_user_id: int, db_path=None) -> dict:
    if not admin_user or "admin" not in admin_user.get("roles", []):
        return {"success": False, "error": "Permission denied: Administrator role required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = 'suspended' WHERE id = ?", (target_user_id,))
    # Invalidate active sessions
    cur.execute("DELETE FROM sessions WHERE user_id = ?", (target_user_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "User account has been suspended."}

def admin_unsuspend_user(admin_user: dict, target_user_id: int, db_path=None) -> dict:
    if not admin_user or "admin" not in admin_user.get("roles", []):
        return {"success": False, "error": "Permission denied: Administrator role required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = 'active' WHERE id = ?", (target_user_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "User account suspension lifted."}

def admin_remove_user(admin_user: dict, target_user_id: int, db_path=None) -> dict:
    if not admin_user or "admin" not in admin_user.get("roles", []):
        return {"success": False, "error": "Permission denied: Administrator role required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET status = 'deactivated' WHERE id = ?", (target_user_id,))
    cur.execute("DELETE FROM sessions WHERE user_id = ?", (target_user_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "User account has been deactivated."}
