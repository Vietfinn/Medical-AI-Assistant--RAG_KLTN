"""
Resend Email Service for Medical AI Assistant.
Sends styled HTML welcome emails to new users on first login.
"""

import logging
from typing import Optional

import resend
from config import settings

logger = logging.getLogger(__name__)


def configure_resend():
    """Initialize the Resend SDK with the API key."""
    if settings.RESEND_API_KEY:
        resend.api_key = settings.RESEND_API_KEY
        logger.info("✅ Resend email service configured")
    else:
        logger.warning("⚠️ RESEND_API_KEY not set — email service disabled")


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
              <div style="font-size:36px; margin-bottom:12px;">🩺</div>
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
                Xin chào {name_display}! 👋
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
                      📋 Cập nhật Hồ sơ Sức khỏe ngay
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Info Box -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:#f0fdfa; border-left:4px solid #14b8a6; border-radius:8px; padding:16px 20px;">
                    <p style="color:#0f766e; font-size:14px; line-height:1.6; margin:0;">
                      💡 <strong>Mẹo:</strong> Điền đầy đủ thông tin về bệnh nền, dị ứng và thuốc đang dùng
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
    Send a welcome HTML email to a newly registered user.
    Designed to be called inside FastAPI BackgroundTasks (non-blocking).

    Args:
        email: Recipient email address
        first_name: User's first name for personalized greeting
    """
    if not settings.RESEND_API_KEY:
        logger.warning(f"Skipping welcome email to {email} — RESEND_API_KEY not configured")
        return

    try:
        html_content = _build_welcome_html(first_name=first_name)

        params = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [email],
            "subject": "🩺 Chào mừng đến với Medical AI Assistant!",
            "html": html_content,
        }

        result = resend.Emails.send(params)
        logger.info(f"✅ Welcome email sent to {email} (ID: {result.get('id', 'N/A')})")

    except Exception as e:
        logger.error(f"❌ Failed to send welcome email to {email}: {e}")
