import os
import sys

from django.apps import AppConfig


class MonitorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitor"

    def ready(self):
        from django.conf import settings

        if not settings.SCHEDULER_ENABLED:
            return
        argv = sys.argv
        # Start the in-process scheduler only for `runserver`, and only in the
        # process that actually serves requests (the autoreloader's child, or
        # when --noreload is used). Production/gunicorn deployments should set
        # SCHEDULER_ENABLED=False and run `python manage.py run_scheduler`.
        if "runserver" in argv and (os.environ.get("RUN_MAIN") == "true" or "--noreload" in argv):
            from .scheduler import start_scheduler

            start_scheduler(blocking=False)
