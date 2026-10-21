import os
import re
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch


TEST_DIRECTORY = tempfile.TemporaryDirectory()
DATABASE_PATH = Path(TEST_DIRECTORY.name) / "farewise-tests.db"
os.environ["FAREWISE_DATABASE_PATH"] = str(DATABASE_PATH)
os.environ.pop("DATABASE_URL", None)
os.environ.pop("VERCEL", None)
os.environ["FAREWISE_SECRET_KEY"] = "test-only-secret-key"

with sqlite3.connect(DATABASE_PATH) as database:
    database.execute("""
        CREATE TABLE searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            distance_km REAL,
            created_at TEXT NOT NULL
        )
    """)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as farewise  # noqa: E402


class AccountFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        farewise.app.config.update(TESTING=True, SECRET_KEY="test-only-secret-key")

    def setUp(self):
        with farewise.app.app_context():
            database = farewise.get_db()
            database.execute("DELETE FROM searches")
            database.execute("DELETE FROM farewise_users")
            database.commit()
        self.client = farewise.app.test_client()

    def csrf_token(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def test_install_action_and_pwa_assets_are_available(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="install-app"', response.data)
        self.assertNotIn(b'id="install-app" type="button" hidden', response.data)
        self.assertIn(b"Add to Home Screen", response.data)

        for path in (
            "/manifest.webmanifest",
            "/service-worker.js",
            "/app.js",
            "/static/icons/icon-192.png",
            "/static/icons/icon-512.png",
        ):
            with self.subTest(path=path):
                asset = self.client.get(path)
                self.assertEqual(asset.status_code, 200)
                asset.close()

    def test_login_and_admin_entry_points_are_visible_to_guests(self):
        response = self.client.get("/")
        self.assertIn(b'href="/login">Log in</a>', response.data)
        self.assertIn(b'href="/register">Sign up</a>', response.data)
        self.assertIn(b'href="/admin">Admin</a>', response.data)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def register(self, email, password="correct-horse-battery"):
        token = self.csrf_token("/register")
        return self.client.post(
            "/register",
            data={"csrf_token": token, "email": email, "password": password},
            follow_redirects=True,
        )

    def login(self, email, password="correct-horse-battery"):
        token = self.csrf_token("/login")
        return self.client.post(
            "/login",
            data={"csrf_token": token, "email": email, "password": password},
            follow_redirects=True,
        )

    def test_registration_hashes_password_and_login_works(self):
        response = self.register("rider@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"free subscriber account is ready", response.data)

        with farewise.app.app_context():
            user = farewise.get_db().execute(
                "SELECT password_hash, subscription_status FROM farewise_users "
                "WHERE email = ?",
                ("rider@example.com",),
            ).fetchone()
        self.assertNotEqual(user["password_hash"], "correct-horse-battery")
        self.assertTrue(user["password_hash"].startswith("scrypt:"))
        self.assertEqual(user["subscription_status"], "free")

        response = self.login("rider@example.com", "wrong-password")
        self.assertIn(b"Email or password is incorrect", response.data)
        self.assertEqual(self.client.get("/account").status_code, 302)

        response = self.login("rider@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Compare road &amp; air fares", response.data)
        self.assertEqual(
            self.client.post(
                "/login",
                data={
                    "csrf_token": self.csrf_token("/login"),
                    "email": "rider@example.com",
                    "password": "wrong-password",
                },
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get("/account").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/logout",
                data={"csrf_token": self.csrf_token("/")},
            ).status_code,
            302,
        )

    def test_registration_validates_csrf_email_and_password(self):
        self.assertEqual(
            self.client.post(
                "/register",
                data={"email": "bad@example.com", "password": "long-enough-password"},
            ).status_code,
            400,
        )
        token = self.csrf_token("/register")
        response = self.client.post(
            "/register",
            data={
                "csrf_token": token,
                "email": "not-an-email",
                "password": "short",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Enter a valid email address", response.data)
        self.assertEqual(
            self.client.post(
                "/register",
                data={
                    "csrf_token": self.csrf_token("/register"),
                    "email": "rider@example.com",
                    "password": "correct-horse-battery",
                },
            ).status_code,
            302,
        )
        response = self.register("rider@example.com")
        self.assertIn(b"already exists", response.data)

    def test_admin_can_manage_access_and_non_admin_is_forbidden(self):
        self.register("rider@example.com")
        self.assertEqual(self.login("rider@example.com").status_code, 200)
        self.assertEqual(self.client.get("/admin").status_code, 403)
        self.client.post(
            "/logout",
            data={"csrf_token": self.csrf_token("/login")},
        )

        self.register("admin@example.com")
        with farewise.app.app_context():
            farewise.get_db().execute(
                "UPDATE farewise_users SET role = 'admin' WHERE email = ?",
                ("admin@example.com",),
            )
            farewise.get_db().commit()
        self.login("admin@example.com")
        dashboard = self.client.get("/admin")
        self.assertEqual(dashboard.status_code, 200)
        homepage = self.client.get("/")
        self.assertIn(b'href="/admin">Admin</a>', homepage.data)
        self.assertIn(b"Paystack checkout remains disabled", dashboard.data)

        token = self.csrf_token("/admin")
        missing_subscriber = self.client.post(
            "/admin",
            data={
                "csrf_token": token,
                "subscriber_id": 999999,
                "subscription_status": "active",
                "subscription_plan": "monthly",
            },
        )
        self.assertEqual(missing_subscriber.status_code, 404)

        with farewise.app.app_context():
            subscriber = farewise.get_db().execute(
                "SELECT id FROM farewise_users WHERE email = ?",
                ("rider@example.com",),
            ).fetchone()
        token = self.csrf_token("/admin")
        response = self.client.post(
            "/admin",
            data={
                "csrf_token": token,
                "subscriber_id": subscriber["id"],
                "subscription_status": "suspended",
                "subscription_plan": "monthly",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Subscriber access updated", response.data)

        self.client.post(
            "/logout",
            data={"csrf_token": self.csrf_token("/admin")},
        )
        self.login("rider@example.com")
        response = self.client.post(
            "/",
            data={"origin": "abuja_city_gate", "destination": "lagos_tbs"},
        )
        self.assertIn(b"Your account is suspended", response.data)
        self.assertNotIn(b"YOUR COMPARISON", response.data)

    def test_each_subscriber_search_history_is_private(self):
        self.register("first@example.com")
        self.login("first@example.com")
        response = self.client.post(
            "/",
            data={"origin": "abuja_city_gate", "destination": "lagos_tbs"},
        )
        self.assertIn(b"YOUR COMPARISON", response.data)
        with farewise.app.app_context():
            row = farewise.get_db().execute(
                "SELECT user_id FROM searches"
            ).fetchone()
            self.assertIsNotNone(row["user_id"])

        self.client.post(
            "/logout",
            data={"csrf_token": self.csrf_token("/")},
        )
        self.register("second@example.com")
        self.login("second@example.com")
        with farewise.app.app_context():
            second_user = farewise.get_db().execute(
                "SELECT id FROM farewise_users WHERE email = ?",
                ("second@example.com",),
            ).fetchone()
            history = farewise.get_db().execute(
                "SELECT id FROM searches WHERE user_id = ?",
                (second_user["id"],),
            ).fetchall()
        self.assertEqual(history, [])

    def test_guest_recent_journeys_are_saved_and_private_to_the_browser(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch.object(
            farewise,
            "get_road_route",
            return_value={
                "distance_km": 800,
                "drive_minutes": 900,
                "source": "Test road estimate",
                "alternatives": 1,
            },
        ):
            response = self.client.post(
                "/",
                data={
                    "origin": "abuja_city_gate",
                    "destination": "lagos_tbs",
                    "departure_date": tomorrow,
                    "adults": "1",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your recent journeys", response.data)
        self.assertIn(b"Abuja City Gate", response.data)
        self.assertIn(b"Tafawa Balewa Square, Lagos", response.data)
        self.assertIn(b'class="history-replay-button" type="submit">Search again', response.data)
        self.assertIn(b'name="origin" value="abuja_city_gate"', response.data)
        self.assertIn(b'name="destination" value="lagos_tbs"', response.data)
        self.assertIn(
            f'name="departure_date" value="{tomorrow}"'.encode(),
            response.data,
        )

        with patch.object(
            farewise,
            "get_road_route",
            return_value={
                "distance_km": 800,
                "drive_minutes": 900,
                "source": "Test road estimate",
                "alternatives": 1,
            },
        ):
            repeated_search = self.client.post(
                "/",
                data={
                    "origin": "abuja_city_gate",
                    "destination": "lagos_tbs",
                    "departure_date": tomorrow,
                    "adults": "1",
                },
            )
        self.assertEqual(repeated_search.status_code, 200)
        self.assertGreaterEqual(repeated_search.data.count(b"Search again"), 2)

        next_page = self.client.get("/")
        self.assertIn(b"Your recent journeys", next_page.data)
        self.assertIn(b"Abuja City Gate", next_page.data)

        other_browser = farewise.app.test_client()
        private_page = other_browser.get("/")
        self.assertNotIn(b"Your recent journeys", private_page.data)

        with farewise.app.app_context():
            guest_search_count = farewise.get_db().execute(
                "SELECT COUNT(*) AS count FROM searches WHERE user_id IS NULL"
            ).fetchone()["count"]
        self.assertEqual(guest_search_count, 0)

    def test_production_auth_requires_persistent_database_and_secret(self):
        original_vercel = os.environ.get("VERCEL")
        original_database_url = farewise.DATABASE_URL
        original_secret = farewise.app.config["SECRET_KEY"]
        try:
            os.environ["VERCEL"] = "1"
            farewise.DATABASE_URL = None
            farewise.app.config["SECRET_KEY"] = None
            self.assertEqual(self.client.get("/register").status_code, 503)
        finally:
            farewise.DATABASE_URL = original_database_url
            farewise.app.config["SECRET_KEY"] = original_secret
            if original_vercel is None:
                os.environ.pop("VERCEL", None)
            else:
                os.environ["VERCEL"] = original_vercel

    def test_legacy_search_table_is_migrated_for_private_history(self):
        with farewise.app.app_context():
            columns = {
                row["name"]
                for row in farewise.get_db().execute("PRAGMA table_info(searches)")
            }
        self.assertIn("user_id", columns)


class LiveFlightQuoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        farewise.app.config.update(TESTING=True, SECRET_KEY="test-only-secret-key")

    def test_amadeus_search_returns_live_offer_details(self):
        token_response = Mock()
        token_response.json.return_value = {"access_token": "test-access-token"}
        offer_response = Mock()
        offer_response.json.return_value = {
            "data": [{
                "price": {"total": "48500.00", "currency": "NGN"},
                "validatingAirlineCodes": ["P4"],
                "itineraries": [{
                    "duration": "PT1H10M",
                    "segments": [{}, {}],
                }],
            }]
        }
        with (
            patch.dict(os.environ, {
                "AMADEUS_CLIENT_ID": "test-client-id",
                "AMADEUS_CLIENT_SECRET": "test-client-secret",
            }),
            patch.object(farewise.requests, "post", return_value=token_response) as token_call,
            patch.object(farewise.requests, "get", return_value=offer_response) as offers_call,
        ):
            offers, error = farewise.get_live_flight_offers(
                "abuja_city_gate", "lagos_tbs", "2026-11-05", 2
            )

        self.assertIsNone(error)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["total"], farewise.Decimal("48500.00"))
        self.assertEqual(offers[0]["currency"], "NGN")
        self.assertEqual(offers[0]["airlines"], "P4")
        self.assertEqual(offers[0]["stops"], 1)
        self.assertEqual(offers[0]["duration_minutes"], 70)
        self.assertEqual(
            offers_call.call_args.kwargs["params"]["departureDate"], "2026-11-05"
        )
        self.assertEqual(offers_call.call_args.kwargs["params"]["adults"], 2)
        self.assertEqual(
            offers_call.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-access-token",
        )
        self.assertEqual(
            token_call.call_args.args[0],
            "https://api.amadeus.com/v1/security/oauth2/token",
        )

    def test_missing_amadeus_credentials_do_not_show_a_fake_fare(self):
        with (
            patch.dict(os.environ, {
                "AMADEUS_CLIENT_ID": "",
                "AMADEUS_CLIENT_SECRET": "",
            }),
            patch.object(farewise.requests, "post") as token_call,
        ):
            offers, error = farewise.get_live_flight_offers(
                "abuja_city_gate", "lagos_tbs", "2026-11-05", 1
            )

        self.assertIsNone(offers)
        self.assertIn("not connected yet", error)
        token_call.assert_not_called()

    def test_same_airport_landmarks_do_not_trigger_a_flight_search(self):
        with patch.object(farewise.requests, "post") as token_call:
            offers, error = farewise.get_live_flight_offers(
                "abuja_city_gate", "abuja_airport", "2026-11-05", 1
            )

        self.assertIsNone(offers)
        self.assertIn("same airport", error)
        token_call.assert_not_called()

    def test_search_page_labels_road_estimates_and_requires_valid_date(self):
        client = farewise.app.test_client()
        invalid_date = client.post(
            "/",
            data={
                "origin": "abuja_city_gate",
                "destination": "lagos_tbs",
                "departure_date": "2026-02-31",
                "adults": "1",
            },
        )
        self.assertIn(b"Choose today or a future departure date", invalid_date.data)

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with patch.object(
            farewise,
            "get_road_route",
            return_value={
                "distance_km": 800,
                "drive_minutes": 900,
                "source": "Test road estimate",
                "alternatives": 1,
            },
        ):
            response = client.post(
                "/",
                data={
                    "origin": "abuja_city_gate",
                    "destination": "lagos_tbs",
                    "departure_date": tomorrow,
                    "adults": "1",
                },
            )

        self.assertIn(b"not current operator prices", response.data)
        self.assertIn(b"Live flight prices are not connected yet", response.data)
        self.assertNotIn(b"Illustrative flight estimate", response.data)
        self.assertNotIn(b"About 800 km by air", response.data)


if __name__ == "__main__":
    unittest.main()
