from django.core.management.base import BaseCommand

from monitor.scheduler import start_scheduler


class Command(BaseCommand):
    help = "Run the monitoring scheduler as a dedicated worker process (recommended for production)."

    def handle(self, *args, **options):
        self.stdout.write("TrustRoute scheduler running. Press Ctrl+C to stop.")
        try:
            start_scheduler(blocking=True)
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Scheduler stopped.")
