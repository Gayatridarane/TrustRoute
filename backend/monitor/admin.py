from django.contrib import admin

from .models import Alert, CheckResult, Incident, MonitoredAPI


@admin.register(MonitoredAPI)
class MonitoredAPIAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "url", "method", "current_status", "is_active", "last_checked_at")
    list_filter = ("current_status", "is_active", "method")
    search_fields = ("name", "url", "owner__username")


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = ("api", "status", "status_code", "response_time_ms", "checked_at")
    list_filter = ("status",)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("api", "status", "started_at", "resolved_at", "reason")
    list_filter = ("status",)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("owner", "api", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
