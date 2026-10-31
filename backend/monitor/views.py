from django.conf import settings
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .filters import AlertFilter, IncidentFilter, MonitoredAPIFilter
from .models import Alert, CheckResult, Incident, MonitoredAPI
from .serializers import (
    AlertSerializer,
    CheckResultSerializer,
    IncidentSerializer,
    LoginSerializer,
    MonitoredAPISerializer,
    RegisterSerializer,
)
from .services import analytics
from .services.checker import check_api

User = get_user_model()


def _account_payload(user):
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "config": {
            "min_check_interval_seconds": settings.MIN_CHECK_INTERVAL_SECONDS,
            "max_apis_per_user": settings.MAX_APIS_PER_USER,
            "email_alerts_enabled": settings.ALERT_EMAIL_ENABLED,
            "retention_days": settings.CHECK_RETENTION_DAYS,
        },
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=RegisterSerializer, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        if not settings.ALLOW_REGISTRATION:
            return Response({"detail": "Registration is disabled."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": _account_payload(user)}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=LoginSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": _account_payload(user)})


class MeView(APIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(_account_payload(request.user))


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MonitoredAPIViewSet(viewsets.ModelViewSet):
    serializer_class = MonitoredAPISerializer
    permission_classes = [IsAuthenticated]
    filterset_class = MonitoredAPIFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "url"]
    ordering_fields = ["name", "created_at", "current_status", "last_response_time_ms", "last_checked_at"]
    throttle_scope = None  # must exist on the class so @action(throttle_scope="check") is accepted

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MonitoredAPI.objects.none()
        return MonitoredAPI.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(request=None, responses=CheckResultSerializer)
    @action(detail=True, methods=["post"], throttle_classes=[ScopedRateThrottle], throttle_scope="check")
    def check(self, request, pk=None):
        """Run a health check right now and return the saved result."""
        api = self.get_object()
        result = check_api(api, manual=True)
        if result is None:
            return Response({"detail": "API no longer exists."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CheckResultSerializer(result).data)

    @extend_schema(
        parameters=[OpenApiParameter("status", str, description="healthy | slow | failed")],
        responses=CheckResultSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Paginated check history, newest first."""
        api = self.get_object()
        qs = CheckResult.objects.filter(api=api).order_by("-checked_at")
        wanted = request.query_params.get("status")
        if wanted in CheckResult.Status.values:
            qs = qs.filter(status=wanted)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(CheckResultSerializer(page, many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter("range", str, enum=["24h", "7d"], description="Default 24h")],
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Summary statistics and a bucketed time series for charts."""
        api = self.get_object()
        range_key = request.query_params.get("range", "24h")
        if range_key not in analytics.RANGES:
            return Response({"range": "Must be '24h' or '7d'."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(analytics.api_analytics(api, range_key))


class IncidentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = IncidentFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["api__name", "reason"]
    ordering_fields = ["started_at", "resolved_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Incident.objects.none()
        return Incident.objects.filter(api__owner=self.request.user).select_related("api")


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = AlertFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Alert.objects.none()
        return Alert.objects.filter(owner=self.request.user).select_related("api")

    @extend_schema(request=None, responses=AlertSerializer)
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        alert = self.get_object()
        if not alert.is_read:
            alert.is_read = True
            alert.save(update_fields=["is_read"])
        return Response(AlertSerializer(alert).data)

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        data = analytics.dashboard_summary(request.user)
        data["recent_incidents"] = IncidentSerializer(data["recent_incidents"], many=True).data
        return Response(data)
