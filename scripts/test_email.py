#!/usr/bin/env python3
"""SMTP connectivity test — run this on the server to diagnose email issues.

Usage (SSH into SiteGround):
    cd ~/dochat
    python3 scripts/test_email.py

It reads the same env vars as the live app (SMTP_HOST, SMTP_PORT, SMTP_USER,
SMTP_PASS, ADMIN_EMAIL) and attempts to send a test message, printing each
step so you can see exactly where a failure occurs.
"""
import os
import smtplib
import socket
import sys
from email.message import EmailMessage
from pathlib import Path

# Load .env from project root so this works both locally and on the server
PROJECT_ROOT = Path(__file__).resolve().parent.parent
dotenv_path = PROJECT_ROOT / '.env'
if dotenv_path.exists():
    for line in dotenv_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip())
    print(f'[✓] Loaded .env from {dotenv_path}')
else:
    print(f'[!] No .env found at {dotenv_path} — using existing environment vars')

print()

# ── Read config ──────────────────────────────────────────────────────────────
smtp_host    = os.environ.get('SMTP_HOST', '')
smtp_port_s  = os.environ.get('SMTP_PORT', '465')
smtp_user    = os.environ.get('SMTP_USER', '')
smtp_pass    = os.environ.get('SMTP_PASS', '')
admin_email  = os.environ.get('ADMIN_EMAIL', '')

print('Config read from environment:')
print(f'  SMTP_HOST   = {smtp_host!r}')
print(f'  SMTP_PORT   = {smtp_port_s!r}')
print(f'  SMTP_USER   = {smtp_user!r}')
print(f'  SMTP_PASS   = {"(set, hidden)" if smtp_pass else "(NOT SET)"}')
print(f'  ADMIN_EMAIL = {admin_email!r}')
print()

missing = [k for k, v in [
    ('SMTP_HOST', smtp_host), ('SMTP_USER', smtp_user),
    ('SMTP_PASS', smtp_pass), ('ADMIN_EMAIL', admin_email),
] if not v]
if missing:
    print(f'[✗] Missing required vars: {", ".join(missing)}')
    print('    Fill these in your .env file and re-run.')
    sys.exit(1)

try:
    smtp_port = int(smtp_port_s)
except ValueError:
    print(f'[✗] SMTP_PORT is not a valid integer: {smtp_port_s!r}')
    sys.exit(1)

# ── DNS resolution ────────────────────────────────────────────────────────────
print(f'Step 1 — DNS: resolving {smtp_host!r} ...')
try:
    ip = socket.gethostbyname(smtp_host)
    print(f'  [✓] Resolved to {ip}')
except socket.gaierror as e:
    print(f'  [✗] DNS resolution failed: {e}')
    print('      Check SMTP_HOST value — it should be something like mail.your-domain.com')
    sys.exit(1)

# ── TCP connectivity ──────────────────────────────────────────────────────────
print(f'Step 2 — TCP: connecting to {smtp_host}:{smtp_port} ...')
try:
    sock = socket.create_connection((smtp_host, smtp_port), timeout=10)
    sock.close()
    print(f'  [✓] TCP connection succeeded')
except (socket.timeout, ConnectionRefusedError, OSError) as e:
    print(f'  [✗] TCP connection failed: {e}')
    if smtp_port == 587:
        print('      Port 587 blocked? Try SMTP_PORT=465 (SSL) instead.')
    elif smtp_port == 465:
        print('      Port 465 blocked? Try SMTP_PORT=587 (STARTTLS) instead.')
    print('      SiteGround sometimes blocks outbound SMTP to external servers.')
    print('      Use your cPanel email credentials (mail.your-domain.com), not Gmail/Outlook.')
    sys.exit(1)

# ── SMTP login ────────────────────────────────────────────────────────────────
print(f'Step 3 — SMTP: logging in as {smtp_user!r} ...')
try:
    if smtp_port == 465:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.starttls()
    server.login(smtp_user, smtp_pass)
    print('  [✓] Login succeeded')
except smtplib.SMTPAuthenticationError as e:
    print(f'  [✗] Authentication failed: {e}')
    print('      Wrong SMTP_USER or SMTP_PASS.')
    print('      On SiteGround: use the cPanel email account password, not your cPanel login.')
    sys.exit(1)
except smtplib.SMTPException as e:
    print(f'  [✗] SMTP error during login: {e}')
    sys.exit(1)

# ── Send test message ─────────────────────────────────────────────────────────
print(f'Step 4 — Sending test email to {admin_email!r} ...')
try:
    msg = EmailMessage()
    msg['Subject'] = '[DocChat] SMTP test — connection working'
    msg['From'] = smtp_user
    msg['To'] = admin_email
    msg.set_content(
        'This is a test email from scripts/test_email.py.\n\n'
        'If you received this, your SMTP configuration is correct and\n'
        'lead notification emails will fire when visitors submit the lead form.\n'
    )
    server.send_message(msg)
    server.quit()
    print(f'  [✓] Test email sent to {admin_email}')
    print()
    print('SMTP is working correctly. Check your inbox (and spam folder).')
except smtplib.SMTPException as e:
    print(f'  [✗] Failed to send: {e}')
    sys.exit(1)
