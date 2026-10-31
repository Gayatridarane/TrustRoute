from datetime import datetime, time

import django_filters
from django.utils import timezone

from .models import Alert, Incident, MonitoredAPI


def _start_of_day(value):
    return timezone.make_aware(datetime.combine(value, time.min))


def _end_of_day(value):
    return timezone.make_aware(datetime.combine(value, time.max))


class MonitoredAPIFilter(django_filters.FilterSet):
    class Meta:
        model = MonitoredAPI
        fields = ["is_active", "current_status", "method"]


class IncidentFilter(django_filters.FilterSet):
    api = django_filters.NumberFilter(field_name="api_id")
    status = django_filters.ChoiceFilter(choices=Incident.Status.choices)
    date_from = django_filters.DateFilter(method="filter_date_from")
    date_to = django_filters.DateFilter(method="filter_date_to")

    class Meta:
        model = Incident
        fields = ["api", "status", "date_from", "date_to"]

    # Python-side datetimes avoid MySQL timezone-table requirements of `__date` lookups.
    def filter_date_from(self, queryset, name, value):
        return queryset.filter(started_at__gte=_start_of_day(value))

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(started_at__lte=_end_of_day(value))


class AlertFilter(django_filters.FilterSet):
    api = django_filters.NumberFilter(field_name="api_id")

    class Meta:
        model = Alert
        fields = ["api", "kind", "is_read"]
