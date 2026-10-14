#!/usr/bin/env python3
"""يُستخدم في GitHub Actions بعد توليد مجلد android:
يضبط اسم التطبيق AbdulmajeedPharma ويضيف أذونات الإنترنت/الكاميرا/الملفات."""
import pathlib, re, sys

m = pathlib.Path("android/app/src/main/AndroidManifest.xml")
if not m.exists():
    print("AndroidManifest not found, skip"); sys.exit(0)
t = m.read_text(encoding="utf-8")
perms = """<uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.READ_MEDIA_IMAGES"/>
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32"/>
    """
if "android.permission.INTERNET" not in t:
    t = t.replace("<manifest", "<manifest", 1)
    t = re.sub(r"(<manifest[^>]*>)", r"\1\n    " + perms, t, count=1)
t = re.sub(r'android:label="[^"]*"', 'android:label="AbdulmajeedPharma"', t)
m.write_text(t, encoding="utf-8")
print("AndroidManifest patched: label=AbdulmajeedPharma + permissions")
