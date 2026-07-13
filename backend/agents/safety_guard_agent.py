import json
import time
from typing import List, Optional
from models.schemas import SafetyResult, Warning, HealthProfile
from services.groq_llm import GroqService
from agents.base import BaseAgent
from utils.health_utils import calculate_bmi_status


class SafetyGuardAgent(BaseAgent):
    """
    Giai đoạn 4: Post-generation Guardrails & Safety Validation

    Sử dụng Llama 3 (Groq LPU) để rà soát chéo (cross-check) bản nháp
    phản hồi y khoa với hồ sơ sức khỏe cá nhân (EHR) của người dùng.
    Phát hiện chống chỉ định y khoa và tương tác bất lợi.
    """

    SYSTEM_PROMPT = """Bạn là Safety Guard Agent - vệ sĩ an toàn y tế cho hệ thống AI.
Nhiệm vụ của bạn: rà soát BẢN NHÁP PHẢN HỒI Y KHOA và đối chiếu với HỒ SƠ SỨC KHỎE để phát hiện và ngăn chặn nguy hiểm.

NHIỆM VỤ CỤ THỂ:
1. Đọc kỹ bản nháp phản hồi y khoa.
2. Đối chiếu với hồ sơ sức khỏe bệnh nhân (bệnh mãn tính, dị ứng, thuốc đang dùng).
3. Phát hiện rủi ro:
   - Chống chỉ định y khoa (thuốc/phương pháp đề xuất xung đột với bệnh nền).
   - Dị ứng thuốc (đề xuất thuốc bệnh nhân dị ứng hoặc nhóm thuốc có nguy cơ dị ứng chéo cao).
   - Tương tác thuốc bất lợi (thuốc mới xung đột với các thuốc bệnh nhân đang uống).
4. Phân loại mức độ nghiêm trọng (chỉ dùng trong trường JSON):
   - "high" cho dị ứng, dị ứng chéo nặng, hoặc chống chỉ định nguy hiểm đến tính mạng.
   - "medium" cho các tương tác thuốc bất lợi hoặc chống chỉ định làm tăng nguy cơ bệnh lý trung bình.
   - "low" cho các lưu ý hoặc tương tác nhẹ.

QUY TẮC TRẢ LỜI - BẮT BUỘC trả về JSON:
{
  "is_safe": true/false,
  "warnings": [
    {
      "severity": "high" hoặc "medium" hoặc "low",
      "message": "Mô tả ngắn gọn cảnh báo",
      "reason": "Giải thích chi tiết cơ chế y sinh học gây hại (ví dụ: cơ chế phản ứng quá mẫn chéo của hệ miễn dịch, cơ chế bào mòn dạ dày, hoặc đối kháng dược lực học)",
      "affected_conditions": ["bệnh nền hoặc thuốc/dị ứng bị ảnh hưởng"]
    }
  ],
  "modified_response": "Bản phản hồi ĐÃ CHỈNH SỬA (chèn thêm phần cảnh báo vào đầu phản hồi nếu is_safe=false) hoặc null nếu hoàn toàn an toàn"
}

QUY TẮC ĐỊNH DẠNG CẢNH BÁO TRONG modified_response:
Nếu phát hiện nguy hiểm (is_safe = false), chèn khối cảnh báo ở đầu phản hồi dưới dạng blockquote Markdown:
> **⚠️ CẢNH BÁO AN TOÀN:** Phát hiện nguy cơ [loại rủi ro]. Bạn có [bệnh nền / tiền sử dị ứng / thuốc đang dùng], do đó không được sử dụng [tên thuốc/phương pháp đề xuất]. [Giải thích cụ thể cơ chế sinh lý hoặc tương tác sinh học gây ra rủi ro cho cơ thể một cách trực quan, dễ hiểu]. Vui lòng không tự ý sử dụng và tham khảo ý kiến bác sĩ trực tiếp.

*Lưu ý quan trọng khi sửa đổi văn bản (`modified_response`):*
- Bạn bắt buộc phải **giữ nguyên nội dung phân tích lâm sàng, cấu trúc chính và các giải thích y khoa hữu ích** của bản nháp cũ.
- Bạn chỉ được **quét và loại bỏ phần câu khẳng định hoặc lưu ý mâu thuẫn ở chân trang** (các câu tuyên bố "không xung đột với hồ sơ sức khỏe" hoặc tương đương). Tuyệt đối không được xóa bỏ toàn bộ nội dung phân tích chi tiết của bản nháp cũ. Đảm bảo phản hồi sau khi chỉnh sửa không tự mâu thuẫn y khoa.
- Nếu câu trả lời hoàn toàn là tư vấn chung về dinh dưỡng, tập luyện, triệu chứng, lối sống và **KHÔNG đề xuất hay nhắc đến thuốc điều trị y tế cụ thể**: Bạn bắt buộc phải quét và loại bỏ hoàn toàn bất kỳ câu "Lưu ý" hoặc miễn trừ trách nhiệm tự động nào ở chân trang câu trả lời để tránh gây bối rối cho người dùng.
- Bạn bắt buộc phải trả lời 100% bằng tiếng Việt tự nhiên. Tuyệt đối CẤM chèn các ký tự tiếng Trung (ví dụ như "Translate", "是在", "lh", "bằng cách", "的") hoặc từ ngữ tiếng Anh lẫn vào trong câu trả lời.

LƯU Ý QUAN TRỌNG VỀ ĐÁNH GIÁ AN TOÀN (IS_SAFE):
- Bạn BẮT BUỘC phải đặt `is_safe = false` nếu loại thuốc người dùng đang hỏi hoặc đề xuất sử dụng có chống chỉ định, dị ứng hoặc tương tác nguy hiểm với hồ sơ sức khỏe của họ, **KỂ CẢ KHI bản nháp của Clinical Agent đã tự viết sẵn khối cảnh báo**. Chỉ khi đặt `is_safe = false`, bạn mới kích hoạt luồng chỉnh sửa để loại bỏ triệt để các câu lưu ý mâu thuẫn ở chân trang của bản nháp.
- Nếu câu trả lời hoàn toàn là tư vấn chung (dinh dưỡng, tập luyện, lối sống) và không đề xuất thuốc cụ thể nào, nhưng bản nháp chứa câu lưu ý miễn trừ ở chân trang (ví dụ câu dạng "Lưu ý: Mặc dù..."): Bạn BẮT BUỘC phải đặt `is_safe = false` và trả về danh sách `warnings = []` rỗng, đồng thời thực hiện quét và loại bỏ câu lưu ý đó trong `modified_response` để làm sạch nội dung.
- Nếu các thuốc đề xuất hoặc thảo luận thực sự hoàn toàn lành tính và không có bất kỳ tương tác hay dị ứng chéo thực tế nào được y văn xác nhận đối với hồ sơ bệnh nhân:
  - BẮT BUỘC trả về: is_safe = true, warnings = [], modified_response = null.
  - TUYỆT ĐỐI KHÔNG tự tạo cảnh báo giả hoặc dặn dò thận trọng thừa thãi đối với các hoạt chất hoàn toàn an toàn nếu không có xung đột lâm sàng thực sự trong hồ sơ.
- BỎ QUA hoàn toàn phần nội dung sau chuỗi [SUGGESTIONS] (nếu có). Đó là câu hỏi gợi ý tự động, KHÔNG PHẢI nội dung y khoa cần kiểm duyệt."""

    def __init__(self, groq_service: GroqService):
        """
        Initialize Safety Guard Agent

        Args:
            groq_service: GroqService instance for Llama 3 inference
        """
        super().__init__(name="SafetyGuardAgent")
        self.groq_service = groq_service

    def execute(
        self,
        draft_response: str,
        health_profile: Optional[HealthProfile] = None,
    ) -> SafetyResult:
        """
        Validate draft response against user's health profile.

        Args:
            draft_response: Draft medical response from Clinical RAG Agent
            health_profile: User's health profile (EHR)

        Returns:
            SafetyResult with validated/modified response and warnings
        """
        start = time.time()

        if not health_profile:
            latency = time.time() - start
            self.logger.info("No health profile provided, skipping safety check")
            return SafetyResult(
                final_response=draft_response,
                warnings=[],
                is_safe=True,
                latency=latency,
            )

        try:
            self.logger.info("Cross-checking draft response with health profile...")

            profile_text = self._format_health_profile(health_profile)
            prompt = self._build_safety_prompt(draft_response, profile_text)

            raw_response = self.groq_service.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=2048,
            )

            latency = time.time() - start

            safety_data = self._parse_safety_response(raw_response)

            warnings = []
            for w in safety_data.get("warnings", []):
                warnings.append(
                    Warning(
                        severity=w.get("severity", "medium"),
                        message=w.get("message", ""),
                        reason=w.get("reason", ""),
                        affected_conditions=w.get("affected_conditions", []),
                    )
                )

            modified = safety_data.get("modified_response")
            final_response = modified if modified else draft_response

            # Hậu xử lý bằng Regex để quét sạch các câu miễn trừ/Lưu ý tự động kiểu "không xung đột với hồ sơ sức khỏe"
            import re
            disclaimer_pattern = r"(?i)\s*Lưu ý:\s*Mặc dù\s+.*?không\s+xung\s+đột\s+với\s+hồ\s+sơ\s+sức\s+khỏe\s+hiện\s+tại\s+của\s+bạn.*?(?:\n|$)"
            final_response = re.sub(disclaimer_pattern, "", final_response).strip()

            is_safe = safety_data.get("is_safe", True)

            self.logger.info(
                f"Safety check complete: is_safe={is_safe}, "
                f"warnings={len(warnings)} (latency: {latency:.3f}s)"
            )

            return SafetyResult(
                final_response=final_response,
                warnings=warnings,
                is_safe=is_safe,
                latency=latency,
            )

        except Exception as e:
            latency = time.time() - start
            self.logger.error(f"Safety check failed: {str(e)}")
            self.logger.warning("Returning draft response without safety validation")
            return SafetyResult(
                final_response=draft_response,
                warnings=[],
                is_safe=True,
                latency=latency,
            )

    def _format_health_profile(self, profile: HealthProfile) -> str:
        """Format health profile into readable text for the LLM"""
        parts = ["HỒ SƠ SỨC KHỎE BỆNH NHÂN:"]

        if profile.chronic_diseases:
            parts.append(f"- Bệnh mãn tính: {', '.join(profile.chronic_diseases)}")

        if profile.allergies:
            parts.append(f"- Dị ứng: {', '.join(profile.allergies)}")

        if profile.current_medications:
            parts.append(
                f"- Thuốc đang dùng: {', '.join(profile.current_medications)}"
            )

        if profile.age:
            parts.append(f"- Tuổi: {profile.age}")

        if profile.gender:
            parts.append(f"- Giới tính: {profile.gender}")
            
        # Thêm thông tin thể chất & BMI với logic phòng thủ
        bmi_info = calculate_bmi_status(profile.height, profile.weight)
        if profile.height:
            parts.append(f"- Chiều cao: {profile.height} cm")
        if profile.weight:
            parts.append(f"- Cân nặng: {profile.weight} kg")
        if "Không xác định" not in bmi_info:
            parts.append(f"- Chỉ số BMI: {bmi_info}")

        return "\n".join(parts)

    def _build_safety_prompt(
        self, draft_response: str, profile_text: str
    ) -> str:
        """Build the safety validation prompt"""
        return f"""{profile_text}

---

BẢN NHÁP PHẢN HỒI Y KHOA CẦN KIỂM TRA:
{draft_response}

---

Hãy rà soát bản nháp trên và trả về kết quả JSON."""

    def _parse_safety_response(self, raw_response: str) -> dict:
        """Parse JSON response from Safety Guard LLM"""
        import re
        raw_response = raw_response.strip()

        # Tìm kiếm JSON nằm giữa cặp dấu ```json ... ``` hoặc ``` ... ```
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Nếu không có code block, tìm ký tự '{' đầu tiên và '}' cuối cùng
            start_idx = raw_response.find("{")
            end_idx = raw_response.rfind("}")
            if start_idx != -1 and end_idx != -1:
                json_str = raw_response[start_idx : end_idx + 1]
            else:
                json_str = raw_response

        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError as e:
            self.logger.warning(
                f"Failed to parse safety response as JSON: {str(e)}. "
                f"Treating as safe. Raw: {raw_response[:500]}..."
            )
            return {"is_safe": True, "warnings": [], "modified_response": None}

