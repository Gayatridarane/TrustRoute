import re

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import Alert, CheckResult, Incident, MonitoredAPI
from .services.secrets import encrypt_headers
from .services.ssrf import UnsafeURLError, validate_public_url

User = get_user_model()

HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")
FORBIDDEN_HEADERS = {"host", "content-length", "transfer-encoding", "connection", "upgrade", "te", "trailer"}
MAX_HEADERS = 10


class MonitoredAPISerializer(serializers.ModelSerializer):
    # Header values are write-only: stored encrypted and never returned. Only names are shown.
    headers = serializers.DictField(
        child=serializers.CharField(max_length=2000), write_only=True, required=False,
        help_text="Custom request headers, e.g. {\"x-goog-api-key\": \"...\"}. Send {} to remove all saved headers.",
    )
    header_names = serializers.SerializerMethodField()
    request_body = serializers.CharField(max_length=5000, required=False, allow_blank=True)

    def get_header_names(self, obj):
        return obj.header_names

    class Meta:
        model = MonitoredAPI
        fields = [
            "id", "name", "url", "method", "expected_status", "interval_seconds",
            "response_threshold_ms", "timeout_seconds", "is_active",
            "headers", "header_names", "request_body",
            "current_status", "last_checked_at", "last_response_time_ms", "next_check_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "current_status", "last_checked_at", "last_response_time_ms",
            "next_check_at", "created_at", "updated_at",
        ]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_url(self, value):
        try:
            validate_public_url(value)
        except UnsafeURLError as exc:
            raise serializers.ValidationError(str(exc))
        return value.strip()

    def validate_headers(self, value):
        if len(value) > MAX_HEADERS:
            raise serializers.ValidationError(f"At most {MAX_HEADERS} headers are allowed.")
        clean, seen = {}, set()
        for name, val in value.items():
            name, val = str(name).strip(), str(val).strip()
            if not HEADER_NAME_RE.match(name):
                raise serializers.ValidationError(f"Invalid header name: {name[:40]!r}.")
            if name.lower() in FORBIDDEN_HEADERS:
                raise serializers.ValidationError(f"The header '{name}' cannot be set.")
            if name.lower() in seen:
                raise serializers.ValidationError(f"Header '{name}' is listed twice.")
            if not val or "\r" in val or "\n" in val:
                raise serializers.ValidationError(f"Header '{name}' needs a single-line value.")
            seen.add(name.lower())
            clean[name] = val
        return clean

    def validate_interval_seconds(self, value):
        minimum = settings.MIN_CHECK_INTERVAL_SECONDS
        if value < minimum:
            raise serializers.ValidationError(f"Interval must be at least {minimum} seconds.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        instance = self.instance
        name = attrs.get("name", instance.name if instance else None)
        duplicates = MonitoredAPI.objects.filter(owner=request.user, name__iexact=name)
        if instance:
            duplicates = duplicates.exclude(pk=instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError({"name": "You already monitor an API with this name."})
        if instance is None:
            if MonitoredAPI.objects.filter(owner=request.user).count() >= settings.MAX_APIS_PER_USER:
                raise serializers.ValidationError(f"You can monitor at most {settings.MAX_APIS_PER_USER} APIs.")
        method = attrs.get("method", instance.method if instance else MonitoredAPI.Method.GET)
        body = attrs.get("request_body", instance.request_body if instance else "")
        if body and method != MonitoredAPI.Method.POST:
            raise serializers.ValidationError({"request_body": "A request body can only be used with the POST method."})
        interval = attrs.get("interval_seconds", instance.interval_seconds if instance else 60)
        timeout = attrs.get("timeout_seconds", instance.timeout_seconds if instance else 10)
        if timeout >= interval:
            raise serializers.ValidationError({"timeout_seconds": "Timeout must be shorter than the check interval."})
        return attrs

    def create(self, validated_data):
        headers = validated_data.pop("headers", None)
        if headers:
            validated_data["headers_encrypted"] = encrypt_headers(headers)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "headers" in validated_data:  # omitted = keep saved headers; {} = remove them
            validated_data["headers_encrypted"] = encrypt_headers(validated_data.pop("headers"))
        reschedule = (
            validated_data.get("is_active") is True and not instance.is_active
        ) or "interval_seconds" in validated_data
        if reschedule:
            validated_data["next_check_at"] = timezone.now()
        return super().update(instance, validated_data)


class CheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckResult
        fields = ["id", "api", "checked_at", "status", "status_code", "response_time_ms", "error_message", "is_manual"]
        read_only_fields = fields


class IncidentSerializer(serializers.ModelSerializer):
    api_id = serializers.IntegerField(read_only=True)
    api_name = serializers.CharField(source="api.name", read_only=True)
    api_url = serializers.CharField(source="api.url", read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id", "api_id", "api_name", "api_url", "started_at", "resolved_at",
            "duration_seconds", "reason", "status_code", "status",
        ]
        read_only_fields = fields


class AlertSerializer(serializers.ModelSerializer):
    api_name = serializers.CharField(source="api.name", read_only=True)

    class Meta:
        model = Alert
        fields = ["id", "api", "api_name", "incident", "kind", "message", "is_read", "created_at"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is taken.")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs.get("email", ""))
        try:
            validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None or not user.is_active:
            raise serializers.ValidationError("Invalid username or password.")
        attrs["user"] = user
        return attrs
