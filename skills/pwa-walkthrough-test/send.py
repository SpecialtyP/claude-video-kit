#!/usr/bin/env python3
"""send.py — email a video attachment via a Supabase edge function (Resend).

Usage:
    python3 send.py <to> <subject> <html_body_file_or_string> <attachment_path>

Env:
    SUPABASE_FUNCTIONS_URL   required — https://<project-ref>.supabase.co/functions/v1/send-report-email
    SUPABASE_ANON_KEY        required (the project's anon/publishable key)
    SEND_FROM                Resend "from" handled by the edge function
"""
import base64, json, os, sys, urllib.request, urllib.error

if len(sys.argv) < 5:
    print(__doc__, file=sys.stderr)
    sys.exit(2)

to, subject, body, attachment = sys.argv[1:5]

if os.path.isfile(body):
    with open(body) as f:
        html = f.read()
else:
    html = body

with open(attachment, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

size_mb = len(b64) / 1024 / 1024
print(f"attachment {attachment}: ~{size_mb:.1f} MB base64", file=sys.stderr)
if size_mb > 38:
    print(f"WARNING: {size_mb:.1f} MB exceeds Resend's 40 MB cap. Upload to Drive instead.", file=sys.stderr)

url = os.environ.get("SUPABASE_FUNCTIONS_URL", "")
if not url:
    print("error: set SUPABASE_FUNCTIONS_URL to your project's send-report-email endpoint",
          file=sys.stderr); sys.exit(2)
key = os.environ.get("SUPABASE_ANON_KEY", "")
if not key:
    print("error: set SUPABASE_ANON_KEY", file=sys.stderr); sys.exit(2)

payload = {
    "to": to,
    "subject": subject,
    "html": html,
    "pdfBase64": b64,
    "filename": os.path.basename(attachment),
}
req = urllib.request.Request(
    url, data=json.dumps(payload).encode(), method="POST",
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}", "apikey": key},
)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        print("HTTP", resp.status)
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read().decode(), file=sys.stderr)
    sys.exit(1)
