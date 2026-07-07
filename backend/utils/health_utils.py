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


def is_profile_completed(profile: Optional[dict]) -> bool:
    """
    Kiểm tra xem hồ sơ sức khỏe có chứa ít nhất 1 thông tin thực tế hay không.
    Trả về False nếu profile là None hoặc tất cả các trường đều rỗng/None.
    """
    if not profile:
        return False
    has_list_data = any([
        bool(profile.get("chronic_diseases")),
        bool(profile.get("allergies")),
        bool(profile.get("current_medications")),
    ])
    has_personal_data = any([
        profile.get("age") is not None and profile.get("age") != "",
        bool(profile.get("gender") and str(profile.get("gender")).strip()),
        profile.get("height") is not None and profile.get("height") != "",
        profile.get("weight") is not None and profile.get("weight") != "",
    ])
    return has_list_data or has_personal_data

