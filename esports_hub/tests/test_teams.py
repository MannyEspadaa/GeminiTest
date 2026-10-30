import os
import unittest
import tempfile
from app.database import init_db
from app.auth import authenticate_user, get_current_user_from_token
from app.services import (
    join_game_roster, leave_game_roster, get_roster_members,
    create_shell_team, modify_team, delete_shell_team,
    add_player_to_team, remove_player_from_team,
    list_teams_for_user, get_team_details, get_user_profile
)
from seed_data import seed

class TestTeamsAndRosters(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        seed(self.temp_db_path)

        self.admin = authenticate_user("admin", "Password123!", db_path=self.temp_db_path)["user"]
        self.val_gm = authenticate_user("val_manager", "Password123!", db_path=self.temp_db_path)["user"]
        self.lol_gm = authenticate_user("lol_manager", "Password123!", db_path=self.temp_db_path)["user"]
        self.val_player = authenticate_user("ace_duelist", "Password123!", db_path=self.temp_db_path)["user"]
        self.reg_user = authenticate_user("jordan_new", "Password123!", db_path=self.temp_db_path)["user"]
        self.comm_user = authenticate_user("alex_fan", "Password123!", db_path=self.temp_db_path)["user"]

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_tc23_tc24_roster_join_and_leave(self):
        # Regular user joins Overwatch 2 roster (game_id 4)
        join_res = join_game_roster(self.reg_user, game_id=4, db_path=self.temp_db_path)
        self.assertTrue(join_res["success"])

        # Verify membership
        members = get_roster_members(game_id=4, db_path=self.temp_db_path)
        self.assertTrue(any(m["id"] == self.reg_user["id"] for m in members))

        # User leaves roster
        leave_res = leave_game_roster(self.reg_user, game_id=4, db_path=self.temp_db_path)
        self.assertTrue(leave_res["success"])
        members_after = get_roster_members(game_id=4, db_path=self.temp_db_path)
        self.assertFalse(any(m["id"] == self.reg_user["id"] for m in members_after))

    def test_tc27_tc28_tc29_create_modify_delete_shell_team(self):
        # GM creates shell team for assigned game (Valorant, game_id 1)
        create_res = create_shell_team(self.val_gm, game_id=1, team_name="Valorant Trainees", db_path=self.temp_db_path)
        self.assertTrue(create_res["success"])
        team_id = create_res["team_id"]

        # Modify team name (TC-28)
        mod_res = modify_team(self.val_gm, team_id, "Valorant Tier 2", db_path=self.temp_db_path)
        self.assertTrue(mod_res["success"])

        details = get_team_details(self.val_gm, team_id, db_path=self.temp_db_path)
        self.assertEqual(details["team"]["name"], "Valorant Tier 2")

        # Delete shell team (TC-29)
        del_res = delete_shell_team(self.val_gm, team_id, db_path=self.temp_db_path)
        self.assertTrue(del_res["success"])

    def test_tc30_prevent_gm_managing_unassigned_team(self):
        # val_gm attempts to create team for LoL (game_id 2)
        res = create_shell_team(self.val_gm, game_id=2, team_name="Unauthorized Team", db_path=self.temp_db_path)
        self.assertFalse(res["success"])
        self.assertIn("Permission denied", res["error"])

    def test_tc31_reject_team_missing_name(self):
        res = create_shell_team(self.val_gm, game_id=1, team_name="   ", db_path=self.temp_db_path)
        self.assertFalse(res["success"])

    def test_tc32_promote_community_member_to_player(self):
        # Community member 'alex_fan' is in Valorant community roster
        # val_gm creates a team or uses existing 'Valorant Academy' (team_id 2)
        # val_gm adds alex_fan to the team
        add_res = add_player_to_team(self.val_gm, team_id=2, target_user_id=self.comm_user["id"], role_in_team="Initiator", db_path=self.temp_db_path)
        self.assertTrue(add_res["success"])

        # Check alex_fan profile and roles
        profile_res = get_user_profile(self.comm_user["id"], viewer=self.comm_user, db_path=self.temp_db_path)
        team_names = [t["name"] for t in profile_res["profile"]["teams"]]
        self.assertIn("Valorant Academy", team_names)

        # Login again to refresh roles and verify player role granted
        alex_auth = authenticate_user("alex_fan", "Password123!", db_path=self.temp_db_path)
        self.assertIn("player", alex_auth["user"]["roles"])

    def test_tc55_admin_views_all_teams_while_gm_and_player_restricted(self):
        # Admin can view all teams (Valorant Varsity, Valorant Academy, LoL Varsity)
        admin_teams = list_teams_for_user(self.admin, db_path=self.temp_db_path)
        admin_team_names = [t["name"] for t in admin_teams]
        self.assertIn("Valorant Varsity", admin_team_names)
        self.assertIn("LoL Varsity", admin_team_names)
        self.assertGreaterEqual(len(admin_teams), 3)

        # val_gm can only view Valorant teams
        val_teams = list_teams_for_user(self.val_gm, db_path=self.temp_db_path)
        val_team_names = [t["name"] for t in val_teams]
        self.assertIn("Valorant Varsity", val_team_names)
        self.assertNotIn("LoL Varsity", val_team_names)

        # player (ace_duelist) is only on Valorant Varsity
        player_teams = list_teams_for_user(self.val_player, db_path=self.temp_db_path)
        self.assertEqual(len(player_teams), 1)
        self.assertEqual(player_teams[0]["name"], "Valorant Varsity")

if __name__ == "__main__":
    unittest.main()
