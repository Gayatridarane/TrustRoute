"""In-app alerts plus optional email notifications (configured via env vars)."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from ..models import Alert

logger = logging.getLogger(__name__)


def create_alert(api, kind, message, incident=None):
    alert = Alert.objects.create(owner=api.owner, api=api, incident=incident, kind=kind, message=message[:500])
    if settings.ALERT_EMAIL_ENABLED and api.owner.email:
        recipient = api.owner.email
        transaction.on_commit(lambda: _send_email(recipient, kind, message))
    return alert


def _send_email(recipient, kind, message):
    try:
        send_mail(
            subject=f"[TrustRoute] {Alert.Kind(kind).label}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send alert email")
