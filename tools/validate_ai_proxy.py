#!/usr/bin/env python3
"""Reject provider keys in the public APH_AI_PROXY build variable."""
import os
import re
import sys
from urllib.parse import urlsplit

value = os.getenv('APH_AI_PROXY', '').strip()
if not value:
    print('APH_AI_PROXY is empty: the APK will use local/offline AI until configured.')
    raise SystemExit(0)
try:
    url = urlsplit(value)
    valid = (url.scheme == 'https' and bool(url.hostname) and not url.username
             and not url.password and not url.query and not url.fragment)
except ValueError:
    valid = False
looks_like_key = bool(re.search(r'(AIza[0-9A-Za-z_-]{12,}|sk-[A-Za-z0-9_-]{12,})', value))
if not valid or looks_like_key:
    print('APH_AI_PROXY must be a public HTTPS Worker URL only; no API keys, credentials, query, or fragment.')
    raise SystemExit(1)
print('APH_AI_PROXY is a valid public HTTPS URL; no provider key is passed to Flutter.')
