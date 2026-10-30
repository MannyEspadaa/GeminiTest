import os
import unittest
import tempfile
import time
from app.database import init_db
from app.auth import (
    register_user, verify_email, authenticate_user,
    get_current_user_from_token, end_session, is_official_email
)
from app.services import get_visible_calendar, list_teams_for_user

class TestAuthAndOnboarding(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_tc1_create_account_valid_official_email(self):
        res = register_user(
            full_name="Marcus Vance",
            username="marcusv",
            email="marcus@esports.edu",
            password="StrongPassword123!",
            db_path=self.temp_db_path
        )
        self.assertTrue(res["success"], f"Registration failed: {res.get('error')}")
        self.assertIn("verification_token", res)

        # Complete email verification
        ver_res = verify_email(res["verification_token"], db_path=self.temp_db_path)
        self.assertTrue(ver_res["success"])

        # Authenticate successfully
        auth_res = authenticate_user("marcusv", "StrongPassword123!", db_path=self.temp_db_path)
        self.assertTrue(auth_res["success"])
        self.assertIn("token", auth_res)
        self.assertEqual(auth_res["user"]["username"], "marcusv")

    def test_tc2_reject_non_official_email(self):
        res = register_user(
            full_name="John Doe",
            username="johndoe",
            email="johndoe@gmail.com",
            password="StrongPassword123!",
            db_path=self.temp_db_path
        )
        self.assertFalse(res["success"])
        self.assertIn("official institutional", res["error"].lower())

    def test_tc3_reject_missing_required_fields(self):
        # Missing full name
        res1 = register_user("", "user1", "user1@university.edu", "pass123", db_path=self.temp_db_path)
        self.assertFalse(res1["success"])

        # Missing username
        res2 = register_user("User Two", "", "user2@university.edu", "pass123", db_path=self.temp_db_path)
        self.assertFalse(res2["success"])

        # Missing email
        res3 = register_user("User Three", "user3", "", "pass123", db_path=self.temp_db_path)
        self.assertFalse(res3["success"])

        # Short password
        res4 = register_user("User Four", "user4", "user4@university.edu", "123", db_path=self.temp_db_path)
        self.assertFalse(res4["success"])

    def test_tc4_reject_duplicate_email(self):
        register_user("User A", "user_a", "duplicate@university.edu", "Password123!", db_path=self.temp_db_path)
        res = register_user("User B", "user_b", "duplicate@university.edu", "Password123!", db_path=self.temp_db_path)
        self.assertFalse(res["success"])
        self.assertIn("already exists", res["error"].lower())

    def test_tc5_nfreq7_onboarding_speed(self):
        start_time = time.time()
        reg = register_user("Speedy User", "speedy", "speedy@university.edu", "Password123!", db_path=self.temp_db_path)
        self.assertTrue(reg["success"])
        ver = verify_email(reg["verification_token"], db_path=self.temp_db_path)
        self.assertTrue(ver["success"])
        auth = authenticate_user("speedy", "Password123!", db_path=self.temp_db_path)
        self.assertTrue(auth["success"])
        elapsed = time.time() - start_time
        # Must be well within 5 minutes (300 seconds)
        self.assertLess(elapsed, 5.0)

    def test_tc9_tc10_freq10_dashboard_access_control(self):
        # Unauthenticated check
        user = get_current_user_from_token("invalid-fake-token", db_path=self.temp_db_path)
        self.assertIsNone(user, "Unauthenticated user should not have a valid session")

        # Authenticated user
        reg = register_user("Dashboard User", "dash_user", "dash@university.edu", "Password123!", db_path=self.temp_db_path)
        verify_email(reg["verification_token"], db_path=self.temp_db_path)
        auth = authenticate_user("dash_user", "Password123!", db_path=self.temp_db_path)
        
        user_info = get_current_user_from_token(auth["token"], db_path=self.temp_db_path)
        self.assertIsNotNone(user_info)
        self.assertEqual(user_info["username"], "dash_user")

        # Check permitted data for dashboard
        cal = get_visible_calendar(viewer=user_info, db_path=self.temp_db_path)
        self.assertTrue(cal["success"])
        teams = list_teams_for_user(user_info, db_path=self.temp_db_path)
        self.assertIsInstance(teams, list)

if __name__ == "__main__":
    unittest.main()
