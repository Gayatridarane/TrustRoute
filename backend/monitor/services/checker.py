"""Health-check service: performs the HTTP request and persists the result."""
import logging
import time
from urllib.parse import urljoin, urlsplit

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import CheckResult, MonitoredAPI
from . import incidents
from .ssrf import HostResolutionError, UnsafeURLError, validate_public_url

logger = logging.getLogger(__name__)

REDIRECT_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5
DNS_MARKERS = ("name or service not known", "nameresolutionerror", "getaddrinfo", "failed to resolve", "no address associated")


def _send(method, url, timeout, headers=None, body=""):
    """Single HTTP request, no automatic redirects, response body not downloaded."""
    merged = {"User-Agent": settings.CHECK_USER_AGENT}
    if headers:
        merged.update(headers)
    if body and not any(name.lower() == "content-type" for name in merged):
        merged["Content-Type"] = "application/json"
    return requests.request(
        method,
        url,
        timeout=timeout,
        allow_redirects=False,
        stream=True,
        headers=merged,
        data=body.encode("utf-8") if body else None,
    )


def _failed(message, status_code=None, elapsed_ms=None):
    return {"status": CheckResult.Status.FAILED, "status_code": status_code, "response_time_ms": elapsed_ms, "error": message}


def execute_check(method, url, expected_status, timeout, threshold_ms, headers=None, body=""):
    """Run one check and return a plain dict (no database access)."""
    start = time.perf_counter()
    current_url, current_method = url, method
    send_headers, send_body = headers or {}, body or ""
    origin = urlsplit(url).netloc.lower()
    code = None
    try:
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current_url)  # SSRF guard on every hop
            response = _send(current_method, current_url, timeout, send_headers, send_body)
            try:
                code = response.status_code
                location = response.headers.get("Location")
            finally:
                response.close()
            if code in REDIRECT_CODES and code != expected_status and location:
                current_url = urljoin(current_url, location)
                if code == 303:
                    current_method = "GET"
                    send_body = ""
                if urlsplit(current_url).netloc.lower() != origin:
                    # Never leak API keys or payloads to a different host.
                    send_headers, send_body = {}, ""
                continue
            break
        else:
            return _failed(f"Too many redirects (more than {MAX_REDIRECTS}).")
    except HostResolutionError:
        return _failed("DNS resolution failed: the hostname could not be resolved.")
    except UnsafeURLError as exc:
        return _failed(f"Blocked destination: {exc}")
    except requests.exceptions.Timeout:
        return _failed(f"Request timed out after {timeout}s.")
    except requests.exceptions.SSLError:
        return _failed("SSL error: the certificate could not be verified.")
    except requests.exceptions.ConnectionError as exc:
        text = str(exc).lower()
        if any(marker in text for marker in DNS_MARKERS):
            return _failed("DNS resolution failed: the hostname could not be resolved.")
        return _failed("Connection failed: could not connect to the host.")
    except requests.exceptions.RequestException as exc:
        return _failed(f"Request failed ({type(exc).__name__}).")
    except Exception:  # never let one bad endpoint crash the worker
        logger.exception("Unexpected error while checking %s", url)
        return _failed("Unexpected error while performing the check.")

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    if code != expected_status:
        return _failed(f"Unexpected HTTP status {code} (expected {expected_status}).", code, elapsed_ms)
    if elapsed_ms > threshold_ms:
        return {
            "status": CheckResult.Status.SLOW,
            "status_code": code,
            "response_time_ms": elapsed_ms,
            "error": f"Response time {elapsed_ms:.0f} ms exceeded threshold of {threshold_ms} ms.",
        }
    return {"status": CheckResult.Status.HEALTHY, "status_code": code, "response_time_ms": elapsed_ms, "error": ""}


def check_api(api, manual=False):
    """Check `api`, save the CheckResult, update state and run incident detection.

    Returns the CheckResult, or None if the API was deleted meanwhile.
    """
    outcome = execute_check(
        api.method, api.url, api.expected_status, api.timeout_seconds, api.response_threshold_ms,
        api.headers, api.request_body,
    )
    now = timezone.now()
    with transaction.atomic():
        try:
            locked = MonitoredAPI.objects.select_for_update().get(pk=api.pk)
        except MonitoredAPI.DoesNotExist:
            return None
        previous = locked.current_status
        result = CheckResult.objects.create(
            api=locked,
            checked_at=now,
            status=outcome["status"],
            status_code=outcome["status_code"],
            response_time_ms=outcome["response_time_ms"],
            error_message=outcome["error"][:500],
            is_manual=manual,
        )
        locked.current_status = result.status
        locked.last_checked_at = now
        locked.last_response_time_ms = result.response_time_ms
        locked.save(update_fields=["current_status", "last_checked_at", "last_response_time_ms", "updated_at"])
        incidents.handle_result(locked, result, previous)
    logger.info("Checked api=%s status=%s code=%s ms=%s", api.pk, result.status, result.status_code, result.response_time_ms)
    return result
