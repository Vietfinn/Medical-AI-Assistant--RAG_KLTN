import logging
from typing import List, Dict, Optional
import google.generativeai as genai
from config import settings
from utils.quota_logger import log_quota_errors

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini API (Clinical RAG Agent)"""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """
        Initialize Gemini service

        Args:
            api_key: Google Gemini API key
            model_name: Model name to use
        """
        self.api_key = api_key
        self.model_name = model_name
        self.model = None

    def configure(self):
        """Configure Gemini API"""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini API configured with model: {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {str(e)}")
            return False

    @log_quota_errors
    def generate_response(
        self,
        query: str,
        documents: List[Dict],
        health_profile: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict]] = None,
    ) -> str:
        import time
        import re

        if self.model is None:
            raise RuntimeError("Gemini not configured. Call configure() first.")

        context = self._build_context(documents)
        profile_text = (
            self._build_profile_text(health_profile)
            if health_profile
            else "Không có thông tin hồ sơ sức khỏe."
        )
        prompt = self._build_prompt(query, context, profile_text, system_prompt, chat_history)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                error_msg = str(e)
                # Retry cho lỗi 429 hoặc 503
                if "429" in error_msg or "ResourceExhausted" in error_msg or "503" in error_msg or "ServiceUnavailable" in error_msg:
                    if attempt < max_retries - 1:
                        # Thử phân tích số giây để đợi từ thông báo lỗi
                        wait_match = re.search(r"retry in (\d+(\.\d+)?)s", error_msg)
                        wait_t = float(wait_match.group(1)) + 1.0 if wait_match else 10.0
                        logger.warning(f"⚠️ Gemini API Quota/Overload (429/503). Tự động đợi {wait_t}s (Lần thử {attempt + 1}/{max_retries})...")
                        time.sleep(wait_t)
                        continue
                    else:
                        logger.error("❌ Đã thử lại nhiều lần nhưng vẫn lỗi 429/503.")
                        return "Hệ thống AI đang quá tải tạm thời. Xin vui lòng chờ một lát rồi thử lại!"
                
                # Các lỗi khác (như 403) thì raise thẳng
                logger.error(f"Error generating response: {error_msg}")
                raise

    def _build_context(self, documents: List[Dict]) -> str:
        """Build context text from documents"""
        if not documents:
            return "Không tìm thấy tài liệu phù hợp."

        context_parts = []
        for idx, doc in enumerate(documents, 1):
            doc_text = f"""
[Tài liệu {idx}] - ID: {doc.get('doc_id', 'N/A')}
Câu hỏi: {doc.get('question', 'N/A')}
Câu trả lời từ bác sĩ: {doc.get('answer', 'N/A')}
---
"""
            context_parts.append(doc_text.strip())

        return "\n\n".join(context_parts)

    def _build_profile_text(self, health_profile: Dict) -> str:
        """Build health profile text"""
        parts = ["HỒ SƠ SỨC KHỎE BỆNH NHÂN:"]

        chronic_diseases = health_profile.get("chronic_diseases", [])
        if chronic_diseases:
            parts.append(f"- Bệnh mãn tính: {', '.join(chronic_diseases)}")

        allergies = health_profile.get("allergies", [])
        if allergies:
            parts.append(f"- Dị ứng: {', '.join(allergies)}")

        medications = health_profile.get("current_medications", [])
        if medications:
            parts.append(f"- Thuốc đang dùng: {', '.join(medications)}")

        age = health_profile.get("age")
        if age:
            parts.append(f"- Tuổi: {age}")

        gender = health_profile.get("gender")
        if gender:
            parts.append(f"- Giới tính: {gender}")

        return (
            "\n".join(parts) if len(parts) > 1 else "Không có thông tin hồ sơ sức khỏe."
        )

    def _build_prompt(
        self,
        query: str,
        context: str,
        profile_text: str,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict]] = None,
    ) -> str:
        """Build complete prompt for Gemini"""

        if system_prompt is None:
            system_prompt = """Bạn là một Trợ lý Y tế AI chuyên nghiệp và cẩn trọng.

NHIỆM VỤ CỐT LÕI:
1. TRẢ LỜI DỰA TRÊN TÀI LIỆU (ZERO-HALLUCINATION):
   - Chỉ trả lời dựa CHÍNH XÁC vào các thông tin có trong phần [CÁC TÀI LIỆU THAM KHẢO].
   - NẾU tài liệu không có thông tin, bạn BẮT BUỘC phải trả lời: "Xin lỗi, các tài liệu y khoa hiện tại của tôi chưa có thông tin về vấn đề này..." và KHÔNG TỰ SUY DIỄN.

2. KIỂM TRA ĐỐI CHIẾU AN TOÀN (TỐI QUAN TRỌNG):
   - Trước khi đưa ra lời khuyên/thuốc, phải ĐỐI CHIẾU với [Hồ sơ sức khỏe] của bệnh nhân.
   - Nếu phát hiện phương pháp/thuốc có xung đột với Bệnh nền, Dị ứng, hoặc Thuốc đang dùng:
     * Bắt đầu câu bằng: "⚠️ CẢNH BÁO AN TOÀN:"
     * Giải thích rõ rủi ro và KHUYÊN NGỪNG SỬ DỤNG phương pháp đó.

3. QUY TẮC ĐỊNH DẠNG & TRÌNH BÀY (BẮT BUỘC TUÂN THỦ NGHIÊM NGẶT):
   - CẤM CHÀO HỎI: Tuyệt đối KHÔNG dùng các từ giao tiếp thừa như "Chào bạn", "Tôi hiểu rằng...", "Mong thông tin này hữu ích". Đi thẳng vào câu trả lời.
   - TRÍCH DẪN ẨN: TUYỆT ĐỐI KHÔNG in ra các thẻ trích dẫn thô như [Tài liệu 1], [Tài liệu 2]. Hãy tự tổng hợp thông tin một cách tự nhiên.
   - XỬ LÝ KHI THIẾU HỒ SƠ: NẾU phần [HỒ SƠ SỨC KHỎE] là "Không có thông tin hồ sơ sức khỏe.", bạn PHẢI bắt đầu câu trả lời bằng đúng 1 dòng in nghiêng này: *(Lưu ý: Không có hồ sơ sức khỏe cá nhân, thông tin dưới đây chỉ mang tính tham khảo)*.
   - SỬ DỤNG MARKDOWN:
     * Dùng `###` cho các tiêu đề phụ (Ví dụ: ### Nguyên nhân, ### Lời khuyên).
     * Dùng `*` để gạch đầu dòng các ý ngắn gọn, súc tích (không quá 2 câu mỗi ý).
     * Dùng `**in đậm**` cho các từ khóa quan trọng, tên bệnh, tên thuốc.
     * Dùng `> ` (Blockquote) cho các cảnh báo rủi ro hoặc yêu cầu đi khám bác sĩ.

4. GIỚI HẠN PHÁP LÝ:
   - KHÔNG đưa ra chẩn đoán bệnh chính thức.
   - KHÔNG kê đơn thuốc. Luôn khuyên bệnh nhân tham vấn bác sĩ trực tiếp.

VÍ DỤ CẢNH BÁO AN TOÀN:
> **⚠️ CẢNH BÁO AN TOÀN:** Tôi thấy trong hồ sơ bạn có tiền sử dị ứng với Aspirin. Dù đây là phương pháp phổ biến, nhưng nó **CÓ THỂ GÂY NGUY HIỂM** cho bạn. Vui lòng không tự ý sử dụng và tham khảo ý kiến bác sĩ trực tiếp."""

        history_text = ""
        if chat_history and len(chat_history) > 0:
            history_text = "\n---\n[LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY]\n"
            for msg in chat_history:
                role = "Bệnh nhân" if msg.get("role") == "user" else "Trợ lý AI"
                history_text += f"{role}: {msg.get('content')}\n\n"

        prompt = f"""{system_prompt}

---
[HỒ SƠ SỨC KHỎE CỦA BỆNH NHÂN]
{profile_text}

---
[CÁC TÀI LIỆU THAM KHẢO]
{context}
{history_text}
---
[CÂU HỎI HIỆN TẠI]
{query}

---
HÃY TRẢ LỜI:"""
        return prompt

    def generate_response_stream(
        self,
        query: str,
        documents: List[Dict],
        health_profile: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict]] = None,
    ):
        """
        Stream response chunks from Gemini API using stream=True.
        Yields text chunks as they arrive from the model.

        Args:
            query: User's medical query
            documents: Retrieved & reranked documents
            health_profile: User health profile dict
            system_prompt: Optional custom system prompt
            chat_history: Recent conversation history

        Yields:
            str: Each text chunk from Gemini streaming response
        """
        import time
        import re

        if self.model is None:
            raise RuntimeError("Gemini not configured. Call configure() first.")

        context = self._build_context(documents)
        profile_text = (
            self._build_profile_text(health_profile)
            if health_profile
            else "Không có thông tin hồ sơ sức khỏe."
        )
        prompt = self._build_prompt(query, context, profile_text, system_prompt, chat_history)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt, stream=True)
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "ResourceExhausted" in error_msg or "503" in error_msg or "ServiceUnavailable" in error_msg:
                    if attempt < max_retries - 1:
                        wait_match = re.search(r"retry in (\d+(\.\d+)?)s", error_msg)
                        wait_t = float(wait_match.group(1)) + 1.0 if wait_match else 10.0
                        logger.warning(f"⚠️ Gemini Streaming Quota/Overload (429/503). Waiting {wait_t}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(wait_t)
                        continue
                    else:
                        logger.error("❌ Gemini streaming retries exhausted (429/503).")
                        yield "Hệ thống AI đang quá tải tạm thời. Xin vui lòng chờ một lát rồi thử lại!"
                        return
                logger.error(f"Error in streaming response: {error_msg}")
                raise

    def is_configured(self) -> bool:
        """Check if Gemini is configured"""
        return self.model is not None