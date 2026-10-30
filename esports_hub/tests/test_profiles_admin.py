import os
import unittest
import tempfile
from app.database import init_db
from app.auth import register_user, verify_email, authenticate_user
from app.services import (
    get_user_profile, update_discord_username, join_game_roster,
    admin_grant_role, admin_revoke_role, admin_suspend_user,
    admin_unsuspend_user, admin_remove_user, admin_list_users
)
from seed_data import seed

class TestProfilesAndAdmin(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        seed(self.temp_db_path)

        # Login admin
        admin_auth = authenticate_user("admin", "Password123!", db_path=self.temp_db_path)
        self.admin_user = admin_auth["user"]

        # Login regular user
        user_auth = authenticate_user("jordan_new", "Password123!", db_path=self.temp_db_path)
        self.reg_user = user_auth["user"]

        # Login player
        player_auth = authenticate_user("ace_duelist", "Password123!", db_path=self.temp_db_path)
        self.player_user = player_auth["user"]

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_tc6_view_own_profile(self):
        # Viewing own profile includes full name, email, discord, rosters
        profile_res = get_user_profile(self.reg_user["id"], viewer=self.reg_user, db_path=self.temp_db_path)
        self.assertTrue(profile_res["success"])
        profile = profile_res["profile"]
        self.assertEqual(profile["full_name"], "Jordan Hayes")
        self.assertEqual(profile["email"], "jordan.hayes@esports.edu")
        self.assertTrue(profile["is_own_profile"])

    def test_tc7_view_other_user_profile_privacy(self):
        # When viewing another user, only first name, username, rosters, discord are exposed (no email or full name)
        profile_res = get_user_profile(self.player_user["id"], viewer=self.reg_user, db_path=self.temp_db_path)
        self.assertTrue(profile_res["success"])
        profile = profile_res["profile"]
        self.assertEqual(profile["first_name"], "Derek")
        self.assertEqual(profile["username"], "ace_duelist")
        self.assertEqual(profile["discord_username"], "Frostbite#9999")
        self.assertNotIn("email", profile)
        self.assertNotIn("full_name", profile)
        self.assertFalse(profile["is_own_profile"])

    def test_tc8_profile_retrieval_failure(self):
        profile_res = get_user_profile(999999, viewer=self.reg_user, db_path=self.temp_db_path)
        self.assertFalse(profile_res["success"])
        self.assertEqual(profile_res["error"], "User not found.")

    def test_tc45_link_discord_username(self):
        update_res = update_discord_username(self.reg_user["id"], "Jordan#5555", db_path=self.temp_db_path)
        self.assertTrue(update_res["success"])

        profile_res = get_user_profile(self.reg_user["id"], viewer=self.reg_user, db_path=self.temp_db_path)
        self.assertEqual(profile_res["profile"]["discord_username"], "Jordan#5555")

    def test_tc38_tc39_tc40_admin_roles_grant_and_revoke(self):
        # Grant Game Manager role to regular user
        grant_res = admin_grant_role(self.admin_user, self.reg_user["id"], "game_manager", game_id=1, db_path=self.temp_db_path)
        self.assertTrue(grant_res["success"])

        users_res = admin_list_users(self.admin_user, db_path=self.temp_db_path)
        target = next(u for u in users_res["users"] if u["id"] == self.reg_user["id"])
        self.assertIn("game_manager", target["roles"])

        # Revoke Game Manager role
        revoke_res = admin_revoke_role(self.admin_user, self.reg_user["id"], "game_manager", db_path=self.temp_db_path)
        self.assertTrue(revoke_res["success"])

        users_res2 = admin_list_users(self.admin_user, db_path=self.temp_db_path)
        target2 = next(u for u in users_res2["users"] if u["id"] == self.reg_user["id"])
        self.assertNotIn("game_manager", target2["roles"])

        # Grant Admin role
        admin_grant = admin_grant_role(self.admin_user, self.reg_user["id"], "admin", db_path=self.temp_db_path)
        self.assertTrue(admin_grant["success"])

    def test_tc41_prevent_non_admin_from_managing_roles(self):
        res = admin_grant_role(self.reg_user, self.player_user["id"], "admin", db_path=self.temp_db_path)
        self.assertFalse(res["success"])
        self.assertIn("Administrator role required", res["error"])

    def test_tc42_tc43_tc44_account_moderation(self):
        # Prevent non-admin moderation (TC-44)
        non_admin_res = admin_suspend_user(self.reg_user, self.player_user["id"], db_path=self.temp_db_path)
        self.assertFalse(non_admin_res["success"])

        # Admin suspends user (TC-42)
        suspend_res = admin_suspend_user(self.admin_user, self.reg_user["id"], db_path=self.temp_db_path)
        self.assertTrue(suspend_res["success"])

        # Suspended user cannot log in
        login_res = authenticate_user("jordan_new", "Password123!", db_path=self.temp_db_path)
        self.assertFalse(login_res["success"])
        self.assertIn("suspended", login_res["error"].lower())

        # Unsuspend
        unsuspend_res = admin_unsuspend_user(self.admin_user, self.reg_user["id"], db_path=self.temp_db_path)
        self.assertTrue(unsuspend_res["success"])
        login_ok = authenticate_user("jordan_new", "Password123!", db_path=self.temp_db_path)
        self.assertTrue(login_ok["success"])

        # Admin removes/deactivates user (TC-43)
        remove_res = admin_remove_user(self.admin_user, self.reg_user["id"], db_path=self.temp_db_path)
        self.assertTrue(remove_res["success"])
        login_deact = authenticate_user("jordan_new", "Password123!", db_path=self.temp_db_path)
        self.assertFalse(login_deact["success"])
        self.assertIn("deactivated", login_deact["error"].lower())

if __name__ == "__main__":
    unittest.main()
