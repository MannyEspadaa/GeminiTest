import os
import unittest
import tempfile
import time
from app.database import init_db
from app.auth import authenticate_user
from app.services import (
    create_event, delete_event, create_schedule, edit_schedule, delete_schedule,
    get_visible_calendar, export_calendar_ics
)
from seed_data import seed

class TestCalendarAndEvents(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        seed(self.temp_db_path)

        self.admin = authenticate_user("admin", "Password123!", db_path=self.temp_db_path)["user"]
        self.val_gm = authenticate_user("val_manager", "Password123!", db_path=self.temp_db_path)["user"]
        self.lol_gm = authenticate_user("lol_manager", "Password123!", db_path=self.temp_db_path)["user"]
        self.val_player = authenticate_user("ace_duelist", "Password123!", db_path=self.temp_db_path)["user"]
        self.reg_user = authenticate_user("jordan_new", "Password123!", db_path=self.temp_db_path)["user"]

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_tc11_tc12_create_event_valid(self):
        # GM creates event for assigned game
        ev_res = create_event(
            user=self.val_gm,
            name="Valorant Scrim Workshop",
            date="2026-11-25",
            start_time="17:00",
            end_time="19:00",
            location="Room 101",
            visibility="public",
            game_id=1,
            db_path=self.temp_db_path
        )
        self.assertTrue(ev_res["success"])
        self.assertIn("event_id", ev_res)

        # Admin creates event (TC-12)
        admin_ev = create_event(
            user=self.admin,
            name="All-Campus LAN Party",
            date="2026-12-01",
            start_time="12:00",
            end_time="20:00",
            location="Student Center",
            visibility="public",
            db_path=self.temp_db_path
        )
        self.assertTrue(admin_ev["success"])

    def test_tc13_delete_event(self):
        ev_res = create_event(
            user=self.val_gm,
            name="Event to Delete",
            date="2026-11-28",
            start_time="14:00",
            end_time="15:00",
            location="Online",
            game_id=1,
            db_path=self.temp_db_path
        )
        event_id = ev_res["event_id"]
        del_res = delete_event(self.val_gm, event_id, db_path=self.temp_db_path)
        self.assertTrue(del_res["success"])

    def test_tc14_reject_event_missing_fields(self):
        res = create_event(
            user=self.val_gm,
            name="",
            date="2026-11-28",
            start_time="",
            end_time="15:00",
            location="Room 101",
            db_path=self.temp_db_path
        )
        self.assertFalse(res["success"])

    def test_tc15_prevent_unauthorized_user_managing_events(self):
        res = create_event(
            user=self.reg_user,
            name="Unauthorized Event",
            date="2026-11-28",
            start_time="14:00",
            end_time="15:00",
            location="Room 101",
            db_path=self.temp_db_path
        )
        self.assertFalse(res["success"])
        self.assertIn("Only Game Managers and Admins", res["error"])

    def test_tc16_tc17_tc18_create_and_edit_schedule(self):
        # Create schedule for Valorant (game_id 1)
        sched_res = create_schedule(
            user=self.val_gm,
            game_id=1,
            title="Practice vs Local Club",
            event_type="practice",
            date="2026-11-14",
            start_time="15:00",
            end_time="17:00",
            location_or_venue="Esports Lab",
            opponent="Local Club",
            db_path=self.temp_db_path
        )
        self.assertTrue(sched_res["success"])
        sched_id = sched_res["schedule_id"]

        # Edit schedule (TC-17)
        edit_res = edit_schedule(
            user=self.val_gm,
            schedule_id=sched_id,
            title="Updated: Practice vs Local Club",
            start_time="15:30",
            db_path=self.temp_db_path
        )
        self.assertTrue(edit_res["success"])

    def test_tc19_prevent_gm_managing_unassigned_game(self):
        # val_gm attempts to create schedule for LoL (game_id 2)
        res = create_schedule(
            user=self.val_gm,
            game_id=2,
            title="Unauthorized LoL Practice",
            event_type="practice",
            date="2026-11-14",
            start_time="15:00",
            end_time="17:00",
            db_path=self.temp_db_path
        )
        self.assertFalse(res["success"])
        self.assertIn("Permission denied", res["error"])

    def test_tc20_detect_schedule_conflict(self):
        # Create initial schedule
        create_schedule(
            user=self.val_gm,
            game_id=1,
            title="Existing Practice Slot",
            event_type="practice",
            date="2026-11-16",
            start_time="18:00",
            end_time="20:00",
            db_path=self.temp_db_path
        )
        # Attempt conflicting schedule at 18:30 - 19:30 on same date
        conf_res = create_schedule(
            user=self.val_gm,
            game_id=1,
            title="Conflicting Scrim",
            event_type="match",
            date="2026-11-16",
            start_time="18:30",
            end_time="19:30",
            db_path=self.temp_db_path
        )
        self.assertFalse(conf_res["success"])
        self.assertTrue(conf_res.get("conflict"))
        self.assertIn("conflict detected", conf_res["error"].lower())

    def test_tc22_nfreq8_calendar_speed_and_rendering(self):
        start = time.time()
        # Logged out / public user view
        cal = get_visible_calendar(viewer=None, db_path=self.temp_db_path)
        elapsed = time.time() - start
        self.assertTrue(cal["success"])
        self.assertLess(elapsed, 3.0, "NFREQ8 violated: calendar rendering took >= 3s")
        # Check exported iCalendar adapter
        ics = export_calendar_ics(viewer=None, db_path=self.temp_db_path)
        self.assertIn("BEGIN:VCALENDAR", ics)

    def test_tc47_tc49_freq19_visibility_scopes(self):
        # Public user sees public events, but not team-only events
        public_cal = get_visible_calendar(viewer=None, db_path=self.temp_db_path)
        event_names = [e["name"] for e in public_cal["events"]]
        self.assertIn("Campus Fall Esports Invitational", event_names)
        self.assertNotIn("Valorant Varsity Strategic Review", event_names)

        # Valorant player sees the team review
        player_cal = get_visible_calendar(viewer=self.val_player, db_path=self.temp_db_path)
        p_event_names = [e["name"] for e in player_cal["events"]]
        self.assertIn("Valorant Varsity Strategic Review", p_event_names)

if __name__ == "__main__":
    unittest.main()
