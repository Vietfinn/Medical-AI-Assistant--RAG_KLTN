from typing import Optional

def calculate_bmi_status(height: Optional[float], weight: Optional[float]) -> str:
    """
    Tính toán BMI với kỹ thuật lập trình phòng thủ (Defensive Programming).
    Xử lý đơn vị (cm/m) và tránh lỗi chia cho 0.
    """
    if not height or not weight or height <= 0:
        return "Không xác định (Thiếu dữ liệu)"
        
    # Chuẩn hóa đơn vị: Nếu height > 3, giả định là cm, chuyển sang m
    # Nếu height <= 3, giả định là mét (vd: 1.7m)
    h_m = height / 100.0 if height > 3 else height
    
    # Kiểm tra tính hợp lệ của chiều cao sau chuẩn hóa
    if h_m < 0.3 or h_m > 2.5: # Quá thấp hoặc quá cao (dữ liệu bất thường)
        return "Không xác định (Dữ liệu chiều cao không hợp lệ)"
        
    bmi = weight / (h_m * h_m)
    
    if bmi < 18.5: status = "Gầy (Thiếu cân)"
    elif 18.5 <= bmi < 25: status = "Bình thường"
    elif 25 <= bmi < 30: status = "Thừa cân"
    else: status = "Béo phì"
    
    return f"{bmi:.1f} - Thể trạng: {status}"
