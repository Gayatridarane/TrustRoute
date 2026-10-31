from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from monitor.models import CheckResult


class Command(BaseCommand):
    help = "Delete check results older than CHECK_RETENTION_DAYS (or --days)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.CHECK_RETENTION_DAYS)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        deleted, _ = CheckResult.objects.filter(checked_at__lt=cutoff).delete()
        self.stdout.write(f"Deleted {deleted} old check results.")
