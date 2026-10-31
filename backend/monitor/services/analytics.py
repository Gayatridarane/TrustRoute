"""Analytics helpers.

Check-based uptime:
    uptime % = successful checks / total completed checks * 100
A check is *successful* when the endpoint answered with the expected HTTP
status (healthy OR slow). A check is *failed* on any error or unexpected
status. Returns None when there are no checks (instead of a misleading 100%).
"""
import math
from datetime import timedelta

from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone

from ..models import CheckResult, Incident

RANGES = {"24h": (24, 1), "7d": (24 * 7, 6)}  # (total hours, bucket size in hours)


def uptime_percent(queryset):
    agg = queryset.aggregate(total=Count("id"), failed=Count("id", filter=Q(status=CheckResult.Status.FAILED)))
    if not agg["total"]:
        return None
    return round((agg["total"] - agg["failed"]) / agg["total"] * 100, 2)


def timeseries(checks, incidents, since, total_hours, bucket_hours):
    n_buckets = math.ceil(total_hours / bucket_hours)
    width = bucket_hours * 3600
    buckets = [
        {
            "bucket_start": (since + timedelta(hours=i * bucket_hours)).isoformat(),
            "_sum": 0.0,
            "_n": 0,
            "success": 0,
            "failed": 0,
            "incidents": 0,
        }
        for i in range(n_buckets)
    ]

    def index(moment):
        i = int((moment - since).total_seconds() // width)
        return min(max(i, 0), n_buckets - 1)

    for checked_at, status, ms in checks.values_list("checked_at", "status", "response_time_ms").iterator():
        b = buckets[index(checked_at)]
        if status == CheckResult.Status.FAILED:
            b["failed"] += 1
        else:
            b["success"] += 1
        if ms is not None:
            b["_sum"] += ms
            b["_n"] += 1
    for started_at in incidents.values_list("started_at", flat=True):
        buckets[index(started_at)]["incidents"] += 1

    series = []
    for b in buckets:
        total = b["success"] + b["failed"]
        series.append(
            {
                "bucket_start": b["bucket_start"],
                "avg_response_ms": round(b["_sum"] / b["_n"], 1) if b["_n"] else None,
                "success": b["success"],
                "failed": b["failed"],
                "checks": total,
                "uptime_percent": round(b["success"] / total * 100, 2) if total else None,
                "incidents": b["incidents"],
            }
        )
    return series


def api_analytics(api, range_key="24h"):
    if range_key not in RANGES:
        raise ValueError("range must be '24h' or '7d'")
    total_hours, bucket_hours = RANGES[range_key]
    now = timezone.now()
    since = now - timedelta(hours=total_hours)
    checks = CheckResult.objects.filter(api=api, checked_at__gte=since)
    incidents = Incident.objects.filter(api=api, started_at__gte=since)

    agg = checks.aggregate(
        total=Count("id"),
        failed=Count("id", filter=Q(status=CheckResult.Status.FAILED)),
        avg=Avg("response_time_ms"),
        min=Min("response_time_ms"),
        max=Max("response_time_ms"),
    )
    return {
        "range": range_key,
        "since": since.isoformat(),
        "summary": {
            "total_checks": agg["total"],
            "successful_checks": agg["total"] - agg["failed"],
            "failed_checks": agg["failed"],
            "uptime_percent": uptime_percent(checks),
            "avg_response_ms": round(agg["avg"], 1) if agg["avg"] is not None else None,
            "min_response_ms": agg["min"],
            "max_response_ms": agg["max"],
            "incident_count": incidents.count(),
        },
        "uptime_24h": uptime_percent(CheckResult.objects.filter(api=api, checked_at__gte=now - timedelta(hours=24))),
        "uptime_7d": uptime_percent(CheckResult.objects.filter(api=api, checked_at__gte=now - timedelta(days=7))),
        "series": timeseries(checks, incidents, since, total_hours, bucket_hours),
    }


def dashboard_summary(user):
    from ..models import MonitoredAPI

    now = timezone.now()
    since = now - timedelta(hours=24)
    apis = MonitoredAPI.objects.filter(owner=user)
    counts = apis.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        healthy=Count("id", filter=Q(current_status=MonitoredAPI.State.HEALTHY)),
        slow=Count("id", filter=Q(current_status=MonitoredAPI.State.SLOW)),
        failed=Count("id", filter=Q(current_status=MonitoredAPI.State.FAILED)),
        unknown=Count("id", filter=Q(current_status=MonitoredAPI.State.UNKNOWN)),
    )
    checks = CheckResult.objects.filter(api__owner=user, checked_at__gte=since)
    avg = checks.aggregate(avg=Avg("response_time_ms"))["avg"]
    incidents = Incident.objects.filter(api__owner=user)
    recent = incidents.select_related("api")[:5]
    return {
        "total_apis": counts["total"],
        "active_apis": counts["active"],
        "healthy_apis": counts["healthy"],
        "slow_apis": counts["slow"],
        "failed_apis": counts["failed"],
        "unknown_apis": counts["unknown"],
        "avg_response_ms": round(avg, 1) if avg is not None else None,
        "uptime_24h": uptime_percent(checks),
        "checks_24h": checks.count(),
        "open_incidents": incidents.filter(status=Incident.Status.OPEN).count(),
        "status_distribution": [
            {"status": "healthy", "count": counts["healthy"]},
            {"status": "slow", "count": counts["slow"]},
            {"status": "failed", "count": counts["failed"]},
            {"status": "unknown", "count": counts["unknown"]},
        ],
        "response_trend": timeseries(checks, incidents.filter(started_at__gte=since), since, 24, 1),
        "recent_incidents": recent,
    }
