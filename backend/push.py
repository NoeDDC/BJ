"""Web Push (VAPID) helpers.

The VAPID key pair is generated once and saved as a PEM file next to the
SQLite DB (same persistent volume in production), so it survives restarts
and redeploys. If it ever regenerates, every existing browser subscription
becomes invalid and users must re-enable notifications.
"""
import base64
import json
import os

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid01
from pywebpush import WebPushException, webpush

VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:noedrionduchapois@gmail.com")

_vapid = None
_vapid_path = None
_public_key_b64 = None


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def init_vapid(db_path):
    """Load the VAPID key pair from disk, generating it on first run.

    This is stored locally next to `db_path` regardless of which DB backend
    is active (SQLite or Postgres), so the directory isn't guaranteed to
    exist yet — unlike db_sqlite.init_db(), Postgres never creates it.
    """
    global _vapid, _vapid_path, _public_key_b64
    vapid_dir = os.path.dirname(db_path) or "."
    os.makedirs(vapid_dir, exist_ok=True)
    _vapid_path = os.path.join(vapid_dir, "vapid_private_key.pem")

    if os.path.exists(_vapid_path):
        vapid = Vapid01.from_file(_vapid_path)  # classmethod: returns a new instance
    else:
        vapid = Vapid01()
        vapid.generate_keys()
        vapid.save_key(_vapid_path)

    raw_public = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    _vapid = vapid
    _public_key_b64 = _b64url(raw_public)
    return _public_key_b64


def get_public_key():
    return _public_key_b64


def send_push(subscription_info, payload: dict):
    """Send one push message. Returns (ok, should_remove_subscription)."""
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=_vapid_path,
            vapid_claims={"sub": VAPID_SUBJECT},
            timeout=10,
        )
        return True, False
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        return False, status in (404, 410)
    except Exception:
        return False, False
