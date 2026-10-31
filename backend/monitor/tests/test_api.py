from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from monitor.models import Alert, CheckResult, Incident, MonitoredAPI

from .helpers import FakeResponse, make_api, make_user


class AuthAndIsolationTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.api = make_api(self.alice)

    def test_requires_authentication(self):
        client = APIClient()
        for path in ["/api/monitored-apis/", "/api/incidents/", "/api/alerts/", "/api/dashboard/summary/"]:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 401)

    def test_register_login_flow(self):
        client = APIClient()
        r = client.post("/api/auth/register/", {"username": "carol", "email": "c@example.com", "password": "Sup3r-secret-pw"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn("token", r.data)
        r = client.post("/api/auth/login/", {"username": "carol", "password": "Sup3r-secret-pw"}, format="json")
        self.assertEqual(r.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Token {r.data['token']}")
        self.assertEqual(client.get("/api/auth/me/").data["username"], "carol")
        bad = APIClient().post("/api/auth/login/", {"username": "carol", "password": "wrong"}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_user_cannot_access_other_users_data(self):
        incident = Incident.objects.create(api=self.api, started_at=timezone.now(), reason="x")
        client = APIClient()
        client.force_authenticate(self.bob)
        self.assertEqual(client.get("/api/monitored-apis/").data["count"], 0)
        self.assertEqual(client.get(f"/api/monitored-apis/{self.api.pk}/").status_code, 404)
        self.assertEqual(client.patch(f"/api/monitored-apis/{self.api.pk}/", {"name": "hax"}, format="json").status_code, 404)
        self.assertEqual(client.delete(f"/api/monitored-apis/{self.api.pk}/").status_code, 404)
        self.assertEqual(client.post(f"/api/monitored-apis/{self.api.pk}/check/").status_code, 404)
        self.assertEqual(client.get(f"/api/monitored-apis/{self.api.pk}/history/").status_code, 404)
        self.assertEqual(client.get("/api/incidents/").data["count"], 0)
        self.assertEqual(client.get(f"/api/incidents/{incident.pk}/").status_code, 404)
        self.assertTrue(MonitoredAPI.objects.filter(pk=self.api.pk).exists())


class EndpointTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.api = make_api(self.user)
        patcher = mock.patch("monitor.services.checker.validate_public_url")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_patch_toggle_and_delete(self):
        r = self.client.patch(f"/api/monitored-apis/{self.api.pk}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_active"])
        self.assertEqual(self.client.delete(f"/api/monitored-apis/{self.api.pk}/").status_code, 204)
        self.assertFalse(MonitoredAPI.objects.exists())

    def test_manual_check_endpoint_and_history(self):
        with mock.patch("monitor.services.checker._send", return_value=FakeResponse(200)):
            r = self.client.post(f"/api/monitored-apis/{self.api.pk}/check/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "healthy")
        self.assertTrue(r.data["is_manual"])
        history = self.client.get(f"/api/monitored-apis/{self.api.pk}/history/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data["count"], 1)

    def test_analytics_endpoint(self):
        CheckResult.objects.create(api=self.api, status="healthy", response_time_ms=120, checked_at=timezone.now())
        r = self.client.get(f"/api/monitored-apis/{self.api.pk}/analytics/?range=7d")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["summary"]["total_checks"], 1)
        self.assertEqual(r.data["uptime_7d"], 100.0)
        self.assertEqual(self.client.get(f"/api/monitored-apis/{self.api.pk}/analytics/?range=1y").status_code, 400)

    def test_incident_filters_and_search(self):
        other = make_api(self.user, name="Other", url="https://other.example.com")
        now = timezone.now()
        Incident.objects.create(api=self.api, started_at=now - timedelta(days=10), resolved_at=now - timedelta(days=10) + timedelta(minutes=5),
                                reason="Unexpected HTTP status 500", status="resolved")
        Incident.objects.create(api=other, started_at=now - timedelta(minutes=1), reason="Request timed out", status="open")

        def ids(query):
            return [i["api_name"] for i in self.client.get(f"/api/incidents/?{query}").data["results"]]

        self.assertEqual(ids("status=open"), ["Other"])
        self.assertEqual(ids("status=resolved"), ["Example"])
        self.assertEqual(ids(f"api={self.api.pk}"), ["Example"])
        self.assertEqual(ids("search=timed"), ["Other"])
        today = timezone.localdate().isoformat()
        self.assertEqual(ids(f"date_from={today}"), ["Other"])
        self.assertEqual(len(ids("")), 2)

    def test_alerts_mark_read(self):
        Alert.objects.create(owner=self.user, api=self.api, kind="failure", message="down")
        Alert.objects.create(owner=self.user, api=self.api, kind="recovery", message="up")
        self.assertEqual(self.client.get("/api/alerts/?is_read=false").data["count"], 2)
        alert_id = self.client.get("/api/alerts/").data["results"][0]["id"]
        self.assertTrue(self.client.post(f"/api/alerts/{alert_id}/mark-read/").data["is_read"])
        self.assertEqual(self.client.post("/api/alerts/mark-all-read/").data["updated"], 1)
        self.assertEqual(self.client.get("/api/alerts/?is_read=false").data["count"], 0)

    def test_schema_generation(self):
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)


class DashboardTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_empty_dashboard(self):
        data = self.client.get("/api/dashboard/summary/").data
        self.assertEqual(data["total_apis"], 0)
        self.assertIsNone(data["avg_response_ms"])
        self.assertIsNone(data["uptime_24h"])
        self.assertEqual(data["recent_incidents"], [])

    def test_dashboard_metrics_use_real_data(self):
        now = timezone.now()
        healthy = make_api(self.user, name="A", current_status="healthy")
        slow = make_api(self.user, name="B", current_status="slow")
        failed = make_api(self.user, name="C", current_status="failed")
        make_api(self.user, name="D", current_status="unknown", is_active=False)
        for api, status, ms in [(healthy, "healthy", 100), (healthy, "healthy", 200), (slow, "slow", 1500), (failed, "failed", None)]:
            CheckResult.objects.create(api=api, status=status, response_time_ms=ms, checked_at=now - timedelta(minutes=10))
        Incident.objects.create(api=failed, started_at=now - timedelta(minutes=10), reason="HTTP 500", status_code=500)
        # old data outside the 24h window must be ignored
        CheckResult.objects.create(api=healthy, status="failed", checked_at=now - timedelta(days=3))

        data = self.client.get("/api/dashboard/summary/").data
        self.assertEqual(data["total_apis"], 4)
        self.assertEqual(data["active_apis"], 3)
        self.assertEqual((data["healthy_apis"], data["slow_apis"], data["failed_apis"], data["unknown_apis"]), (1, 1, 1, 1))
        self.assertEqual(data["avg_response_ms"], 600.0)  # (100+200+1500)/3
        self.assertEqual(data["uptime_24h"], 75.0)  # 3 of 4 successful
        self.assertEqual(data["checks_24h"], 4)
        self.assertEqual(data["open_incidents"], 1)
        self.assertEqual(data["recent_incidents"][0]["api_name"], "C")
        self.assertEqual(len(data["response_trend"]), 24)
        self.assertEqual({d["status"]: d["count"] for d in data["status_distribution"]}["healthy"], 1)
