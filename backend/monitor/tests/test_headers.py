from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from monitor.models import MonitoredAPI
from monitor.services.checker import check_api

from .helpers import FakeResponse, make_api, make_user, patch_public_dns


class HeaderStorageTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {
            "name": "Gemini", "url": "https://generativelanguage.googleapis.com/v1beta/models",
            "method": "GET", "expected_status": 200, "interval_seconds": 60,
            "response_threshold_ms": 1500, "timeout_seconds": 10,
            "headers": {"x-goog-api-key": "SECRET-VALUE-123"},
        }

    def post(self, **overrides):
        with patch_public_dns():
            return self.client.post("/api/monitored-apis/", {**self.payload, **overrides}, format="json")

    def test_header_values_are_encrypted_and_never_returned(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["header_names"], ["x-goog-api-key"])
        self.assertNotIn("headers", response.data)
        self.assertNotIn("SECRET-VALUE-123", str(response.data))
        api = MonitoredAPI.objects.get()
        self.assertNotIn("SECRET-VALUE-123", api.headers_encrypted)
        self.assertEqual(api.headers, {"x-goog-api-key": "SECRET-VALUE-123"})
        listing = self.client.get("/api/monitored-apis/")
        self.assertNotIn("SECRET-VALUE-123", str(listing.data))

    def test_patch_keeps_headers_unless_replaced_or_cleared(self):
        api_id = self.post().data["id"]
        with patch_public_dns():
            self.client.patch(f"/api/monitored-apis/{api_id}/", {"response_threshold_ms": 900}, format="json")
        self.assertEqual(MonitoredAPI.objects.get().headers, {"x-goog-api-key": "SECRET-VALUE-123"})
        with patch_public_dns():
            self.client.patch(f"/api/monitored-apis/{api_id}/", {"headers": {"Authorization": "Bearer t"}}, format="json")
        self.assertEqual(MonitoredAPI.objects.get().headers, {"Authorization": "Bearer t"})
        with patch_public_dns():
            self.client.patch(f"/api/monitored-apis/{api_id}/", {"headers": {}}, format="json")
        self.assertEqual(MonitoredAPI.objects.get().headers, {})

    def test_invalid_headers_rejected(self):
        for bad in [{"Host": "evil"}, {"Content-Length": "1"}, {"bad name": "x"}, {"X-A": "line1\nline2"}, {"X-A": ""}]:
            with self.subTest(headers=bad):
                response = self.post(headers=bad, name=f"n{abs(hash(str(bad)))}")
                self.assertEqual(response.status_code, 400)

    def test_too_many_headers_rejected(self):
        many = {f"X-H{i}": "v" for i in range(11)}
        self.assertEqual(self.post(headers=many).status_code, 400)

    def test_body_only_allowed_with_post(self):
        self.assertEqual(self.post(request_body='{"a": 1}').status_code, 400)
        ok = self.post(method="POST", request_body='{"contents": []}', name="Posting")
        self.assertEqual(ok.status_code, 201, ok.data)


class HeaderSendingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        patcher = mock.patch("monitor.services.checker.validate_public_url")
        patcher.start()
        self.addCleanup(patcher.stop)

    def make(self, **kwargs):
        from monitor.services.secrets import encrypt_headers

        return make_api(self.user, headers_encrypted=encrypt_headers({"X-Api-Key": "abc"}), **kwargs)

    def test_headers_and_body_are_sent(self):
        api = self.make(method="POST", request_body='{"ping": true}')
        with mock.patch("monitor.services.checker.requests.request", return_value=FakeResponse(200)) as sent:
            check_api(api)
        kwargs = sent.call_args.kwargs
        self.assertEqual(kwargs["headers"]["X-Api-Key"], "abc")
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(kwargs["data"], b'{"ping": true}')

    def test_headers_not_leaked_on_cross_host_redirect(self):
        api = self.make()
        responses = [FakeResponse(302, {"Location": "https://other.example.net/x"}), FakeResponse(200)]
        with mock.patch("monitor.services.checker.requests.request", side_effect=responses) as sent:
            check_api(api)
        first, second = sent.call_args_list
        self.assertEqual(first.kwargs["headers"]["X-Api-Key"], "abc")
        self.assertNotIn("X-Api-Key", second.kwargs["headers"])

    def test_headers_kept_on_same_host_redirect(self):
        api = self.make()
        responses = [FakeResponse(301, {"Location": "/v2/health"}), FakeResponse(200)]
        with mock.patch("monitor.services.checker.requests.request", side_effect=responses) as sent:
            check_api(api)
        self.assertEqual(sent.call_args_list[1].kwargs["headers"]["X-Api-Key"], "abc")
