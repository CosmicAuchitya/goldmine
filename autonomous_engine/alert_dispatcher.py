"""
DataX-Ray Real Automated Alert Dispatcher (SMTP Email · WhatsApp Cloud / Twilio · Webhook).

Delivers concise, ranked bleeding-leak alerts directly to founders & ops leads:
1. Real SMTP Email (`smtplib` + TLS/SSL) configured via environment variables:
   `DATAXRAY_SMTP_HOST`, `DATAXRAY_SMTP_PORT`, `DATAXRAY_SMTP_USER`,
   `DATAXRAY_SMTP_PASS`, `DATAXRAY_SMTP_FROM`.
2. Real WhatsApp Cloud API (`WHATSAPP_PHONE_NUMBER_ID` + `WHATSAPP_ACCESS_TOKEN`)
   or Twilio WhatsApp (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`)
   dispatched via SSRF-guarded `safe_urlopen`.
3. Real Slack / Teams / Generic JSON Webhook via SSRF-guarded `safe_urlopen`.
4. Honest Dry-Run Mode: When SMTP/WhatsApp env credentials are not set, NEVER
   fakes delivery — returns `status="dry_run"` with exact formatted payload and
   the exact environment variables needed to activate live delivery.
"""

from __future__ import annotations

import base64
import html
import json
import os
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

try:
    from .live_connectors import safe_urlopen
except ImportError:
    from live_connectors import safe_urlopen


def format_ranked_leaks_alert(
    ranked_report: Dict[str, Any],
    run_id: str,
    lang: str = "hi",
) -> Dict[str, str]:
    """Formats ALL autonomously detected Abnormal Deviations + Healthy Summary into crisp Text & HTML alert."""
    is_hi = str(lang or "hi").lower().startswith("hi")
    leaks: List[Dict[str, Any]] = ranked_report.get("abnormal_deviations") or ranked_report.get("top_ranked_leaks") or []
    healthy_cnt: int = len(ranked_report.get("healthy_checks_suppressed") or [])
    shields: List[Dict[str, Any]] = ranked_report.get("do_not_spend_shields") or []
    opps: List[Dict[str, Any]] = (ranked_report.get("hidden_opportunities") or [])[:3]

    subject = (
        f"DataX-Ray Exception Alert ({run_id}): {len(leaks)} Abnormalities Detected ({healthy_cnt} Healthy Checks Auto-Hidden)"
        if not is_hi
        else f"DataX-Ray स्वचालित अलर्ट ({run_id}): {len(leaks)} असली खराबियाँ मिलीं ({healthy_cnt} सही जाँचें ऑटो-हाइड)"
    )

    lines: List[str] = [
        f"*{subject}*",
        "",
    ]
    if leaks:
        lines.append("🚨 *ALL CONFIRMED ABNORMALITIES (EXPECTED VS ACTUAL):*" if not is_hi else "🚨 *सभी असली खराबियाँ (क्या होना चाहिए था बनाम असल स्थिति):*")
        for lk in leaks:
            hl = lk.get("headline_hi") if is_hi else lk.get("headline_en")
            act = lk.get("fix_action_hi") if is_hi else lk.get("fix_action_en")
            exp = lk.get("expected_standard_hi") if is_hi else lk.get("expected_standard_en")
            lines.append(f"{lk.get('rank')}. [{lk.get('severity')}] {hl}")
            if exp:
                lines.append(f"   🎯 {exp}")
            lines.append(f"   → {act}")
    else:
        lines.append("✅ Zero abnormalities detected — all evaluated checks are healthy as expected.")

    if shields:
        lines.append("")
        lines.append("🛡️ *DO NOT WASTE MONEY HERE (0 SPEND):*" if not is_hi else "🛡️ *यहाँ ₹0 बचाएं (सिर्फ़ संयोग):*")
        for sh in shields:
            lines.append(f"• {sh.get('message_hi') if is_hi else sh.get('message_en')}")

    if opps:
        lines.append("")
        lines.append("💎 *TOP OPPORTUNITIES:*" if not is_hi else "💎 *प्रॉफिट बढ़ाने के मौके:*")
        for op in opps:
            lines.append(f"• {op.get('title_hi') if is_hi else op.get('title_en')}: {op.get('key_metric')}")

    plain_text = "\n".join(lines)

    # Clean inline-CSS HTML email body
    leak_html_rows = "".join(
        f"<li style='margin-bottom:10px;'><strong>#{lk.get('rank')} [{html.escape(str(lk.get('severity')))}]</strong> "
        f"{html.escape(str(lk.get('headline_hi') if is_hi else lk.get('headline_en')))}<br/>"
        f"<span style='color:#475569;font-size:13px;'>Action: {html.escape(str(lk.get('fix_action_hi') if is_hi else lk.get('fix_action_en')))}</span></li>"
        for lk in leaks
    )
    shield_html_rows = "".join(
        f"<li>{html.escape(str(sh.get('message_hi') if is_hi else sh.get('message_en')))}</li>"
        for sh in shields
    )
    html_body = (
        f"<html><body style='font-family:Arial,sans-serif;color:#0f172a;max-width:640px;margin:auto;padding:16px;'>"
        f"<h2 style='color:#0f172a;border-bottom:2px solid #0284c7;padding-bottom:8px;'>{html.escape(subject)}</h2>"
        f"<h3 style='color:#dc2626;'>Top Ranked Leaks</h3><ol>{leak_html_rows or '<li>No elevated leaks detected.</li>'}</ol>"
        + (f"<h3 style='color:#059669;'>Don't Spend Here (Circuit-Breaker)</h3><ul>{shield_html_rows}</ul>" if shields else "")
        + "<p style='font-size:12px;color:#64748b;margin-top:20px;'>Generated deterministically by DataX-Ray (Zero-Hallucination DuckDB Verified).</p>"
        + "</body></html>"
    )

    return {"subject": subject, "plain_text": plain_text, "html_body": html_body}


def dispatch_email_smtp(
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str,
) -> Dict[str, Any]:
    """Dispatches real SMTP email when DATAXRAY_SMTP_* env vars exist, else returns honest dry-run."""
    host = os.environ.get("DATAXRAY_SMTP_HOST", "").strip()
    port = int(os.environ.get("DATAXRAY_SMTP_PORT", "587") or 587)
    user = os.environ.get("DATAXRAY_SMTP_USER", "").strip()
    password = os.environ.get("DATAXRAY_SMTP_PASS", "").strip()
    sender = os.environ.get("DATAXRAY_SMTP_FROM", user or "alerts@dataxray.local").strip()

    if not host or not to_email:
        return {
            "channel": "email",
            "status": "dry_run",
            "delivered": False,
            "reason": "DATAXRAY_SMTP_HOST not configured; returning formatted preview without faking delivery.",
            "required_env": ["DATAXRAY_SMTP_HOST", "DATAXRAY_SMTP_PORT", "DATAXRAY_SMTP_USER", "DATAXRAY_SMTP_PASS", "DATAXRAY_SMTP_FROM"],
            "preview_subject": subject,
            "preview_text": plain_body,
        }

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=12) as srv:
            if user and password:
                srv.login(user, password)
            srv.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=12) as srv:
            srv.ehlo()
            try:
                srv.starttls()
                srv.ehlo()
            except smtplib.SMTPException:
                pass
            if user and password:
                srv.login(user, password)
            srv.send_message(msg)

    return {"channel": "email", "status": "sent", "delivered": True, "recipient": to_email, "subject": subject}


def dispatch_whatsapp_alert(to_phone: str, message_text: str) -> Dict[str, Any]:
    """Dispatches via Meta WhatsApp Cloud API or Twilio WhatsApp when env vars are set; else dry-run."""
    wa_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    wa_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    tw_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    tw_from = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()

    clean_phone = "".join(ch for ch in str(to_phone or "") if ch.isdigit() or ch == "+")
    if wa_phone_id and wa_token and clean_phone:
        url = f"https://graph.facebook.com/v19.0/{urllib.parse.quote(wa_phone_id)}/messages"
        payload = json.dumps({
            "messaging_product": "whatsapp",
            "to": clean_phone.lstrip("+"),
            "type": "text",
            "text": {"body": message_text[:4000]},
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {wa_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with safe_urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
        return {"channel": "whatsapp_cloud", "status": "sent" if ok else "error", "delivered": ok, "recipient": clean_phone}

    if tw_sid and tw_token and tw_from and clean_phone:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{urllib.parse.quote(tw_sid)}/Messages.json"
        form = urllib.parse.urlencode({
            "From": tw_from if tw_from.startswith("whatsapp:") else f"whatsapp:{tw_from}",
            "To": f"whatsapp:{clean_phone}" if not clean_phone.startswith("whatsapp:") else clean_phone,
            "Body": message_text[:1550],
        }).encode("utf-8")
        auth = base64.b64encode(f"{tw_sid}:{tw_token}".encode("utf-8")).decode("ascii")
        req = urllib.request.Request(
            url,
            data=form,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with safe_urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
        return {"channel": "twilio_whatsapp", "status": "sent" if ok else "error", "delivered": ok, "recipient": clean_phone}

    return {
        "channel": "whatsapp",
        "status": "dry_run",
        "delivered": False,
        "reason": "WhatsApp Cloud API / Twilio credentials not configured; returning formatted WhatsApp message preview.",
        "required_env": ["WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_ACCESS_TOKEN"],
        "preview_text": message_text,
    }


def dispatch_webhook_alert(webhook_url: str, message_text: str, run_id: str) -> Dict[str, Any]:
    """Dispatches Slack / Teams / Generic JSON alert through SSRF-guarded safe_urlopen."""
    if not webhook_url:
        return {"channel": "webhook", "status": "dry_run", "delivered": False, "reason": "No webhook_url supplied."}
    payload = json.dumps({"text": message_text, "run_id": run_id, "source": "DataX-Ray"}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "DataXRay-AlertDispatcher/1.0"},
        method="POST",
    )
    with safe_urlopen(req, timeout=10) as resp:
        ok = 200 <= resp.status < 300
    return {"channel": "webhook", "status": "sent" if ok else "error", "delivered": ok}


__all__ = [
    "format_ranked_leaks_alert",
    "dispatch_email_smtp",
    "dispatch_whatsapp_alert",
    "dispatch_webhook_alert",
]
