"""SSRF protection for user-supplied URLs.

`validate_public_url` is called (a) when a user saves a URL and (b) before
EVERY outgoing request, including each redirect hop, so a hostname that later
resolves to a private address (or redirects there) is still blocked.

Known limitation: there is a small time-of-check/time-of-use window between our
DNS lookup and the connection made by `requests` (DNS rebinding). For hostile
multi-tenant deployments, run checks from an egress-restricted network or pin
the resolved IP with a custom transport adapter.
"""
import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings

BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "metadata", "instance-data"}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain", ".home.arpa")


class UnsafeURLError(ValueError):
    """The URL points somewhere we refuse to send requests."""


class HostResolutionError(UnsafeURLError):
    """The hostname could not be resolved (DNS failure)."""


def _ip_is_blocked(ip):
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    # `not is_global` covers private, loopback, link-local (169.254.169.254
    # cloud metadata), CGNAT 100.64/10, reserved, unspecified, ULA, etc.
    return (not ip.is_global) or ip.is_multicast


def _resolve(host, port):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise HostResolutionError("Could not resolve the hostname.")
    return sorted({info[4][0].split("%")[0] for info in infos})


def validate_public_url(url):
    """Raise UnsafeURLError if `url` is not an acceptable public http(s) target."""
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURLError("URL is required.")
    if len(url) > 2000:
        raise UnsafeURLError("URL is too long.")
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        raise UnsafeURLError("URL is malformed.")
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("Only http:// and https:// URLs are allowed.")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("URL must include a hostname.")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs containing credentials are not allowed.")

    if settings.ALLOW_PRIVATE_URLS:
        return []

    lowered = host.lower().rstrip(".")
    if lowered in BLOCKED_HOSTNAMES or lowered.endswith(BLOCKED_SUFFIXES):
        raise UnsafeURLError("This hostname is not allowed (local or internal address).")

    try:
        addresses = [str(ipaddress.ip_address(host))]  # IP literal: no DNS needed
    except ValueError:
        addresses = _resolve(host, port or (443 if parts.scheme == "https" else 80))

    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise UnsafeURLError("Hostname resolved to an invalid address.")
        if _ip_is_blocked(ip):
            raise UnsafeURLError(
                "This URL resolves to a private, loopback, link-local or otherwise non-public address."
            )
    return addresses
