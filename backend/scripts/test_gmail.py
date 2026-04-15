"""
Test Script for Gmail SMTP Welcome Email Integration
Run this directly to verify if your Gmail SMTP config is correct.
"""

import sys
import os
from pathlib import Path

# Thêm thư mục mẹ vào sys.path để có thể import từ backend
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from config import settings
from services.email_service import configure_gmail, send_welcome_email

def main():
    print("=" * 50)
    print("📧 Kiểm tra hệ thống gửi Email (Gmail SMTP)")
    print("=" * 50)
    print(f"GMAIL_SENDER: {settings.GMAIL_SENDER}")
    
    if not settings.GMAIL_SENDER or not settings.GMAIL_APP_PASSWORD:
        print("❌ LỖI: Chưa cấu hình GMAIL_SENDER hoặc GMAIL_APP_PASSWORD trong .env!")
        print("Vui lòng cập nhật .env bằng email và mật khẩu ứng dụng gồm 16 ký tự của bạn.")
        return

    # Khởi tạo dịch vụ
    configure_gmail()

    test_email = input("\nNhập địa chỉ email muốn nhận thư test (Bỏ trống để gửi chính người gửi): ").strip()
    if not test_email:
        test_email = settings.GMAIL_SENDER

    test_name = input("Nhập tên hiển thị (Bỏ trống để dùng tên 'Tester'): ").strip()
    if not test_name:
        test_name = "Tester"

    print(f"\n⏳ Đang gửi thư thử nghiệm đến: {test_email}...")
    
    try:
        # Gọi thẳng hàm gửi email để test
        send_welcome_email(email=test_email, first_name=test_name)
        print("\n✅ Email đã được gửi! Vui lòng kiểm tra hộp thư đến (hoặc Spam).")
    except Exception as e:
        print(f"\n❌ Gọi hàm gửi email thất bại: {e}")

if __name__ == "__main__":
    main()
