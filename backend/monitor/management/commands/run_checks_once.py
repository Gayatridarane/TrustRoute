from django.core.management.base import BaseCommand

from monitor.models import MonitoredAPI
from monitor.services.checker import check_api


class Command(BaseCommand):
    help = "Check every active API once, right now (handy for cron or debugging)."

    def handle(self, *args, **options):
        for api in MonitoredAPI.objects.filter(is_active=True):
            result = check_api(api)
            if result:
                self.stdout.write(f"{api.name}: {result.status} ({result.status_code}, {result.response_time_ms} ms)")
