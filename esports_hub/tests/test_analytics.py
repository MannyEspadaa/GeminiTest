import os
import unittest
import tempfile
from app.database import init_db
from app.auth import authenticate_user
from app.services import (
    upload_vod, parse_and_upload_csv_stats, add_analytics_comment,
    get_team_vods, get_team_statistics
)
from seed_data import seed

class TestAnalyticsAndVODs(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        seed(self.temp_db_path)

        self.admin = authenticate_user("admin", "Password123!", db_path=self.temp_db_path)["user"]
        self.val_gm = authenticate_user("val_manager", "Password123!", db_path=self.temp_db_path)["user"]
        self.lol_gm = authenticate_user("lol_manager", "Password123!", db_path=self.temp_db_path)["user"]
        self.val_player = authenticate_user("ace_duelist", "Password123!", db_path=self.temp_db_path)["user"]
        self.lol_player = authenticate_user("shadow_mid", "Password123!", db_path=self.temp_db_path)["user"]
        self.reg_user = authenticate_user("jordan_new", "Password123!", db_path=self.temp_db_path)["user"]

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_tc33_tc50_upload_and_view_vod(self):
        # val_gm uploads VOD for Valorant Varsity (team_id 1)
        res = upload_vod(
            user=self.val_gm,
            team_id=1,
            title="Tournament Semifinals VOD",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            notes="Watch retake execution",
            db_path=self.temp_db_path
        )
        self.assertTrue(res["success"])
        self.assertIn("vod_id", res)

        # Player of team (val_player) views VODs
        vods_res = get_team_vods(self.val_player, team_id=1, db_path=self.temp_db_path)
        self.assertTrue(vods_res["success"])
        vod_titles = [v["title"] for v in vods_res["vods"]]
        self.assertIn("Tournament Semifinals VOD", vod_titles)

    def test_tc34_tc51_upload_csv_calculate_stats(self):
        csv_data = """match_date,opponent,map,result,kills,deaths,assists
2026-10-01,NYU,Haven,WIN,65,40,30
2026-10-05,Columbia,Ascent,LOSS,50,55,25
2026-10-08,Cornell,Split,WIN,70,45,35"""

        res = parse_and_upload_csv_stats(
            user=self.val_gm,
            team_id=1,
            filename="oct_matches.csv",
            csv_text=csv_data,
            db_path=self.temp_db_path
        )
        self.assertTrue(res["success"])
        stats = res["statistics"]
        self.assertEqual(stats["total_matches"], 3)
        self.assertEqual(stats["wins"], 2)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["win_rate"], 66.7)
        self.assertEqual(stats["total_kills"], 185)
        self.assertEqual(stats["total_deaths"], 140)
        self.assertEqual(stats["kd_ratio"], 1.32)

        # Player views team statistics
        player_stats = get_team_statistics(self.val_player, team_id=1, db_path=self.temp_db_path)
        self.assertTrue(player_stats["success"])
        self.assertGreaterEqual(len(player_stats["datasets"]), 1)

    def test_tc35_leave_comment_on_data(self):
        comm_res = add_analytics_comment(
            user=self.val_gm,
            team_id=1,
            comment="Great spacing during default setups.",
            team_data_id=1,
            db_path=self.temp_db_path
        )
        self.assertTrue(comm_res["success"])

        # Check comment appears in player view
        stats = get_team_statistics(self.val_player, team_id=1, db_path=self.temp_db_path)
        first_dataset = stats["datasets"][0]
        self.assertTrue(any("spacing during default setups" in c["comment"] for c in first_dataset["comments"]))

    def test_tc36_reject_empty_csv(self):
        res = parse_and_upload_csv_stats(
            user=self.val_gm,
            team_id=1,
            filename="empty.csv",
            csv_text="",
            db_path=self.temp_db_path
        )
        self.assertFalse(res["success"])

    def test_tc37_prevent_gm_uploading_unassigned_team(self):
        # val_gm attempts to upload to LoL team (team_id 3)
        res = upload_vod(
            user=self.val_gm,
            team_id=3,
            title="Unauthorized VOD",
            youtube_url="https://youtube.com/watch?v=xyz",
            db_path=self.temp_db_path
        )
        self.assertFalse(res["success"])
        self.assertIn("Permission denied", res["error"])

    def test_tc52_prevent_player_viewing_other_team_vods_and_stats(self):
        # val_player (on team 1) attempts to access LoL team (team 3)
        vods_res = get_team_vods(self.val_player, team_id=3, db_path=self.temp_db_path)
        self.assertFalse(vods_res["success"])
        self.assertIn("Permission denied", vods_res["error"])

        stats_res = get_team_statistics(self.val_player, team_id=3, db_path=self.temp_db_path)
        self.assertFalse(stats_res["success"])
        self.assertIn("Permission denied", stats_res["error"])

    def test_tc53_display_no_vods_available(self):
        # Team 2 (Valorant Academy) has no VODs uploaded yet
        # Admin or member views VODs
        res = get_team_vods(self.admin, team_id=2, db_path=self.temp_db_path)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["vods"]), 0)

if __name__ == "__main__":
    unittest.main()
