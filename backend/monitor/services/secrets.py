"""Encrypt stored request headers (API keys, tokens) at rest.

The key is derived from DJANGO_SECRET_KEY. If that key is ever changed, saved
headers can no longer be decrypted and are treated as empty (re-enter them).
"""
import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    digest = hashlib.sha256(("trustroute-headers:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_headers(headers):
    if not headers:
        return ""
    return _fernet().encrypt(json.dumps(headers).encode()).decode()


def decrypt_headers(token):
    if not token:
        return {}
    try:
        data = json.loads(_fernet().decrypt(token.encode()))
    except (InvalidToken, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
