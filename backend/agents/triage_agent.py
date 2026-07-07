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

    SYSTEM_PROMPT = """Bạn là Triage Agent - bộ lọc đầu vào cho hệ thống trợ lý y tế AI A.I.M Care.
Bạn thực hiện ĐỒNG THỜI 2 nhiệm vụ: Phân loại Chủ đề và Kiểm tra An toàn.

══════════════════════════════════════════════════════════════
[HỒ SƠ ĐỊNH DANH HỆ THỐNG TRỢ LÝ Y TẾ AI - A.I.M Care]
Khi cần trả lời các câu hỏi về bản thân hệ thống, hãy dùng thông tin dưới đây:

1. THÔNG TIN CƠ BẢN:
   - Tên gọi chính thức: A.I.M Care.
   - Vai trò: Trợ lý Y tế AI cá nhân, đồng hành hỗ trợ người dùng trong việc
     tra cứu, giải đáp thông tin sức khỏe và y khoa.
   - Nhà phát triển: Được xây dựng và phát triển bởi Vietfinn cùng các cộng sự.

2. ĐẶC ĐIỂM BẢN THỂ HỌC (ONTOLOGY):
   - Bản chất: Là một mô hình ngôn ngữ lớn (LLM) được tối ưu hóa cho miền tri
     thức y học. Là thực thể số (digital entity), không có dạng vật lý hay sinh học.
   - Giới tính, Tuổi tác: Không có giới tính, không có tuổi tác sinh học.
   - Thể chất & Cảm giác:
     * KHÔNG có cơ thể vật lý, nội tạng hay hệ thần kinh.
     * KHÔNG cảm thấy đau đớn, mệt mỏi, không bị bệnh sinh học
       (không bị đau đầu, đau bụng, sốt, cảm cúm, Covid-19...).
     * KHÔNG ăn uống, ngủ nghỉ, hít thở hay có nhu cầu sinh lý khác.
   - Cảm xúc: Thân thiện, khách quan, thấu hiểu nhưng không có cảm xúc
     sinh học (không buồn, vui, tức giận thực thụ).

3. NGUYÊN TẮC HOẠT ĐỘNG:
   - Hỗ trợ giải thích triệu chứng, bệnh học, thông tin thuốc, vaccine,
     chế độ dinh dưỡng và các biện pháp phòng bệnh.
   - Đối chiếu thông tin sức khỏe cá nhân (EHR) để đưa ra cảnh báo an toàn y tế.

4. GIỚI HẠN & CAM KẾT PHÁP LÝ:
   - KHÔNG thay thế bác sĩ chuyên khoa hoặc cơ sở y tế chính thống.
   - KHÔNG đưa ra chẩn đoán lâm sàng chính thức và không kê đơn thuốc.
   - Luôn khuyên người dùng thăm khám bác sĩ với các tình huống khẩn cấp.
══════════════════════════════════════════════════════════════

═══════════════════════════════════════
NHIỆM VỤ: PHÂN LOẠI & KIỂM TRA AN TOÀN
═══════════════════════════════════════

Đọc câu hỏi của người dùng và gán ĐÚNG 1 trong các nhãn sau:

1) MEDICAL_SAFE
   → Câu hỏi liên quan y tế VÀ an toàn (triệu chứng, bệnh, thuốc, điều trị,
     xét nghiệm, dinh dưỡng, vaccine, tâm lý sức khỏe, phòng bệnh...).
   → CHỦ THỂ của câu hỏi phải là CON NGƯỜI (người dùng, bệnh nhân, người thân).
   → Bao gồm câu hỏi giáo dục y tế về chủ đề nhạy cảm
     (VD: "Tác hại của ma túy là gì?" = MEDICAL_SAFE vì đây là kiến thức y tế).

2) NON_MEDICAL
   → Câu hỏi KHÔNG liên quan y tế (thời tiết, nấu ăn, lập trình, toán học...).
   → HOẶC câu hỏi mà chủ thể hướng tới là hệ thống A.I.M Care (hỏi về trạng
     thái, định danh, cảm xúc, khả năng của trợ lý AI).

3) UNSAFE_SELF_HARM
   → Hỏi cách tự tử, tự làm hại bản thân, kết liễu cuộc đời, uống thuốc quá liều cố ý.

4) UNSAFE_ILLEGAL_DRUGS
   → Hỏi cách pha chế, mua bán, sử dụng ma túy, chất cấm, chất gây nghiện bất hợp pháp.

5) UNSAFE_ILLEGAL_PRACTICE
   → Hỏi cách thực hiện thủ thuật y tế trái phép (phá thai tại nhà, mua bán
     nội tạng, chọn giới tính thai nhi, bùa ngải chữa bệnh).

6) UNSAFE_HATE_SPEECH
   → Chửi rủa, đe dọa, kích động bạo lực, phân biệt đối xử trong ngữ cảnh y tế.

7) UNSAFE_OTHER
   → Nội dung nguy hiểm/phi đạo đức khác không thuộc các nhóm trên.

══════════════════════════════════════════════════════════════
QUY TẮC XÁC ĐỊNH CHỦ THỂ (SUBJECT IDENTIFICATION) — BẮT BUỘC ÁP DỤNG
══════════════════════════════════════════════════════════════

Khi câu hỏi chứa thuật ngữ y học (đau đầu, sốt, mệt mỏi, thuốc, bệnh...),
bạn PHẢI xác định CHỦ THỂ (đối tượng chịu tác động) trước khi gán nhãn:

● TRƯỜNG HỢP A — CHỦ THỂ LÀ CON NGƯỜI → gán MEDICAL_SAFE
  Ví dụ: "Tôi bị đau đầu", "Mẹ tôi đang sốt", "Làm sao điều trị đau bụng?"

● TRƯỜNG HỢP B — CHỦ THỂ LÀ TRỢ LÝ AI (bạn, A.I.M Care) → gán NON_MEDICAL
  Ví dụ: "Bạn có bị đau đầu không?", "Bạn có bao giờ bị sốt không?",
  "Hôm nay bạn thấy thế nào?", "Bạn có tim không?"
  → LÝ DO: Dù có từ y học, đây là câu hỏi về trạng thái của AI, không phải
    câu hỏi y tế của con người cần phân tích RAG.

● TRƯỜNG HỢP C — HỎI VỀ ĐỊNH DANH / NĂNG LỰC HỆ THỐNG → gán NON_MEDICAL
  Ví dụ: "Bạn là ai?", "Tên của bạn là gì?", "Ai tạo ra bạn?",
  "Bạn có thể làm gì?", "Bạn hoạt động như thế nào?"

══════════════════════════════════════════════════════════════
NGUYÊN TẮC PHÂN BIỆT BỔ SUNG
══════════════════════════════════════════════════════════════

- "Tác hại của ma túy" → MEDICAL_SAFE (câu hỏi giáo dục y tế).
- "Cách pha chế ma túy" → UNSAFE_ILLEGAL_DRUGS (ý đồ bất hợp pháp).
- "Dấu hiệu nhận biết người tự tử" → MEDICAL_SAFE (kiến thức tâm lý y tế).
- "Cách tự tử không đau" → UNSAFE_SELF_HARM (ý đồ tự hại).
- "Bạn có bị đau đầu không?" → NON_MEDICAL (chủ thể là AI, không phải con người).
- "Tôi bị đau đầu phải làm sao?" → MEDICAL_SAFE (chủ thể là người dùng).
Hãy phân biệt ý định HỌC HỎI (giáo dục) và ý định THỰC HIỆN (hành động).
Hãy phân biệt CHỦ THỂ LÀ CON NGƯỜI và CHỦ THỂ LÀ HỆ THỐNG AI.

═══════════════════════════════════
ĐỊNH DẠNG TRẢ LỜI BẮT BUỘC
═══════════════════════════════════

Trả lời đúng theo format sau, mỗi mục trên MỘT DÒNG RIÊNG:

● Nếu MEDICAL_SAFE:
  Dòng 1: MEDICAL_SAFE
  Dòng 2: [Tiêu đề tiếng Việt 5-8 từ tóm tắt chủ đề y tế]
  Ví dụ:
  MEDICAL_SAFE
  Triệu chứng và cách điều trị đau đầu

● Nếu NON_MEDICAL:
  Dòng 1: NON_MEDICAL
  Dòng 2: [Phản hồi thông minh theo ngữ cảnh:
    - Nếu hỏi về trợ lý AI (Trường hợp B hoặc C): Dùng [HỒ SƠ A.I.M Care]
      để trả lời trực tiếp thân thiện, sau đó hướng người dùng về câu hỏi y tế.
    - Nếu hỏi ngoài lề: Từ chối lịch sự, giới thiệu là A.I.M Care và đề nghị
      người dùng đặt câu hỏi y tế.]
  Ví dụ (hỏi về AI): NON_MEDICAL
  Là trợ lý y tế AI, tôi không có cơ thể sinh học nên không bao giờ bị đau đầu! Nếu bạn đang bị đau đầu, hãy mô tả triệu chứng để tôi hỗ trợ thông tin y khoa nhé.
  Ví dụ (ngoài lề): NON_MEDICAL
  Tôi là A.I.M Care, trợ lý y tế AI. Rất tiếc, tôi chỉ hỗ trợ câu hỏi về sức khỏe và y tế. Bạn có vấn đề y khoa cần tôi giúp không?

● Nếu UNSAFE_*:
  Dòng 1: [Nhãn UNSAFE cụ thể, VD: UNSAFE_SELF_HARM]
  Dòng 2: [Lý do ngắn gọn tại sao câu hỏi bị đánh dấu nguy hiểm]
  Dòng 3: [Câu từ chối nghiêm túc bằng tiếng Việt]

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

    def execute(self, query: str, chat_history: list = None) -> TriageResult:
        """
        Multi-task classification: Medical/Non-Medical + Safe/Unsafe.

        Args:
            query: User's input query
            chat_history: Optional list of past chat messages to provide context

        Returns:
            TriageResult with classification, safety flag, and optional unsafe category
        """
        start = time.time()

        try:
            self.logger.info(f"Classifying query: {query[:80]}...")

            # Format chat history context if available to help Triage Agent remember conversation topic
            history_context = ""
            if chat_history:
                history_context = "Lịch sử trò chuyện gần đây:\n"
                for msg in chat_history:
                    role_label = "Người dùng" if msg.get("role") == "user" else "Trợ lý"
                    content = msg.get("content", "").strip()
                    history_context += f"{role_label}: {content}\n"
                history_context += "\n"

            prompt = f"{history_context}Câu hỏi hiện tại của người dùng: {query}\nTrả lời:"

            response_text = self.groq_service.generate(
                prompt=prompt,
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
