import logging
from typing import List, Dict, Optional
import google.generativeai as genai
from config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini API"""

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

    def generate_response(
        self,
        query: str,
        documents: List[Dict],
        health_profile: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate response using Gemini

        Args:
            query: User query
            documents: Retrieved documents
            health_profile: User health profile
            system_prompt: System prompt template

        Returns:
            Generated response text
        """
        if self.model is None:
            raise RuntimeError("Gemini not configured. Call configure() first.")

        # Build context from documents
        context = self._build_context(documents)

        # Build health profile text
        profile_text = (
            self._build_profile_text(health_profile)
            if health_profile
            else "Không có thông tin hồ sơ sức khỏe."
        )

        # Build prompt
        prompt = self._build_prompt(query, context, profile_text, system_prompt)

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise

    def gate_query(self, query: str) -> tuple[bool, str]:
        """
        Decide whether the query is medical. If not medical, return a short response.

        Returns:
            (is_medical, response_text)
        """
        if self.model is None:
            raise RuntimeError("Gemini not configured. Call configure() first.")

        prompt = self._build_gate_prompt(query)

        try:
            response = self.model.generate_content(prompt)
            text = (response.text or "").strip()
        except Exception as e:
            logger.error(f"Error during medical gate check: {str(e)}")
            raise

        normalized = text.strip().upper()
        if normalized.startswith("MEDICAL"):
            return True, ""

        # If Gemini returns an empty string, provide a safe default
        if not text:
            text = "Xin lỗi, tôi chỉ hỗ trợ các câu hỏi y tế. Bạn có thể mô tả vấn đề sức khỏe của bạn không?"

        return False, text

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
    ) -> str:
        """Build complete prompt for Gemini"""

        if system_prompt is None:
            system_prompt = """Bạn là một trợ lý y tế AI chuyên nghiệp và cẩn trọng. Nhiệm vụ của bạn là:

1. TRÁCH NHIỆM CHÍNH:
   - Trả lời câu hỏi y tế dựa CHÍNH XÁC và CHẶT CHẼ vào các tài liệu đã cung cấp
   - KHÔNG bịa đặt hoặc thêm thông tin không có trong tài liệu
   - Luôn kiểm tra tương tác thuốc/bệnh với hồ sơ bệnh nhân

2. KIỂM TRA AN TOÀN (QUAN TRỌNG NHẤT):
   - ĐỌC KỸ hồ sơ sức khỏe của bệnh nhân
   - KIỂM TRA xem các phương pháp điều trị có xung đột với:
     * Bệnh mãn tính của bệnh nhân
     * Dị ứng thuốc/thực phẩm
     * Thuốc đang sử dụng
   - NẾU phát hiện xung đột nguy hiểm, BẮT BUỘC phải:
     * Bắt đầu câu trả lời bằng "⚠️ CẢNH BÁO AN TOÀN:"
     * Giải thích rõ ràng nguy hiểm
     * Khuyên bệnh nhân tham khảo bác sĩ
     * KHÔNG khuyên dùng thuốc/phương pháp đó

3. TRÍCH DẪN:
   - Mỗi thông tin quan trọng phải có [Tài liệu X] để trích dẫn
   - Giúp người dùng biết nguồn gốc thông tin

4. NGÔN NGỮ:
   - Dùng tiếng Việt thân thiện, dễ hiểu
   - Tránh thuật ngữ y khoa phức tạp (hoặc giải thích nếu cần)
   - Thể hiện sự đồng cảm

5. GIỚI HẠN:
   - KHÔNG đưa ra chẩn đoán chính thức
   - LUÔN khuyên gặp bác sĩ cho các trường hợp nghiêm trọng
   - KHÔNG kê đơn thuốc, chỉ cung cấp thông tin tham khảo

VÍ DỤ CẢNH BÁO AN TOÀN:
⚠️ CẢNH BÁO AN TOÀN: Tôi thấy trong hồ sơ bạn có tiền sử dị ứng với Aspirin. Tài liệu đề cập đến việc sử dụng Aspirin, nhưng điều này CÓ THỂ GÂY NGUY HIỂM cho bạn. Vui lòng KHÔNG tự ý sử dụng thuốc này và tham khảo bác sĩ để được tư vấn phương pháp thay thế an toàn."""

        prompt = f"""{system_prompt}

---

{profile_text}

---

CÁC TÀI LIỆU THAM KHẢO:

{context}

---

CÂU HỎI CỦA BỆNH NHÂN:
{query}

---

HÃY TRẢ LỜI:
(Nhớ kiểm tra an toàn với hồ sơ bệnh nhân trước khi trả lời)
"""
        return prompt

    def _build_gate_prompt(self, query: str) -> str:
        """Build prompt for the medical relevance gate"""
        return f"""Bạn là bộ lọc đầu vào cho trợ lý y tế. Hãy quyết định câu hỏi có LIÊN QUAN Y TẾ không.

Quy tắc:
1) Nếu câu hỏi liên quan sức khỏe, y tế, triệu chứng, bệnh, thuốc, điều trị, xét nghiệm, chăm sóc sức khỏe -> trả lời đúng 1 từ: MEDICAL
2) Nếu KHÔNG liên quan y tế (chào hỏi, trò chuyện, kiến thức ngoài y tế...) -> trả lời ngắn gọn bằng tiếng Việt (1-2 câu) để từ chối lịch sự và hướng dẫn hỏi về sức khỏe.

Yêu cầu bắt buộc:
- Không giải thích.
- Không thêm nhãn khác ngoài "MEDICAL".
- Nếu không phải y tế, tuyệt đối không trả về chữ "MEDICAL".

Câu hỏi: {query}
Trả lời:"""

    def is_configured(self) -> bool:
        """Check if Gemini is configured"""
        return self.model is not None
