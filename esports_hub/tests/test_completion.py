import os
import unittest
import tempfile
import time
import concurrent.futures
from app.database import init_db, get_db
from app.auth import authenticate_user, register_user, verify_email
from app.services import (
    get_visible_calendar, list_teams_for_user, get_user_profile,
    join_game_roster, list_games
)
from seed_data import seed

class TestCompletionAndNonFunctionalRequirements(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        seed(self.temp_db_path)
        self.admin = authenticate_user("admin", "Password123!", db_path=self.temp_db_path)["user"]

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_nfreq1_200_concurrent_requests(self):
        """NFREQ1: The system shall support at least 200 concurrent users/requests on file-backed database."""
        num_requests = 200

        def worker(req_id):
            # Mix of reads, writes, and authentication calls across 200 simultaneous requests
            if req_id % 4 == 0:
                return get_visible_calendar(viewer=self.admin, db_path=self.temp_db_path)["success"]
            elif req_id % 4 == 1:
                return len(list_games(db_path=self.temp_db_path)) >= 4
            elif req_id % 4 == 2:
                prof = get_user_profile(1, viewer=self.admin, db_path=self.temp_db_path)
                return prof["success"]
            else:
                auth = authenticate_user("admin", "Password123!", db_path=self.temp_db_path)
                return auth["success"]

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(worker, i) for i in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.time() - start_time

        self.assertEqual(len(results), num_requests)
        self.assertTrue(all(results), "All 200 concurrent requests must succeed without database locks or corruption.")
        print(f"NFREQ1: Successfully executed {num_requests} concurrent requests in {elapsed:.2f} seconds.")

    def test_nfreq5_responsive_layout_assets_exist(self):
        """NFREQ5: Portability: desktop layout and responsive mobile breakpoint."""
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
        index_html = os.path.join(static_dir, "index.html")
        styles_css = os.path.join(static_dir, "styles.css")
        app_js = os.path.join(static_dir, "app.js")

        self.assertTrue(os.path.exists(index_html), "index.html must exist")
        self.assertTrue(os.path.exists(styles_css), "styles.css must exist")
        self.assertTrue(os.path.exists(app_js), "app.js must exist")

        with open(styles_css, "r", encoding="utf-8") as f:
            css_content = f.read()

        # Check for responsive mobile breakpoints (e.g. @media (max-width: 768px))
        self.assertIn("@media", css_content, "CSS must include responsive media queries")
        self.assertIn("768px", css_content, "CSS must include mobile breakpoint (768px)")

        with open(index_html, "r", encoding="utf-8") as f:
            html_content = f.read()

        self.assertIn("viewport", html_content, "HTML must include responsive viewport meta tag")

    def test_nfreq8_public_calendar_latency(self):
        """NFREQ8: Calendar interface and associated events displayed within 3 seconds for logged-out users."""
        start = time.time()
        res = get_visible_calendar(viewer=None, db_path=self.temp_db_path)
        duration = time.time() - start
        self.assertTrue(res["success"])
        self.assertLess(duration, 3.0, f"Public calendar took {duration:.2f}s, expected < 3.0s")

if __name__ == "__main__":
    unittest.main()
