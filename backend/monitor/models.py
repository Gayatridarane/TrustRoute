from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class MonitoredAPI(models.Model):
    class Method(models.TextChoices):
        GET = "GET", "GET"
        HEAD = "HEAD", "HEAD"
        POST = "POST", "POST"
        OPTIONS = "OPTIONS", "OPTIONS"

    class State(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        HEALTHY = "healthy", "Healthy"
        SLOW = "slow", "Slow"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monitored_apis")
    name = models.CharField(max_length=120)
    url = models.URLField(max_length=2000)
    method = models.CharField(max_length=8, choices=Method.choices, default=Method.GET)
    expected_status = models.PositiveSmallIntegerField(
        default=200, validators=[MinValueValidator(100), MaxValueValidator(599)]
    )
    interval_seconds = models.PositiveIntegerField(
        default=60, validators=[MinValueValidator(1), MaxValueValidator(86400)]
    )
    response_threshold_ms = models.PositiveIntegerField(
        default=1000, validators=[MinValueValidator(1), MaxValueValidator(60000)]
    )
    timeout_seconds = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1), MaxValueValidator(30)]
    )
    is_active = models.BooleanField(default=True)
    # Optional request customisation. Header values are encrypted at rest (see services/secrets.py).
    headers_encrypted = models.TextField(blank=True, default="")
    request_body = models.TextField(blank=True, default="")

    # Denormalised "current state" for fast dashboards
    current_status = models.CharField(max_length=10, choices=State.choices, default=State.UNKNOWN)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_response_time_ms = models.FloatField(null=True, blank=True)
    # Used by the scheduler as an atomic "claim" so a check never runs twice.
    next_check_at = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="uniq_api_name_per_owner")]
        indexes = [
            models.Index(fields=["owner", "is_active"], name="api_owner_active_idx"),
            models.Index(fields=["is_active", "next_check_at"], name="api_due_idx"),
        ]

    @property
    def headers(self):
        from .services.secrets import decrypt_headers

        return decrypt_headers(self.headers_encrypted)

    @property
    def header_names(self):
        return sorted(self.headers.keys(), key=str.lower)

    def __str__(self):
        return f"{self.name} ({self.method} {self.url})"


class CheckResult(models.Model):
    class Status(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        SLOW = "slow", "Slow"
        FAILED = "failed", "Failed"

    api = models.ForeignKey(MonitoredAPI, on_delete=models.CASCADE, related_name="checks")
    checked_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=Status.choices)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_time_ms = models.FloatField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    is_manual = models.BooleanField(default=False)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["api", "-checked_at"], name="check_api_time_idx"),
            models.Index(fields=["checked_at"], name="check_time_idx"),
        ]

    def __str__(self):
        return f"{self.api_id} {self.status} @ {self.checked_at:%Y-%m-%d %H:%M:%S}"


class Incident(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    api = models.ForeignKey(MonitoredAPI, on_delete=models.CASCADE, related_name="incidents")
    started_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=500)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["api", "status"], name="incident_api_status_idx"),
            models.Index(fields=["started_at"], name="incident_started_idx"),
        ]

    @property
    def duration_seconds(self):
        end = self.resolved_at or timezone.now()
        return max(0, int((end - self.started_at).total_seconds()))

    @property
    def duration(self):
        return timedelta(seconds=self.duration_seconds)

    def __str__(self):
        return f"Incident #{self.pk} on API {self.api_id} ({self.status})"


class Alert(models.Model):
    class Kind(models.TextChoices):
        FAILURE = "failure", "API failure"
        RECOVERY = "recovery", "API recovery"
        SLOW = "slow", "Slow response"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts")
    api = models.ForeignKey(MonitoredAPI, on_delete=models.CASCADE, related_name="alerts")
    incident = models.ForeignKey(Incident, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "is_read", "-created_at"], name="alert_owner_read_idx")]

    def __str__(self):
        return f"{self.kind}: {self.message[:60]}"
