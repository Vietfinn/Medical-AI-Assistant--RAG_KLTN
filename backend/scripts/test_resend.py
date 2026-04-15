import os
from dotenv import load_dotenv
import resend

# Tải biến môi trường từ file .env
load_dotenv()

def test_email():
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("❌ LỖI: Không tìm thấy RESEND_API_KEY trong file .env")
        return

    resend.api_key = api_key
    sender = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    
    print(f"🔑 Dùng API Key: {api_key[:5]}...{api_key[-5:]}")
    print(f"📧 Gửi từ: {sender}")
    
    # Nhập địa chỉ nhận
    recipient = input("\nNhập địa chỉ Email CỦA BẠN muốn gửi test tới: ").strip()
    
    if not recipient:
        print("Hủy lệnh.")
        return

    try:
        print("\n⏳ Đang gửi email qua máy chủ Resend...")
        response = resend.Emails.send({
            "from": sender,
            "to": [recipient],
            "subject": "🩺 Test KLTN - Resend Email System",
            "html": """
                <h2>Gửi email thành công!</h2>
                <p>Hệ thống Resend API của Medical AI Assistant đã hoạt động chu đáo.</p>
            """
        })
        print(f"✅ THÀNH CÔNG! Đã ném qua Resend. ID Email: {response.get('id', 'N/A')}")
        print("👉 Vui lòng check ngay Email hoặc mở Dashboard Resend lên xem có lỗi chặn gì không nhé.")
        
    except Exception as e:
        print(f"\n❌ LỖI GỬI EMAIL: {e}")
        print("Gợi ý Fix: Bạn đang dùng email không hợp lệ, hoặc do tài khoản Resend chưa Verify tên miền nên nó chỉ cho phép gửi CHÍNH XÁC cấu hình đã thiết lập!")

if __name__ == "__main__":
    test_email()
