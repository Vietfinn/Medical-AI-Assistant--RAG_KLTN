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
    - Core feature highlights (triage, health profile, corners)
    - Empathy quote and friendly signature
    - Official Veracel App URL
    - Modern warning/disclaimer footer
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
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc; padding:48px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:24px; overflow:hidden; border: 1px solid #e2e8f0; box-shadow:0 8px 30px rgba(0,0,0,0.02);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%); padding:56px 40px; text-align:center;">
              <div style="font-size: 13px; text-transform: uppercase; letter-spacing: 2px; color: #ccfbf1; font-weight: 700; margin-bottom: 12px;">Hành Trình Chăm Sóc Sức Khỏe Số</div>
              <h1 style="color:#ffffff; font-size:36px; font-weight:800; margin:0; letter-spacing:-0.5px; line-height: 1.2;">
                A.I.M Care
              </h1>
              <p style="color:#e2fbf7; font-size:16px; margin:8px 0 0 0; font-weight: 500;">Người bạn đồng hành y khoa thông minh của bạn</p>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding:48px 40px 40px 40px;">
              <h2 style="color:#0f172a; font-size:22px; font-weight:700; margin:0 0 20px 0; letter-spacing: -0.3px;">
                Xin chào {name_display},
              </h2>
              <p style="color:#475569; font-size:16px; line-height:1.8; margin:0 0 24px 0;">
                Chúng tôi rất vui mừng chào đón bạn gia nhập cộng đồng <strong>A.I.M Care</strong>. 
                Trong hành trình chăm sóc sức khỏe của bản thân và gia đình, A.I.M Care sẽ là trợ lý công nghệ luôn bên cạnh, hỗ trợ bạn tìm kiếm và giải đáp thông tin y khoa một cách khoa học, nhanh chóng và an toàn nhất.
              </p>
              
              <!-- Divider -->
              <hr style="border: 0; border-top: 1px solid #f1f5f9; margin: 32px 0;" />

              <!-- Core Features List -->
              <h3 style="color:#0f172a; font-size:15px; font-weight:700; margin:0 0 20px 0; text-transform: uppercase; letter-spacing: 1px;">Bạn có thể làm gì trên A.I.M Care?</h3>
              
              <!-- Feature 1 -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
                <tr>
                  <td width="44" valign="top" style="padding-top: 2px;">
                    <div style="background-color: #ccfbf1; border-radius: 12px; width: 36px; height: 36px; text-align: center; line-height: 36px; font-size: 18px;">🩺</div>
                  </td>
                  <td style="padding-left: 12px;">
                    <h4 style="color:#0f172a; font-size:15px; font-weight:600; margin:0 0 4px 0;">Tham vấn Triệu chứng Đa tác nhân (Multi-Agent)</h4>
                    <p style="color:#64748b; font-size:14px; margin:0; line-height:1.6;">Đặt câu hỏi về các dấu hiệu sức khỏe để nhận phân tích chuyên sâu từ hệ thống trợ lý phân luồng và tổng hợp y khoa.</p>
                  </td>
                </tr>
              </table>

              <!-- Feature 2 -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
                <tr>
                  <td width="44" valign="top" style="padding-top: 2px;">
                    <div style="background-color: #ccfbf1; border-radius: 12px; width: 36px; height: 36px; text-align: center; line-height: 36px; font-size: 18px;">📋</div>
                  </td>
                  <td style="padding-left: 12px;">
                    <h4 style="color:#0f172a; font-size:15px; font-weight:600; margin:0 0 4px 0;">Cá nhân hóa theo Hồ sơ Sức khỏe</h4>
                    <p style="color:#64748b; font-size:14px; margin:0; line-height:1.6;">Cập nhật tiền sử bệnh nền, dị ứng hoạt chất y tế để nhận cảnh báo chống chỉ định tự động, bảo vệ an toàn cho bạn.</p>
                  </td>
                </tr>
              </table>

              <!-- Feature 3 -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
                <tr>
                  <td width="44" valign="top" style="padding-top: 2px;">
                    <div style="background-color: #ccfbf1; border-radius: 12px; width: 36px; height: 36px; text-align: center; line-height: 36px; font-size: 18px;">🌱</div>
                  </td>
                  <td style="padding-left: 12px;">
                    <h4 style="color:#0f172a; font-size:15px; font-weight:600; margin:0 0 4px 0;">Tạo Góc Sức Khỏe riêng biệt</h4>
                    <p style="color:#64748b; font-size:14px; margin:0; line-height:1.6;">Tự lập các chuyên mục theo dõi riêng cho bản thân hoặc các thành viên trong gia đình để dễ dàng quản lý thông tin hội thoại.</p>
                  </td>
                </tr>
              </table>

              <!-- CTA Area -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top: 36px;">
                <tr>
                  <td align="center">
                    <a href="{app_url}" target="_blank"
                       style="display:inline-block; background:linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
                              color:#ffffff; text-decoration:none; font-size:16px; font-weight:600;
                              padding:16px 40px; border-radius:14px;
                              box-shadow:0 10px 20px rgba(15,118,110,0.25);">
                      Bắt Đầu Khám Phá Ngay
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Friendly note -->
              <p style="color:#475569; font-size:15px; line-height:1.8; margin:40px 0 0 0; text-align: center; font-style: italic; background-color: #f8fafc; padding: 20px; border-radius: 16px; border: 1px dashed #e2e8f0;">
                "Sức khỏe không chỉ là việc không có bệnh tật, mà là trạng thái hoàn hảo về cả thể chất, tinh thần và xã hội." — Hãy để A.I.M Care đồng hành cùng bạn chăm sóc sức khỏe mỗi ngày!
              </p>

              <!-- Outro -->
              <p style="color:#334155; font-size:15px; line-height:1.7; margin:32px 0 0 0;">
                Chúc bạn luôn dồi dào sức khỏe,<br/>
                <strong>Đội ngũ A.I.M Care</strong> ❤️
              </p>
            </td>
          </tr>

          <!-- Footer / Disclaimer -->
          <tr>
            <td style="background-color:#f8fafc; padding:32px 40px; border-top:1px solid #f1f5f9;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background-color:#fffbeb; border-left:4px solid #f59e0b; border-radius:8px; padding:16px 20px; margin-bottom: 24px;">
                    <p style="color:#b45309; font-size:13px; line-height:1.6; margin:0; font-weight: 500;">
                      <strong>⚠️ Khuyến cáo y khoa:</strong> A.I.M Care cung cấp thông tin y tế dựa trên trí tuệ nhân tạo chỉ mang tính chất tham khảo, không thay thế cho tư vấn, chẩn đoán hay điều trị từ bác sĩ hoặc các nhân viên y tế có chuyên môn.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding-top: 24px;">
                    <p style="color:#94a3b8; font-size:12px; line-height:1.6; margin:0;">
                      Email này được gửi tự động đến <strong>{email}</strong> vì bạn đã đăng ký tài khoản trên A.I.M Care.
                    </p>
                    <p style="color:#94a3b8; font-size:12px; line-height:1.6; margin:8px 0 0 0;">
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
