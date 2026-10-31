"""Incident detection: open on failure, close on recovery, never duplicate."""
from ..models import Alert, CheckResult, Incident
from . import notifications


def handle_result(api, result, previous_status):
    """Must be called inside the transaction that holds a row lock on `api`.

    The row lock serialises concurrent checks of the same API, so at most one
    open incident can exist per API.
    """
    open_incident = Incident.objects.filter(api=api, status=Incident.Status.OPEN).order_by("-started_at").first()

    if result.status == CheckResult.Status.FAILED:
        if open_incident is None:
            incident = Incident.objects.create(
                api=api,
                started_at=result.checked_at,
                reason=result.error_message,
                status_code=result.status_code,
            )
            notifications.create_alert(
                api, Alert.Kind.FAILURE, f"{api.name} failed: {result.error_message}", incident
            )
        return

    if open_incident is not None:
        open_incident.status = Incident.Status.RESOLVED
        open_incident.resolved_at = result.checked_at
        open_incident.save(update_fields=["status", "resolved_at", "updated_at"])
        notifications.create_alert(
            api,
            Alert.Kind.RECOVERY,
            f"{api.name} recovered after {_humanize(open_incident.duration_seconds)}.",
            open_incident,
        )

    if result.status == CheckResult.Status.SLOW and previous_status != CheckResult.Status.SLOW:
        notifications.create_alert(api, Alert.Kind.SLOW, f"{api.name} is slow: {result.error_message}")


def _humanize(seconds):
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"
