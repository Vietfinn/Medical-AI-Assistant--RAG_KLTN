import time
from models.schemas import TriageResult
from services.groq_llm import GroqService
from agents.base import BaseAgent


class TriageAgent(BaseAgent):
    """
    Giai đoạn 1: Pre-retrieval Query Routing & Intent Classification

    Sử dụng Llama 3 (Groq LPU) để phân loại ý định truy vấn.
    Quyết định truy vấn có thuộc miền y tế hay không.
    Nếu không thuộc miền y tế → Early Exit, trả về phản hồi từ chối lịch sự.
    Đồng thời đề xuất tiêu đề ngắn gọn (5-8 từ) cho cuộc hội thoại.
    """

    SYSTEM_PROMPT = """Bạn là Triage Agent - bộ phân loại đầu vào cho hệ thống trợ lý y tế AI.
Bạn có 2 nhiệm vụ:

NHIỆM VỤ 1 - PHÂN LOẠI:
1) Nếu câu hỏi liên quan đến: sức khỏe, y tế, triệu chứng, bệnh tật, thuốc, điều trị, xét nghiệm, dinh dưỡng sức khỏe, chăm sóc sức khỏe, phòng bệnh, vaccine, tâm lý sức khỏe → nhãn MEDICAL
2) Nếu câu hỏi KHÔNG liên quan y tế → nhãn NON_MEDICAL

NHIỆM VỤ 2 - ĐẶT TÊN (chỉ khi MEDICAL):
Đặt một tiêu đề ngắn gọn bằng tiếng Việt (5-8 từ) tóm tắt chủ đề y tế của câu hỏi.

ĐỊNH DẠNG TRẢ LỜI BẮT BUỘC:
- Nếu MEDICAL: trả lời đúng 2 dòng, dòng 1 là "MEDICAL", dòng 2 là tiêu đề (5-8 từ).
  Ví dụ:
  MEDICAL
  Triệu chứng và cách điều trị đau đầu
- Nếu NON_MEDICAL: trả lời bằng tiếng Việt, ngắn gọn 1-2 câu, từ chối lịch sự và hướng dẫn người dùng hỏi về sức khỏe. KHÔNG ghi "MEDICAL" hay "NON_MEDICAL".

YÊU CẦU BẮT BUỘC:
- Tiêu đề phải bằng tiếng Việt, không có dấu ngoặc, dấu gạch, hay ký tự đặc biệt.
- Tiêu đề tóm tắt đúng nội dung y tế của câu hỏi.
- Phản hồi từ chối phải thân thiện và chuyên nghiệp."""

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
        Classify user query as medical or non-medical.
        If medical, also generate a suggested title for the conversation.

        Args:
            query: User's input query

        Returns:
            TriageResult with classification decision and suggested title
        """
        start = time.time()

        try:
            self.logger.info(f"Classifying query: {query[:80]}...")

            response_text = self.groq_service.generate(
                prompt=f"Câu hỏi: {query}\nTrả lời:",
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=256,
            )

            response_text = (response_text or "").strip()
            lines = [line.strip() for line in response_text.split("\n") if line.strip()]

            latency = time.time() - start

            if lines and lines[0].upper().startswith("MEDICAL"):
                suggested_title = None
                if len(lines) >= 2:
                    title_text = lines[1].strip()
                    words = title_text.split()
                    if len(words) > 8:
                        title_text = " ".join(words[:8])
                    if len(words) >= 3:
                        suggested_title = title_text

                self.logger.info(
                    f"Query classified as MEDICAL (title: {suggested_title}) (latency: {latency:.3f}s)"
                )
                return TriageResult(
                    is_medical=True,
                    response=None,
                    suggested_title=suggested_title,
                    latency=latency,
                )

            if not response_text or not lines:
                response_text = (
                    "Xin lỗi, tôi là trợ lý y tế AI và chỉ hỗ trợ các câu hỏi "
                    "liên quan đến sức khỏe. Bạn có thể mô tả vấn đề sức khỏe "
                    "của mình để tôi giúp bạn không?"
                )

            self.logger.info(
                f"Query classified as NON_MEDICAL (latency: {latency:.3f}s)"
            )
            return TriageResult(
                is_medical=False,
                response=response_text,
                suggested_title="Chưa có chủ đề",
                latency=latency,
            )

        except Exception as e:
            latency = time.time() - start
            self.logger.error(f"Triage classification failed: {str(e)}")
            raise
