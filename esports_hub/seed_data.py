import os
import sys
from app.database import init_db, get_db
from app.auth import hash_password

def seed(db_path=None):
    init_db(db_path)
    conn = get_db(db_path)
    cur = conn.cursor()

    # Check if already seeded
    cur.execute("SELECT COUNT(*) as count FROM games")
    if cur.fetchone()["count"] > 0:
        print("Database already contains data.")
        conn.close()
        return

    print("Seeding Esports Program Central Hub database...")

    # 1. Games
    games_data = [
        ("Valorant", "VAL", "5v5 tactical hero shooter developed by Riot Games."),
        ("League of Legends", "LOL", "Multiplayer online battle arena (MOBA) game."),
        ("Rocket League", "RL", "High-powered vehicular soccer developed by Psyonix."),
        ("Overwatch 2", "OW2", "Team-based hero shooter by Blizzard Entertainment.")
    ]
    cur.executemany("INSERT INTO games (name, code, description) VALUES (?, ?, ?)", games_data)

    cur.execute("SELECT id, name FROM games")
    games_dict = {r["name"]: r["id"] for r in cur.fetchall()}

    # 2. Users across all 5 roles
    users_data = [
        ("System Administrator", "admin", "admin@esports.edu", "Password123!", "active", 1, "Admin#0001"),
        ("Marcus Vance", "val_manager", "marcus.vance@esports.edu", "Password123!", "active", 1, "MarcusV#1337"),
        ("Sarah Jenkins", "lol_manager", "sarah.jenkins@esports.edu", "Password123!", "active", 1, "SarahJ#4040"),
        ("Derek Frost", "ace_duelist", "derek.frost@esports.edu", "Password123!", "active", 1, "Frostbite#9999"),
        ("Elena Rostova", "shadow_mid", "elena.rostova@esports.edu", "Password123!", "active", 1, "ElenaMid#1111"),
        ("Alex Rivera", "alex_fan", "alex.rivera@esports.edu", "Password123!", "active", 1, "AlexR#2222"),
        ("Jordan Hayes", "jordan_new", "jordan.hayes@esports.edu", "Password123!", "active", 1, None),
        ("Suspended User", "toxic_player", "toxic@esports.edu", "Password123!", "suspended", 1, "Banned#6666")
    ]

    user_ids = {}
    for full_name, username, email, pwd, status, is_verified, discord in users_data:
        p_hash, p_salt = hash_password(pwd)
        cur.execute("""
            INSERT INTO users (full_name, username, email, password_hash, password_salt, is_verified, status, discord_username)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (full_name, username, email, p_hash, p_salt, is_verified, status, discord))
        user_ids[username] = cur.lastrowid

    # 3. Roles
    # Base user role for all
    for uid in user_ids.values():
        cur.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, 'user')", (uid,))

    # Admin
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'admin')", (user_ids["admin"],))

    # Game Managers
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'game_manager')", (user_ids["val_manager"],))
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'player')", (user_ids["val_manager"],))
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'community_member')", (user_ids["val_manager"],))
    cur.execute("INSERT INTO game_manager_assignments (user_id, game_id) VALUES (?, ?)", (user_ids["val_manager"], games_dict["Valorant"]))

    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'game_manager')", (user_ids["lol_manager"],))
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'player')", (user_ids["lol_manager"],))
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'community_member')", (user_ids["lol_manager"],))
    cur.execute("INSERT INTO game_manager_assignments (user_id, game_id) VALUES (?, ?)", (user_ids["lol_manager"], games_dict["League of Legends"]))

    # Players
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'player')", (user_ids["ace_duelist"],))
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'community_member')", (user_ids["ace_duelist"],))

    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'player')", (user_ids["shadow_mid"],))
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'community_member')", (user_ids["shadow_mid"],))

    # Community Member
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'community_member')", (user_ids["alex_fan"],))

    # 4. Game Rosters
    cur.execute("INSERT INTO game_rosters (game_id, user_id) VALUES (?, ?)", (games_dict["Valorant"], user_ids["ace_duelist"]))
    cur.execute("INSERT INTO game_rosters (game_id, user_id) VALUES (?, ?)", (games_dict["Valorant"], user_ids["alex_fan"]))
    cur.execute("INSERT INTO game_rosters (game_id, user_id) VALUES (?, ?)", (games_dict["League of Legends"], user_ids["shadow_mid"]))
    cur.execute("INSERT INTO game_rosters (game_id, user_id) VALUES (?, ?)", (games_dict["Rocket League"], user_ids["alex_fan"]))

    # 5. Teams
    cur.execute("""
        INSERT INTO teams (name, game_id, created_by)
        VALUES ('Valorant Varsity', ?, ?)
    """, (games_dict["Valorant"], user_ids["val_manager"]))
    val_team_id = cur.lastrowid

    cur.execute("""
        INSERT INTO teams (name, game_id, created_by)
        VALUES ('Valorant Academy', ?, ?)
    """, (games_dict["Valorant"], user_ids["val_manager"]))
    val_acad_id = cur.lastrowid

    cur.execute("""
        INSERT INTO teams (name, game_id, created_by)
        VALUES ('LoL Varsity', ?, ?)
    """, (games_dict["League of Legends"], user_ids["lol_manager"]))
    lol_team_id = cur.lastrowid

    # 6. Team Members
    cur.execute("INSERT INTO team_members (team_id, user_id, role_in_team) VALUES (?, ?, 'Captain')", (val_team_id, user_ids["ace_duelist"]))
    cur.execute("INSERT INTO team_members (team_id, user_id, role_in_team) VALUES (?, ?, 'Mid Laner')", (lol_team_id, user_ids["shadow_mid"]))

    # 7. Events
    cur.execute("""
        INSERT INTO events (name, date, start_time, end_time, location, visibility, game_id, team_id, created_by)
        VALUES
        ('Campus Fall Esports Invitational', '2026-11-15', '13:00', '18:00', 'Campus Arena Hall B', 'public', ?, ?, ?),
        ('Valorant Community Scrim Night', '2026-11-08', '19:00', '21:30', 'Discord Voice & Custom Lobbies', 'roster', ?, NULL, ?),
        ('Valorant Varsity Strategic Review', '2026-11-05', '18:00', '19:30', 'Esports Lab Room 204', 'team', ?, ?, ?)
    """, (games_dict["Valorant"], val_team_id, user_ids["admin"],
          games_dict["Valorant"], user_ids["val_manager"],
          games_dict["Valorant"], val_team_id, user_ids["val_manager"]))

    # 8. Schedules
    cur.execute("""
        INSERT INTO schedules (game_id, team_id, title, event_type, date, start_time, end_time, location_or_venue, opponent, created_by)
        VALUES
        (?, ?, 'Collegiate League Match #1', 'match', '2026-11-12', '19:00', '21:00', 'Main Stage / Twitch Stream', 'Rutgers Scarlet', ?),
        (?, ?, 'Tactical Map Practice (Bind & Ascent)', 'practice', '2026-11-10', '18:00', '20:00', 'Esports Training Facility', NULL, ?),
        (?, ?, 'Eastern Regional Qualifier', 'tournament', '2026-11-20', '14:00', '18:00', 'Online Tournament Server', 'Rowan University', ?)
    """, (games_dict["Valorant"], val_team_id, user_ids["val_manager"],
          games_dict["Valorant"], val_team_id, user_ids["val_manager"],
          games_dict["League of Legends"], lol_team_id, user_ids["lol_manager"]))

    # 9. VODs
    cur.execute("""
        INSERT INTO vods (team_id, title, youtube_url, notes, uploaded_by)
        VALUES
        (?, 'Scrim vs Temple University - Map 1 Haven', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'Excellent retake execution on A-site in round 14. Watch eco rounds.', ?),
        (?, 'Playoff Quarterfinals vs Drexel', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'Great utility usage and post-plant setups.', ?)
    """, (val_team_id, user_ids["val_manager"], val_team_id, user_ids["val_manager"]))
    vod_id = cur.lastrowid

    # 10. Team Data (CSV) & Statistics
    sample_csv = """match_date,opponent,map,result,kills,deaths,assists,score
2026-10-15,Temple,Haven,WIN,68,52,34,13-9
2026-10-18,Drexel,Ascent,WIN,74,48,41,13-7
2026-10-22,Rowan,Bind,LOSS,58,65,29,10-13
2026-10-25,Penn State,Split,WIN,70,55,38,13-11"""

    cur.execute("""
        INSERT INTO team_data (team_id, filename, raw_csv, total_matches, wins, losses, win_rate,
                              total_kills, total_deaths, total_assists, kd_ratio, avg_kills, avg_deaths, uploaded_by)
        VALUES (?, 'val_varsity_oct2026.csv', ?, 4, 3, 1, 75.0, 270, 220, 142, 1.23, 67.5, 55.0, ?)
    """, (val_team_id, sample_csv, user_ids["val_manager"]))
    data_id = cur.lastrowid

    # 11. Comments
    cur.execute("""
        INSERT INTO analytics_comments (team_id, team_data_id, vod_id, author_id, comment)
        VALUES
        (?, ?, NULL, ?, 'Great overall performance in October. K/D ratio is positive (1.23). Let us work on defensive rotations on Bind.'),
        (?, NULL, ?, ?, 'Pay close attention to crosshair placement at 14:32 in this Haven VOD.')
    """, (val_team_id, data_id, user_ids["val_manager"], val_team_id, vod_id, user_ids["val_manager"]))

    conn.commit()
    conn.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed()
