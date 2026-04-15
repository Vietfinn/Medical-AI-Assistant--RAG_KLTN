import json
import time
from typing import List, Optional
from models.schemas import SafetyResult, Warning, HealthProfile
from services.groq_llm import GroqService
from agents.base import BaseAgent


class SafetyGuardAgent(BaseAgent):
    """
    Giai đoạn 4: Post-generation Guardrails & Safety Validation

    Sử dụng Llama 3 (Groq LPU) để rà soát chéo (cross-check) bản nháp
    phản hồi y khoa với hồ sơ sức khỏe cá nhân (EHR) của người dùng.
    Phát hiện chống chỉ định y khoa và tương tác bất lợi.
    """

    SYSTEM_PROMPT = """Bạn là Safety Guard Agent - vệ sĩ an toàn y tế cho hệ thống AI.
Nhiệm vụ của bạn: rà soát BẢN NHÁP PHẢN HỒI Y KHOA và đối chiếu với HỒ SƠ SỨC KHỎE để phát hiện nguy hiểm.

NHIỆM VỤ CỤ THỂ:
1. Đọc kỹ bản nháp phản hồi y khoa
2. Đối chiếu với hồ sơ sức khỏe bệnh nhân (bệnh mãn tính, dị ứng, thuốc đang dùng)
3. Phát hiện:
   - Chống chỉ định y khoa (thuốc/phương pháp xung đột với bệnh nền)
   - Dị ứng thuốc (đề xuất thuốc mà bệnh nhân dị ứng)
   - Tương tác thuốc bất lợi (thuốc mới xung đột với thuốc đang dùng)

QUY TẮC TRẢ LỜI - BẮT BUỘC trả về JSON:
{
  "is_safe": true/false,
  "warnings": [
    {
      "severity": "high" hoặc "medium" hoặc "low",
      "message": "Mô tả ngắn gọn cảnh báo",
      "reason": "Giải thích chi tiết lý do",
      "affected_conditions": ["điều kiện bị ảnh hưởng"]
    }
  ],
  "modified_response": "Bản phản hồi ĐÃ CHỈNH SỬA (thêm cảnh báo nếu cần) hoặc null nếu an toàn"
}

LƯU Ý QUAN TRỌNG:
- Nếu KHÔNG có hồ sơ sức khỏe → trả is_safe=true, warnings=[], modified_response=null
- Nếu AN TOÀN → trả is_safe=true, warnings=[], modified_response=null
- Nếu NGUY HIỂM → thêm cảnh báo ⚠️ vào đầu modified_response, giữ nguyên nội dung gốc phía sau
- CHỈ trả về JSON hợp lệ, không thêm markdown hay giải thích"""

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
        raw_response = raw_response.strip()

        if raw_response.startswith("```"):
            lines = raw_response.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_response = "\n".join(lines)

        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            self.logger.warning(
                f"Failed to parse safety response as JSON, "
                f"treating as safe. Raw: {raw_response[:200]}..."
            )
            return {"is_safe": True, "warnings": [], "modified_response": None}
