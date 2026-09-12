"""Quick SMTP/Mailpit connectivity check for local OTP delivery."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from utils.ses_mail import send_email  # noqa: E402

result = send_email(
    to_addresses=["otp.demo@contentos.local"],
    subject="ContentOS Mailpit setup check",
    html_body="<p>If you see this in <a href='http://127.0.0.1:8025'>Mailpit</a>, OTP email is ready.</p>",
    text_body="If you see this in Mailpit (http://127.0.0.1:8025), OTP email is ready.",
)
print(result)
if not result.get("sent"):
    sys.exit(1)
print("Open http://127.0.0.1:8025 to view the message.")
