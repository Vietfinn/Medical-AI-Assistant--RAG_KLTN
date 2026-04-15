"""
Email Service for Medical AI Assistant (via Google Apps Script).
Sends styled HTML welcome emails to new users on first login
by making an HTTPS POST request to a Google Apps Script Web App URL.
This completely bypasses standard SMTP port blocks on Cloud deployments.
"""

import logging
import httpx
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_mail_ready = False


def configure_gmail():
    """Validate Google Apps Script Web App URL on startup."""
    global _mail_ready
    if settings.GOOGLE_APPS_SCRIPT_URL:
        _mail_ready = True
        logger.info("✅ Mail service (Google Apps Script) configured")
    else:
        logger.warning("⚠️ GOOGLE_APPS_SCRIPT_URL not set — email service disabled")


def _build_welcome_html(first_name: Optional[str] = None, app_url: str = "http://localhost:3000") -> str:
    """
    Build the HTML welcome email template in Medical Teal tone.

    Includes:
    - Personalized greeting with first_name
    - CTA button to update Health Profile
    - Medical Disclaimer footer
    """
    name_display = first_name if first_name else "bạn"

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
</head>
<body style="margin:0; padding:0; background-color:#f0f4f9; font-family:'Segoe UI', Roboto, Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f4f9; padding:40px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #0d9488 0%, #14b8a6 50%, #2dd4bf 100%); padding:40px 32px; text-align:center;">
              <div style="font-size:36px; margin-bottom:12px;">&#129658;</div>
              <h1 style="color:#ffffff; font-size:24px; font-weight:700; margin:0 0 8px 0;">
                Chào mừng đến với Medical AI
              </h1>
              <p style="color:rgba(255,255,255,0.9); font-size:15px; margin:0;">
                Trợ lý sức khỏe cá nhân thông minh của bạn
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <h2 style="color:#1f2937; font-size:20px; font-weight:600; margin:0 0 16px 0;">
                Xin chào {name_display}! &#128075;
              </h2>
              <p style="color:#4b5563; font-size:15px; line-height:1.7; margin:0 0 16px 0;">
                Cảm ơn bạn đã đăng ký tài khoản tại <strong>Medical AI Assistant</strong>.
                Hệ thống của chúng tôi sử dụng trí tuệ nhân tạo đa tác nhân (Multi-Agent AI) để cung cấp
                thông tin y tế chính xác và an toàn.
              </p>
              <p style="color:#4b5563; font-size:15px; line-height:1.7; margin:0 0 24px 0;">
                Để AI có thể đưa ra lời khuyên <strong>an toàn và phù hợp nhất</strong> với tình trạng
                sức khỏe của bạn, hãy cập nhật Hồ sơ Sức khỏe ngay bây giờ:
              </p>

              <!-- CTA Button -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="padding:8px 0 32px 0;">
                    <a href="{app_url}"
                       style="display:inline-block; background:linear-gradient(135deg, #0d9488, #14b8a6);
                              color:#ffffff; text-decoration:none; font-size:16px; font-weight:600;
                              padding:14px 36px; border-radius:12px;
                              box-shadow:0 4px 14px rgba(13,148,136,0.35);">
                      &#128203; Cập nhật Hồ sơ Sức khỏe ngay
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Info Box -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:#f0fdfa; border-left:4px solid #14b8a6; border-radius:8px; padding:16px 20px;">
                    <p style="color:#0f766e; font-size:14px; line-height:1.6; margin:0;">
                      &#128161; <strong>Mẹo:</strong> Điền đầy đủ thông tin về bệnh nền, dị ứng và thuốc đang dùng
                      sẽ giúp AI kiểm tra chéo và cảnh báo khi có xung đột y khoa.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer / Disclaimer -->
          <tr>
            <td style="background-color:#f9fafb; padding:24px 32px; border-top:1px solid #e5e7eb;">
              <p style="color:#9ca3af; font-size:12px; line-height:1.6; margin:0; text-align:center;">
                <strong>Miễn trừ trách nhiệm y tế:</strong> Medical AI Assistant là công cụ hỗ trợ
                thông tin, không phải là bác sĩ. Vui lòng luôn tham khảo ý kiến chuyên gia y tế
                trước khi đưa ra quyết định sức khỏe.
              </p>
              <p style="color:#d1d5db; font-size:11px; margin:12px 0 0 0; text-align:center;">
                © 2026 Medical AI Assistant — Đồ án tốt nghiệp KLTN
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_welcome_email(email: str, first_name: Optional[str] = None):
    """
    Send a welcome HTML email to a newly registered user via Google Apps Script POST.
    Designed to be called inside asyncio.to_thread (non-blocking).

    Args:
        email: Recipient email address
        first_name: User's first name for personalized greeting
    """
    if not _mail_ready:
        logger.warning(f"Skipping welcome email to {email} — GOOGLE_APPS_SCRIPT_URL not configured")
        return

    try:
        app_url = settings.FRONTEND_URL if settings.FRONTEND_URL else "http://localhost:3000"
        html_content = _build_welcome_html(first_name=first_name, app_url=app_url)

        import json
        import base64
        
        # Bọc Base64 toàn bộ file HTML để đảm bảo 1 tỷ phần trăm không bị lỗi Font (truyền ASCII thuần)
        html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('ascii')

        # Chuẩn bị Data Payload để bắn qua Apps Script
        payload = {
            "to": email,
            "subject": "[Medical AI] Chào mừng đến với Trợ lý Sức khỏe!",
            "htmlBodyB64": html_b64
        }

        # Nếu có thiết lập tên người gửi, truyền sang Apps Script (để Apps Script chỉnh name/from)
        if hasattr(settings, "GMAIL_SENDER") and settings.GMAIL_SENDER:
             payload["from"] = settings.GMAIL_SENDER
             payload["name"] = "Medical AI"

        # Bắn Request HTTPS POST qua Google (Follow redirect để đảm bảo request thành công)
        response = httpx.post(
            settings.GOOGLE_APPS_SCRIPT_URL,
            json=payload,
            timeout=30.0,
            follow_redirects=True
        )

        response.raise_for_status()

        # Web App script nên trả về json chứa status
        try:
            resp_data = response.json()
            if resp_data.get("status") == "error":
                logger.error(f"❌ Google Apps Script Error: {resp_data.get('message')}")
                return
        except Exception:
            # Nếu Google trả về trang HTML bẫy đăng nhập/redirect thay vì JSON
            logger.warning(f"⚠️ Google Apps Script didn't return JSON: {response.text[:200]}")

        logger.info(f"✅ Welcome email sent to {email} via Google Apps Script")

    except Exception as e:
        logger.error(f"❌ Failed to send welcome email to {email} (Apps Script): {e}")
