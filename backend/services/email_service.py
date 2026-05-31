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


def _build_welcome_html(email: str, first_name: Optional[str] = None, app_url: str = "https://aimcare.vercel.app/") -> str:
    """
    Build the HTML welcome email template in a professional, friendly, medical-teal theme.

    Includes:
    - Personalized greeting with first_name
    - Core feature highlights in a clean horizontal 3-column grid
    - Numeric CSS badges instead of unicode emojis to avoid encoding issues
    - Official Vercel App URL
    - Clean signature and disclaimer footer
    """
    name_display = first_name if first_name else "bạn"

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Chào mừng bạn đến với A.I.M Care</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
  </style>
</head>
<body style="margin:0; padding:0; background-color:#f8fafc; font-family:'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc; padding:32px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:20px; overflow:hidden; border: 1px solid #e2e8f0; box-shadow:0 4px 20px rgba(0,0,0,0.02);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%); padding:40px 32px; text-align:center;">
              <h1 style="color:#ffffff; font-size:30px; font-weight:800; margin:0; letter-spacing:-0.5px; line-height: 1.2;">
                A.I.M Care
              </h1>
              <p style="color:#ccfbf1; font-size:14px; margin:6px 0 0 0; font-weight: 500; text-transform: uppercase; letter-spacing: 1px;">Trợ Lý Y Tế Thông Minh</p>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding:40px 32px 32px 32px;">
              <h2 style="color:#0f172a; font-size:20px; font-weight:700; margin:0 0 12px 0; letter-spacing: -0.3px;">
                Xin chào {name_display},
              </h2>
              <p style="color:#475569; font-size:14px; line-height:1.7; margin:0 0 24px 0;">
                Chúng tôi rất vui mừng chào đón bạn gia nhập cộng đồng <strong>A.I.M Care</strong>. 
                A.I.M Care đồng hành cùng bạn để giải đáp thông tin sức khỏe khoa học, nhanh chóng và an toàn nhất qua kiến trúc Đa tác nhân (Multi-Agent).
              </p>
              
              <!-- 3-Column Features Grid -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top: 24px; margin-bottom: 24px;">
                <tr>
                  <!-- Column 1 -->
                  <td width="168" valign="top" style="background-color: #fafbfb; border: 1px solid #f1f5f9; border-radius: 12px; padding: 16px 12px; text-align: center;">
                    <div style="background-color: #ccfbf1; color: #0f766e; border-radius: 50%; width: 32px; height: 32px; text-align: center; line-height: 32px; font-size: 14px; font-weight: 700; margin: 0 auto 10px auto;">1</div>
                    <h4 style="color:#0f172a; font-size:13px; font-weight:700; margin:0 0 6px 0; line-height: 1.3;">Tham vấn triệu chứng</h4>
                    <p style="color:#64748b; font-size:11px; margin:0; line-height:1.4;">Hỏi đáp dấu hiệu sức khỏe qua Multi-Agent.</p>
                  </td>
                  <td width="16" style="font-size: 1px; line-height: 1px;">&nbsp;</td>
                  <!-- Column 2 -->
                  <td width="168" valign="top" style="background-color: #fafbfb; border: 1px solid #f1f5f9; border-radius: 12px; padding: 16px 12px; text-align: center;">
                    <div style="background-color: #ccfbf1; color: #0f766e; border-radius: 50%; width: 32px; height: 32px; text-align: center; line-height: 32px; font-size: 14px; font-weight: 700; margin: 0 auto 10px auto;">2</div>
                    <h4 style="color:#0f172a; font-size:13px; font-weight:700; margin:0 0 6px 0; line-height: 1.3;">Hồ sơ sức khỏe</h4>
                    <p style="color:#64748b; font-size:11px; margin:0; line-height:1.4;">Cảnh báo dị ứng và tương tác thuốc tự động.</p>
                  </td>
                  <td width="16" style="font-size: 1px; line-height: 1px;">&nbsp;</td>
                  <!-- Column 3 -->
                  <td width="168" valign="top" style="background-color: #fafbfb; border: 1px solid #f1f5f9; border-radius: 12px; padding: 16px 12px; text-align: center;">
                    <div style="background-color: #ccfbf1; color: #0f766e; border-radius: 50%; width: 32px; height: 32px; text-align: center; line-height: 32px; font-size: 14px; font-weight: 700; margin: 0 auto 10px auto;">3</div>
                    <h4 style="color:#0f172a; font-size:13px; font-weight:700; margin:0 0 6px 0; line-height: 1.3;">Góc sức khỏe</h4>
                    <p style="color:#64748b; font-size:11px; margin:0; line-height:1.4;">Tạo các chuyên mục theo dõi riêng cho gia đình.</p>
                  </td>
                </tr>
              </table>

              <!-- CTA Area -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top: 24px; margin-bottom: 24px;">
                <tr>
                  <td align="center">
                    <a href="{app_url}" target="_blank"
                       style="display:inline-block; background:linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
                              color:#ffffff; text-decoration:none; font-size:15px; font-weight:600;
                              padding:14px 36px; border-radius:10px;
                              box-shadow:0 4px 12px rgba(15,118,110,0.2);">
                      Bắt Đầu Khám Phá Ngay
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Outro -->
              <p style="color:#334155; font-size:14px; line-height:1.6; margin:24px 0 0 0;">
                Chúc bạn luôn dồi dào sức khỏe,<br/>
                <strong>Đội ngũ A.I.M Care</strong>
              </p>
            </td>
          </tr>

          <!-- Footer / Disclaimer -->
          <tr>
            <td style="background-color:#f8fafc; padding:24px 32px; border-top:1px solid #f1f5f9;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:#fffbeb; border-left:4px solid #f59e0b; border-radius:8px; padding:12px 16px; margin-bottom: 20px;">
                    <p style="color:#b45309; font-size:12px; line-height:1.5; margin:0; font-weight: 500;">
                      <strong>Khuyến cáo y khoa:</strong> A.I.M Care cung cấp thông tin y tế dựa trên trí tuệ nhân tạo chỉ mang tính chất tham khảo, không thay thế cho tư vấn, chẩn đoán hay điều trị từ bác sĩ hoặc nhân viên y tế có chuyên môn.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding-top: 16px;">
                    <p style="color:#94a3b8; font-size:11px; line-height:1.5; margin:0;">
                      Email này được gửi tự động đến <strong>{email}</strong> vì bạn đã đăng ký tài khoản trên A.I.M Care.
                    </p>
                    <p style="color:#94a3b8; font-size:11px; line-height:1.5; margin:6px 0 0 0;">
                      © 2026 A.I.M Care. Mọi quyền được bảo lưu.<br/>
                      Hỗ trợ: <a href="mailto:aimcare.chat@gmail.com" style="color:#0f766e; text-decoration:none; font-weight: 600;">aimcare.chat@gmail.com</a>
                    </p>
                  </td>
                </tr>
              </table>
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
        app_url = settings.FRONTEND_URL if settings.FRONTEND_URL else "https://aimcare.vercel.app/"
        html_content = _build_welcome_html(email=email, first_name=first_name, app_url=app_url)

        import json
        import base64
        
        # Bọc Base64 toàn bộ file HTML để đảm bảo 1 tỷ phần trăm không bị lỗi Font (truyền ASCII thuần)
        html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('ascii')

        # Chuẩn bị Data Payload để bắn qua Apps Script
        payload = {
            "to": email,
            "subject": "Chào mừng đến với A.I.M Care. Cùng bắt đầu nhé!",
            "htmlBodyB64": html_b64
        }

        # Nếu có thiết lập tên người gửi, truyền sang Apps Script (để Apps Script chỉnh name/from)
        if hasattr(settings, "GMAIL_SENDER") and settings.GMAIL_SENDER:
             payload["from"] = settings.GMAIL_SENDER
             payload["name"] = "A.I.M Care"

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
