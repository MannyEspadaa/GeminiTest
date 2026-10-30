import os
import json
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from app.database import init_db
from app.auth import (
    register_user, verify_email, authenticate_user,
    get_current_user_from_token, end_session
)
from app.services import (
    get_user_profile, update_discord_username, list_games,
    join_game_roster, leave_game_roster, get_roster_members,
    create_shell_team, modify_team, delete_shell_team,
    add_player_to_team, remove_player_from_team, list_teams_for_user,
    get_team_details, create_event, delete_event,
    create_schedule, edit_schedule, delete_schedule,
    get_visible_calendar, export_calendar_ics,
    upload_vod, parse_and_upload_csv_stats, add_analytics_comment,
    get_team_vods, get_team_statistics,
    admin_list_users, admin_grant_role, admin_revoke_role,
    admin_suspend_user, admin_unsuspend_user, admin_remove_user
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

class EsportsAppHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, content_type="text/plain; charset=utf-8", status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path, content_type="text/html; charset=utf-8"):
        if not os.path.exists(file_path):
            self.send_error(404, "File not found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _get_auth_user(self):
        auth_header = self.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "token=" in self.headers.get("Cookie", ""):
            cookies = urllib.parse.parse_qs(self.headers.get("Cookie").replace("; ", "&"))
            token = cookies.get("token", [None])[0]
        if not token:
            return None
        return get_current_user_from_token(token)

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        user = self._get_auth_user()

        # Static files
        if path == "/" or path == "/index.html":
            self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return
        elif path.startswith("/static/"):
            rel_file = path[len("/static/"):]
            full_path = os.path.join(STATIC_DIR, rel_file)
            mime = "text/plain"
            if rel_file.endswith(".css"):
                mime = "text/css"
            elif rel_file.endswith(".js"):
                mime = "application/javascript"
            elif rel_file.endswith(".html"):
                mime = "text/html"
            self._send_file(full_path, mime)
            return

        # API Endpoints
        if path == "/api/me":
            if not user:
                self._send_json({"authenticated": False, "user": None})
            else:
                self._send_json({"authenticated": True, "user": user})
            return

        elif path.startswith("/api/profile"):
            target_id = user["id"] if user else None
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                target_id = int(parts[2])
            if not target_id:
                self._send_json({"success": False, "error": "User ID required or not authenticated."}, 401)
                return
            res = get_user_profile(target_id, viewer=user)
            self._send_json(res, 200 if res["success"] else 404)
            return

        elif path == "/api/games":
            games = list_games()
            self._send_json({"success": True, "games": games})
            return

        elif path.startswith("/api/roster/members/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3].isdigit():
                game_id = int(parts[3])
                members = get_roster_members(game_id)
                self._send_json({"success": True, "members": members})
                return
            self._send_json({"success": False, "error": "Game ID required"}, 400)
            return

        elif path == "/api/teams":
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, 401)
                return
            teams = list_teams_for_user(user)
            self._send_json({"success": True, "teams": teams})
            return

        elif path.startswith("/api/teams/") and path.endswith("/vods"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                team_id = int(parts[2])
                res = get_team_vods(user, team_id)
                self._send_json(res, 200 if res["success"] else 403)
                return

        elif path.startswith("/api/teams/") and path.endswith("/stats"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[2].isdigit():
                team_id = int(parts[2])
                res = get_team_statistics(user, team_id)
                self._send_json(res, 200 if res["success"] else 403)
                return

        elif path.startswith("/api/teams/") and not path.endswith(("/vods", "/stats")):
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                team_id = int(parts[2])
                res = get_team_details(user, team_id)
                self._send_json(res, 200 if res["success"] else 403)
                return

        elif path == "/api/calendar":
            res = get_visible_calendar(viewer=user)
            self._send_json(res)
            return

        elif path == "/api/calendar/export.ics":
            ics = export_calendar_ics(viewer=user)
            self._send_text(ics, "text/calendar; charset=utf-8")
            return

        elif path == "/api/admin/users":
            res = admin_list_users(user)
            self._send_json(res, 200 if res["success"] else 403)
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()
        user = self._get_auth_user()

        if path == "/api/register":
            res = register_user(
                full_name=body.get("full_name", ""),
                username=body.get("username", ""),
                email=body.get("email", ""),
                password=body.get("password", "")
            )
            self._send_json(res, 201 if res["success"] else 400)
            return

        elif path == "/api/verify":
            res = verify_email(token=body.get("token", ""))
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path == "/api/login":
            res = authenticate_user(
                username_or_email=body.get("username_or_email", ""),
                password=body.get("password", "")
            )
            self._send_json(res, 200 if res["success"] else 401)
            return

        elif path == "/api/logout":
            token = None
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            end_session(token)
            self._send_json({"success": True, "message": "Logged out successfully."})
            return

        elif path == "/api/discord":
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, 401)
                return
            res = update_discord_username(user["id"], body.get("discord_username", ""))
            self._send_json(res)
            return

        elif path == "/api/roster/join":
            res = join_game_roster(user, int(body.get("game_id", 0)))
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path == "/api/roster/leave":
            res = leave_game_roster(user, int(body.get("game_id", 0)))
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path == "/api/teams/create":
            res = create_shell_team(user, int(body.get("game_id", 0)), body.get("team_name", ""))
            self._send_json(res, 201 if res["success"] else 400)
            return

        elif path.startswith("/api/teams/") and path.endswith("/edit"):
            parts = path.strip("/").split("/")
            team_id = int(parts[2])
            res = modify_team(user, team_id, body.get("name", ""))
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path.startswith("/api/teams/") and path.endswith("/delete"):
            parts = path.strip("/").split("/")
            team_id = int(parts[2])
            res = delete_shell_team(user, team_id)
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path.startswith("/api/teams/") and path.endswith("/add_member"):
            parts = path.strip("/").split("/")
            team_id = int(parts[2])
            res = add_player_to_team(user, team_id, int(body.get("user_id", 0)), body.get("role_in_team", "player"))
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path.startswith("/api/teams/") and path.endswith("/remove_member"):
            parts = path.strip("/").split("/")
            team_id = int(parts[2])
            res = remove_player_from_team(user, team_id, int(body.get("user_id", 0)))
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path == "/api/events/create":
            res = create_event(
                user=user,
                name=body.get("name", ""),
                date=body.get("date", ""),
                start_time=body.get("start_time", ""),
                end_time=body.get("end_time", ""),
                location=body.get("location", ""),
                visibility=body.get("visibility", "public"),
                game_id=body.get("game_id"),
                team_id=body.get("team_id")
            )
            self._send_json(res, 201 if res["success"] else 400)
            return

        elif path.startswith("/api/events/") and path.endswith("/delete"):
            parts = path.strip("/").split("/")
            event_id = int(parts[2])
            res = delete_event(user, event_id)
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path == "/api/schedules/create":
            res = create_schedule(
                user=user,
                game_id=int(body.get("game_id", 0)),
                title=body.get("title", ""),
                event_type=body.get("event_type", "match"),
                date=body.get("date", ""),
                start_time=body.get("start_time", ""),
                end_time=body.get("end_time", ""),
                team_id=body.get("team_id"),
                location_or_venue=body.get("location_or_venue", ""),
                opponent=body.get("opponent", ""),
                allow_conflict=body.get("allow_conflict", False)
            )
            self._send_json(res, 201 if res["success"] else 400)
            return

        elif path.startswith("/api/schedules/") and path.endswith("/edit"):
            parts = path.strip("/").split("/")
            sched_id = int(parts[2])
            res = edit_schedule(
                user=user,
                schedule_id=sched_id,
                title=body.get("title"),
                event_type=body.get("event_type"),
                date=body.get("date"),
                start_time=body.get("start_time"),
                end_time=body.get("end_time"),
                location_or_venue=body.get("location_or_venue"),
                opponent=body.get("opponent"),
                team_id=body.get("team_id"),
                allow_conflict=body.get("allow_conflict", False)
            )
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path.startswith("/api/schedules/") and path.endswith("/delete"):
            parts = path.strip("/").split("/")
            sched_id = int(parts[2])
            res = delete_schedule(user, sched_id)
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path == "/api/vods/upload":
            res = upload_vod(
                user=user,
                team_id=int(body.get("team_id", 0)),
                title=body.get("title", ""),
                youtube_url=body.get("youtube_url", ""),
                notes=body.get("notes", "")
            )
            self._send_json(res, 201 if res["success"] else 400)
            return

        elif path == "/api/stats/upload_csv":
            res = parse_and_upload_csv_stats(
                user=user,
                team_id=int(body.get("team_id", 0)),
                filename=body.get("filename", "match_data.csv"),
                csv_text=body.get("csv_text", "")
            )
            self._send_json(res, 201 if res["success"] else 400)
            return

        elif path == "/api/comments/create":
            res = add_analytics_comment(
                user=user,
                team_id=int(body.get("team_id", 0)),
                comment=body.get("comment", ""),
                team_data_id=body.get("team_data_id"),
                vod_id=body.get("vod_id")
            )
            self._send_json(res, 201 if res["success"] else 400)
            return

        elif path == "/api/admin/roles/grant":
            res = admin_grant_role(
                admin_user=user,
                target_user_id=int(body.get("target_user_id", 0)),
                role=body.get("role", ""),
                game_id=body.get("game_id")
            )
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path == "/api/admin/roles/revoke":
            res = admin_revoke_role(
                admin_user=user,
                target_user_id=int(body.get("target_user_id", 0)),
                role=body.get("role", ""),
                game_id=body.get("game_id")
            )
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path.startswith("/api/admin/users/") and path.endswith("/suspend"):
            parts = path.strip("/").split("/")
            target_id = int(parts[4])
            res = admin_suspend_user(user, target_id)
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path.startswith("/api/admin/users/") and path.endswith("/unsuspend"):
            parts = path.strip("/").split("/")
            target_id = int(parts[4])
            res = admin_unsuspend_user(user, target_id)
            self._send_json(res, 200 if res["success"] else 400)
            return

        elif path.startswith("/api/admin/users/") and path.endswith("/remove"):
            parts = path.strip("/").split("/")
            target_id = int(parts[4])
            res = admin_remove_user(user, target_id)
            self._send_json(res, 200 if res["success"] else 400)
            return

        self.send_error(404, "Endpoint not found")

def run_server(port=8080, db_path=None):
    init_db(db_path)
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, EsportsAppHandler)
    print(f"Esports Program Central Hub server running on http://localhost:{port}/")
    return httpd

if __name__ == "__main__":
    httpd = run_server(8080)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()
