#!/usr/bin/env python3
"""Print fresh values for the secrets in .env.

    python scripts/generate_secrets.py

Use this after a leak. Rotating SECRET_KEY invalidates every existing admin
session; rotating KIOSK_TOKEN requires re-enrolling each kiosk tablet via
/kiosk/enroll.
"""

import secrets

print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
print(f"KIOSK_TOKEN={secrets.token_urlsafe(32)}")
