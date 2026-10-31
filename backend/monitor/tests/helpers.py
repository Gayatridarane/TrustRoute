from unittest import mock

from django.contrib.auth import get_user_model

from monitor.models import MonitoredAPI

PUBLIC_IP = "93.184.216.34"


class FakeResponse:
    """Minimal stand-in for requests.Response used by the mocked HTTP layer."""

    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}

    def close(self):
        pass


def make_user(username="alice", password="Str0ng-pass-123"):
    return get_user_model().objects.create_user(username=username, email=f"{username}@example.com", password=password)


def make_api(owner, **kwargs):
    defaults = dict(name="Example", url="https://api.example.com/health", expected_status=200,
                    response_threshold_ms=1000, timeout_seconds=5, interval_seconds=60)
    defaults.update(kwargs)
    return MonitoredAPI.objects.create(owner=owner, **defaults)


def patch_public_dns():
    """Make every hostname resolve to a public IP so no real DNS is used."""
    return mock.patch("monitor.services.ssrf._resolve", return_value=[PUBLIC_IP])
