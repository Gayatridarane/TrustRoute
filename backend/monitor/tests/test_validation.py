from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from monitor.services.ssrf import HostResolutionError, UnsafeURLError, validate_public_url

from .helpers import PUBLIC_IP, make_user, patch_public_dns


class SSRFValidationTests(SimpleTestCase):
    def test_rejects_bad_schemes_and_malformed(self):
        for url in ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)", "http://", "not a url", ""]:
            with self.subTest(url=url), self.assertRaises(UnsafeURLError):
                validate_public_url(url)

    def test_rejects_credentials_in_url(self):
        with self.assertRaises(UnsafeURLError):
            validate_public_url("https://user:pass@93.184.216.34/")

    def test_rejects_private_and_local_literals(self):
        for url in [
            "http://127.0.0.1/", "http://localhost/", "http://10.0.0.5/", "http://192.168.1.1/",
            "http://172.16.0.1/", "http://169.254.169.254/latest/meta-data/", "http://[::1]/",
            "http://0.0.0.0/", "http://100.64.0.1/", "http://[::ffff:127.0.0.1]/",
            "http://service.internal/", "http://printer.local/",
        ]:
            with self.subTest(url=url), self.assertRaises(UnsafeURLError):
                validate_public_url(url)

    def test_rejects_hostname_resolving_to_private_ip(self):
        from unittest import mock

        with mock.patch("monitor.services.ssrf._resolve", return_value=["10.1.2.3"]):
            with self.assertRaises(UnsafeURLError):
                validate_public_url("https://evil.example.com/")

    def test_dns_failure_raises_resolution_error(self):
        from unittest import mock

        with mock.patch("monitor.services.ssrf._resolve", side_effect=HostResolutionError("nope")):
            with self.assertRaises(HostResolutionError):
                validate_public_url("https://does-not-exist.example/")

    def test_accepts_public_urls(self):
        validate_public_url(f"https://{PUBLIC_IP}/health")
        with patch_public_dns():
            validate_public_url("https://api.example.com/v1/ping?x=1")

    @override_settings(ALLOW_PRIVATE_URLS=True)
    def test_private_allowed_only_when_explicitly_enabled(self):
        validate_public_url("http://127.0.0.1:8000/health")


class APIValidationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {
            "name": "Payments", "url": "https://api.example.com/health", "method": "GET",
            "expected_status": 200, "interval_seconds": 60, "response_threshold_ms": 800, "timeout_seconds": 10,
        }

    def post(self, **overrides):
        with patch_public_dns():
            return self.client.post("/api/monitored-apis/", {**self.payload, **overrides}, format="json")

    def test_valid_create(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["current_status"], "unknown")

    def test_invalid_url_rejected(self):
        for url in ["http://127.0.0.1/x", "ftp://example.com", "http://169.254.169.254/", "nonsense"]:
            with self.subTest(url=url):
                response = self.post(url=url, name=f"n-{abs(hash(url))}")
                self.assertEqual(response.status_code, 400)
                self.assertIn("url", response.data)

    def test_invalid_method_interval_threshold_status(self):
        self.assertEqual(self.post(method="DELETE").status_code, 400)
        self.assertEqual(self.post(interval_seconds=5).status_code, 400)
        self.assertEqual(self.post(response_threshold_ms=0).status_code, 400)
        self.assertEqual(self.post(expected_status=99).status_code, 400)
        self.assertEqual(self.post(expected_status=700).status_code, 400)

    def test_timeout_must_be_shorter_than_interval(self):
        self.assertEqual(self.post(interval_seconds=30, timeout_seconds=30).status_code, 400)

    def test_duplicate_name_rejected(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post().status_code, 400)
