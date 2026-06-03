import time
from models.schemas import TriageResult
from services.groq_llm import GroqService
from agents.base import BaseAgent


# Các nhãn UNSAFE hợp lệ để parse
UNSAFE_CATEGORIES = {
    "UNSAFE_SELF_HARM": "SELF_HARM",
    "UNSAFE_ILLEGAL_DRUGS": "ILLEGAL_DRUGS",
    "UNSAFE_ILLEGAL_PRACTICE": "ILLEGAL_PRACTICE",
    "UNSAFE_HATE_SPEECH": "HATE_SPEECH",
    "UNSAFE_OTHER": "OTHER",
}


class TriageAgent(BaseAgent):
    """
    Giai đoạn 1: Pre-retrieval Multi-task Routing & Safety Gate

    Sử dụng Llama 3 (Groq LPU) để thực hiện đồng thời 2 nhiệm vụ:
      1. Phân loại ý định (Medical / Non-Medical)
      2. Kiểm tra an toàn (Safe / Unsafe + Phân nhóm rủi ro)

    Nếu UNSAFE → Early Exit, ghi log vào kho dữ liệu nghiên cứu.
    Nếu NON_MEDICAL → Early Exit, từ chối lịch sự.
    Nếu MEDICAL_SAFE → Cho phép đi tiếp vào pipeline RAG.
    """

    SYSTEM_PROMPT = """Bạn là Triage Agent - bộ lọc đầu vào cho hệ thống trợ lý y tế AI.
Bạn thực hiện ĐỒNG THỜI 2 nhiệm vụ: Phân loại Chủ đề và Kiểm tra An toàn.

═══════════════════════════════════════
NHIỆM VỤ: PHÂN LOẠI & KIỂM TRA AN TOÀN
═══════════════════════════════════════

Đọc câu hỏi của người dùng và gán ĐÚNG 1 trong các nhãn sau:

1) MEDICAL_SAFE
   → Câu hỏi liên quan y tế VÀ an toàn (hỏi về triệu chứng, bệnh, thuốc, điều trị, xét nghiệm, dinh dưỡng sức khỏe, vaccine, tâm lý sức khỏe, phòng bệnh...).
   → Bao gồm cả câu hỏi mang tính giáo dục về các chủ đề nhạy cảm (VD: "Tác hại của ma túy là gì?" = MEDICAL_SAFE vì đây là câu hỏi kiến thức y tế).

2) NON_MEDICAL
   → Câu hỏi KHÔNG liên quan y tế (thời tiết, nấu ăn, lập trình, toán học...).

3) UNSAFE_SELF_HARM
   → Hỏi cách tự tử, tự làm hại bản thân, kết liễu cuộc đời, uống thuốc quá liều cố ý.

4) UNSAFE_ILLEGAL_DRUGS
   → Hỏi cách pha chế, mua bán, sử dụng ma túy, chất cấm, chất gây nghiện bất hợp pháp.

5) UNSAFE_ILLEGAL_PRACTICE
   → Hỏi cách thực hiện thủ thuật y tế trái phép (phá thai tại nhà, mua bán nội tạng, chọn giới tính thai nhi, bùa ngải chữa bệnh).

6) UNSAFE_HATE_SPEECH
   → Chửi rủa, đe dọa, kích động bạo lực, phân biệt đối xử trong ngữ cảnh y tế.

7) UNSAFE_OTHER
   → Nội dung nguy hiểm/phi đạo đức khác không thuộc các nhóm trên.

═══════════════════════════════
NGUYÊN TẮC PHÂN BIỆT QUAN TRỌNG
═══════════════════════════════

- "Tác hại của ma túy" → MEDICAL_SAFE (câu hỏi giáo dục y tế).
- "Cách pha chế ma túy" → UNSAFE_ILLEGAL_DRUGS (ý đồ bất hợp pháp).
- "Dấu hiệu nhận biết người tự tử" → MEDICAL_SAFE (kiến thức tâm lý y tế).
- "Cách tự tử không đau" → UNSAFE_SELF_HARM (ý đồ tự hại).
Hãy phân biệt ý định HỌC HỎI (giáo dục) và ý định THỰC HIỆN (hành động).

═══════════════════════════
ĐỊNH DẠNG TRẢ LỜI BẮT BUỘC
═══════════════════════════

Trả lời đúng theo format sau, mỗi mục trên MỘT DÒNG RIÊNG:

● Nếu MEDICAL_SAFE:
  Dòng 1: MEDICAL_SAFE
  Dòng 2: [Tiêu đề tiếng Việt 5-8 từ tóm tắt chủ đề y tế]
  Ví dụ:
  MEDICAL_SAFE
  Triệu chứng và cách điều trị đau đầu

● Nếu NON_MEDICAL:
  Dòng 1: NON_MEDICAL
  Dòng 2: [Giới thiệu ngắn gọn bạn là A.I.M Care - Trợ lý y tế AI cá nhân, sau đó hướng dẫn lịch sự người dùng đặt câu hỏi hoặc chia sẻ vấn đề liên quan đến y tế/sức khỏe bằng tiếng Việt, 1-2 câu]
  Ví dụ:
  NON_MEDICAL
  Tôi là A.I.M Care, trợ lý y tế AI cá nhân của bạn. Xin lỗi, tôi chỉ hỗ trợ các câu hỏi liên quan đến sức khỏe và y tế. Bạn có thể chia sẻ triệu chứng hoặc câu hỏi y khoa để tôi trợ giúp nhé!

● Nếu UNSAFE_*:
  Dòng 1: [Nhãn UNSAFE cụ thể, VD: UNSAFE_SELF_HARM]
  Dòng 2: [Lý do ngắn gọn tại sao câu hỏi bị đánh dấu nguy hiểm]
  Dòng 3: [Câu từ chối nghiêm túc bằng tiếng Việt]
  Ví dụ:
  UNSAFE_ILLEGAL_DRUGS
  Câu hỏi yêu cầu hướng dẫn pha chế chất cấm
  Xin lỗi, hệ thống không thể hỗ trợ nội dung liên quan đến chất cấm hoặc hoạt động bất hợp pháp. Nếu bạn đang gặp khó khăn, vui lòng liên hệ đường dây hỗ trợ.

YÊU CẦU BẮT BUỘC:
- Tiêu đề phải bằng tiếng Việt, không có dấu ngoặc, dấu gạch, hay ký tự đặc biệt.
- CHỈ trả lời theo đúng format trên, KHÔNG thêm giải thích hay markdown."""

    # Thông điệp mặc định cho từng nhóm UNSAFE
    UNSAFE_RESPONSES = {
        "SELF_HARM": (
            "⚠️ Hệ thống nhận thấy câu hỏi của bạn liên quan đến hành vi tự hại. "
            "Chúng tôi không thể hỗ trợ nội dung này. Nếu bạn đang gặp khó khăn, "
            "xin hãy gọi ngay **Đường dây nóng hỗ trợ tâm lý: 19001267** (24/7)."
        ),
        "ILLEGAL_DRUGS": (
            "⚠️ Hệ thống phát hiện câu hỏi liên quan đến chất cấm hoặc hoạt động bất hợp pháp. "
            "Chúng tôi không thể hỗ trợ nội dung này theo quy định pháp luật Việt Nam."
        ),
        "ILLEGAL_PRACTICE": (
            "⚠️ Hệ thống phát hiện câu hỏi liên quan đến thủ thuật y tế trái phép hoặc vi phạm đạo đức y khoa. "
            "Chúng tôi không thể hỗ trợ nội dung này. Vui lòng tham vấn bác sĩ tại cơ sở y tế hợp pháp."
        ),
        "HATE_SPEECH": (
            "⚠️ Hệ thống phát hiện nội dung mang tính chất đe dọa hoặc kích động bạo lực. "
            "Chúng tôi không thể hỗ trợ nội dung này."
        ),
        "OTHER": (
            "⚠️ Hệ thống phát hiện câu hỏi của bạn chứa nội dung không phù hợp với chính sách an toàn. "
            "Chúng tôi không thể hỗ trợ nội dung này."
        ),
    }

    def __init__(self, groq_service: GroqService):
        """
        Initialize Triage Agent

        Args:
            groq_service: GroqService instance for Llama 3 inference
        """
        super().__init__(name="TriageAgent")
        self.groq_service = groq_service

    def execute(self, query: str) -> TriageResult:
        """
        Multi-task classification: Medical/Non-Medical + Safe/Unsafe.

        Args:
            query: User's input query

        Returns:
            TriageResult with classification, safety flag, and optional unsafe category
        """
        start = time.time()

        try:
            self.logger.info(f"Classifying query: {query[:80]}...")

            response_text = self.groq_service.generate(
                prompt=f"Câu hỏi: {query}\nTrả lời:",
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=300,
            )

            response_text = (response_text or "").strip()
            lines = [line.strip() for line in response_text.split("\n") if line.strip()]

            latency = time.time() - start

            if not lines:
                self.logger.warning("Empty response from Triage Agent")
                return TriageResult(
                    is_medical=False,
                    is_safe=True,
                    response=(
                        "Xin lỗi, tôi là trợ lý y tế AI và chỉ hỗ trợ các câu hỏi "
                        "liên quan đến sức khỏe. Bạn có thể mô tả vấn đề sức khỏe "
                        "của mình để tôi giúp bạn không?"
                    ),
                    suggested_title="Chưa có chủ đề",
                    latency=latency,
                )

            label = lines[0].upper().strip()

            # ── MEDICAL_SAFE ──
            if label.startswith("MEDICAL_SAFE") or label == "MEDICAL":
                suggested_title = None
                if len(lines) >= 2:
                    title_text = lines[1].strip()
                    words = title_text.split()
                    if len(words) > 8:
                        title_text = " ".join(words[:8])
                    if len(words) >= 3:
                        suggested_title = title_text

                self.logger.info(
                    f"Query classified as MEDICAL_SAFE (title: {suggested_title}) (latency: {latency:.3f}s)"
                )
                return TriageResult(
                    is_medical=True,
                    is_safe=True,
                    response=None,
                    suggested_title=suggested_title,
                    latency=latency,
                )

            # ── UNSAFE_* ──
            for unsafe_label, category in UNSAFE_CATEGORIES.items():
                if label.startswith(unsafe_label):
                    reason = lines[1] if len(lines) >= 2 else "Nội dung không phù hợp"
                    # Lấy câu từ chối từ Llama hoặc dùng mặc định
                    llama_response = lines[2] if len(lines) >= 3 else None
                    fallback_response = self.UNSAFE_RESPONSES.get(category, self.UNSAFE_RESPONSES["OTHER"])
                    final_response = llama_response or fallback_response

                    self.logger.warning(
                        f"🚨 Query classified as {unsafe_label} | Reason: {reason} | (latency: {latency:.3f}s)"
                    )
                    return TriageResult(
                        is_medical=False,
                        is_safe=False,
                        unsafe_category=category,
                        unsafe_reason=reason,
                        response=final_response,
                        suggested_title="Câu hỏi không phù hợp",
                        latency=latency,
                    )

            # ── NON_MEDICAL (Default Fallback) ──
            non_medical_response = lines[1] if len(lines) >= 2 else response_text
            if not non_medical_response or "NON_MEDICAL" in non_medical_response.upper():
                non_medical_response = (
                    "Xin lỗi, tôi là trợ lý y tế AI và chỉ hỗ trợ các câu hỏi "
                    "liên quan đến sức khỏe. Bạn có thể mô tả vấn đề sức khỏe "
                    "của mình để tôi giúp bạn không?"
                )

            self.logger.info(
                f"Query classified as NON_MEDICAL (latency: {latency:.3f}s)"
            )
            return TriageResult(
                is_medical=False,
                is_safe=True,
                response=non_medical_response,
                suggested_title="Chưa có chủ đề",
                latency=latency,
            )

        except Exception as e:
            latency = time.time() - start
            self.logger.error(f"Triage classification failed: {str(e)}")
            raise
