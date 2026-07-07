import logging
from typing import List, Dict, Optional
from config import settings
from utils.health_utils import calculate_bmi_status, is_profile_completed
from groq import Groq

logger = logging.getLogger(__name__)


class ClinicalLLMService:
    """Service for interacting with Groq API for clinical RAG generation (using GROQ_API_KEY2)"""

    def __init__(self, api_key: str, model_name: str = "llama-3.3-70b-versatile"):
        """
        Initialize Clinical LLM service using Groq

        Args:
            api_key: Groq API key
            model_name: Model name to use
        """
        self.api_key = api_key
        self.model_name = model_name
        self.client = None

    def configure(self) -> bool:
        """Configure Groq client"""
        try:
            self.client = Groq(api_key=self.api_key)
            logger.info(f"Clinical Groq LLM configured with model: {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Clinical Groq LLM: {str(e)}")
            return False

    def generate_response(
        self,
        query: str,
        documents: List[Dict],
        health_profile: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict]] = None,
        strict_mode: bool = True,
    ) -> str:
        """
        Generate a RAG-grounded response using Groq Llama 3.3.
        """
        if self.client is None:
            raise RuntimeError("Clinical Groq LLM not configured. Call configure() first.")

        context = self._build_context(documents)
        profile_completed = is_profile_completed(health_profile)
        profile_text = (
            self._build_profile_text(health_profile)
            if health_profile
            else "Không có thông tin hồ sơ sức khỏe."
        )
        prompt = self._build_prompt(
            query=query,
            context=context,
            profile_text=profile_text,
            system_prompt=system_prompt,
            chat_history=chat_history,
            strict_mode=strict_mode,
            profile_completed=profile_completed,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Error generating clinical response from Groq: {str(e)}")
            raise

    def generate_response_stream(
        self,
        query: str,
        documents: List[Dict],
        health_profile: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
        chat_history: Optional[List[Dict]] = None,
        strict_mode: bool = True,
        context_addon: Optional[str] = None,
    ):
        """
        Stream response chunks from Groq.
        Yields text chunks as they arrive.
        """
        if self.client is None:
            raise RuntimeError("Clinical Groq LLM not configured. Call configure() first.")

        context = self._build_context(documents)
        profile_completed = is_profile_completed(health_profile)
        profile_text = (
            self._build_profile_text(health_profile)
            if health_profile
            else "Không có thông tin hồ sơ sức khỏe."
        )
        prompt = self._build_prompt(
            query=query,
            context=context,
            profile_text=profile_text,
            system_prompt=system_prompt,
            chat_history=chat_history,
            strict_mode=strict_mode,
            context_addon=context_addon,
            profile_completed=profile_completed,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                stream=True,
            )
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Error in streaming response from Clinical Groq: {str(e)}")
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
        """Build health profile text with defensive BMI logic"""
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
            
        height = health_profile.get("height")
        weight = health_profile.get("weight")
        bmi_info = calculate_bmi_status(height, weight)
        
        if height:
            parts.append(f"- Chiều cao: {height} cm")
        if weight:
            parts.append(f"- Cân nặng: {weight} kg")
        if "Không xác định" not in bmi_info:
            parts.append(f"- Chỉ số BMI: {bmi_info}")

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
        strict_mode: bool = True,
        context_addon: Optional[str] = None,
        profile_completed: bool = False,
    ) -> str:
        """Build complete prompt"""
        if system_prompt is None:
            rule_1 = """1. TRẢ LỜI DỰA TRÊN TÀI LIỆU (ZERO-HALLUCINATION):
   - Chỉ trả lời dựa CHÍNH XÁC vào các thông tin có trong phần [CÁC TÀI LIỆU THAM KHẢO].
   - NẾU tài liệu không có thông tin, bạn BẮT BUỘC phải trả lời: "Xin lỗi, các tài liệu y khoa hiện tại của tôi chưa có thông tin về vấn đề này..." và KHÔNG TỰ SUY DIỄN.""" if strict_mode else """1. TRẢ LỜI LINH HOẠT VỚI KIẾN THỨC CHUYÊN MÔN:
   - Ưu tiên sử dụng thông tin trong phần [CÁC TÀI LIỆU THAM KHẢO] nếu có.
   - NẾU tài liệu không có thông tin và bạn phải tự trả lời từ tri thức của mình, bạn BẮT BUỘC phải mở đầu câu trả lời bằng đúng khối blockquote Markdown nổi bật này (không thêm bớt):
     > 🤖 **Tham khảo từ Trí tuệ Nhân tạo (AI):** Câu hỏi này chưa có tài liệu đối chiếu trực tiếp từ thư viện y khoa xác thực của hệ thống. AI đã tự động tổng hợp thông tin từ kiến thức chung để bạn tham khảo. Vui lòng hỏi ý kiến bác sĩ chuyên khoa trước khi áp dụng."""

            system_prompt = f"""Bạn là một Trợ lý Y tế AI chuyên nghiệp và cẩn trọng.

NHIỆM VỤ CỐT LÕI:
{rule_1}

2. KIỂM TRA ĐỐI CHIẾU AN TOÀN (TỐI QUAN TRỌNG):
   - Trước khi đưa ra lời khuyên/thuốc, phải ĐỐI CHIẾU với [Hồ sơ sức khỏe] của bệnh nhân.
   - Nếu phát hiện phương pháp/thuốc có xung đột với Bệnh nền, Dị ứng, hoặc Thuốc đang dùng:
     * Bắt đầu câu bằng: "⚠️ CẢNH BÁO AN TOÀN:"
     * Giải thích rõ rủi ro và KHUYÊN NGỪNG SỬ DỤNG phương pháp đó.

3. QUY TẮC ĐỊNH DẠNG & TRÌNH BÀY (BẮT BUỘC TUÂN THỦ NGHIÊM NGẶT):
   - CẤM CHÀO HỎI: Tuyệt đối KHÔNG dùng các từ giao tiếp thừa như "Chào bạn", "Tôi hiểu rằng...", "Mong thông tin này hữu ích". Đi thẳng vào câu trả lời.
   - TRÍCH DẪN CUỐI ĐOẠN: Khi sử dụng thông tin từ tài liệu tham khảo, bạn BẮT BUỘC phải chèn ký hiệu trích dẫn dạng [1], [2], [3] (trong đó [1] tương ứng với [Tài liệu 1], [2] tương ứng với [Tài liệu 2],...) vào CUỐI ĐOẠN VĂN hoặc cuối mỗi ý chính chứa thông tin đó.
     * Quy tắc: Số trong ngoặc vuông tương ứng với số thứ tự của tài liệu.
     * Nếu một đoạn hoặc ý chính tổng hợp từ nhiều tài liệu, hãy chèn liền nhau, ví dụ: [1][3].
     * TUYỆT ĐỐI KHÔNG viết dạng dài như "[Tài liệu 1]" hay "[Nguồn 2]". Chỉ dùng ký hiệu ngắn gọn dạng [1], [2].
     * Nếu đoạn trả lời hoàn toàn do bạn tự tổng hợp từ kiến thức chung (không có tài liệu đối chiếu phù hợp nào), KHÔNG chèn bất kỳ ký hiệu trích dẫn nào cho đoạn đó.
   - SỬ DỤNG MARKDOWN:
     * Dùng `###` cho các tiêu đề phụ (Ví dụ: ### Nguyên nhân, ### Lời khuyên).
     * Dùng `*` để gạch đầu dòng các ý ngắn gọn, súc tích (không quá 2 câu mỗi ý).
     * Dùng `**in đậm**` cho các từ khóa quan trọng, tên bệnh, tên thuốc.
     * Dùng `> ` (Blockquote) cho các cảnh báo rủi ro hoặc yêu cầu đi khám bác sĩ.

4. GIỚI HẠN PHÁP LÝ:
   - KHÔNG đưa ra chẩn đoán bệnh chính thức.
   - KHÔNG kê đơn thuốc. Luôn khuyên bệnh nhân tham vấn bác sĩ trực tiếp.

5. CÂU HỎI GỢI Ý (BẮT BUỘC):
   - Sau khi trả lời XONG, bạn PHẢI chèn chuỗi [SUGGESTIONS] trên một dòng riêng biệt.
   - Ngay sau [SUGGESTIONS], liệt kê đúng 3 câu hỏi gợi ý liên quan mà người dùng có thể muốn hỏi tiếp.
   - Mỗi câu hỏi gợi ý trên một dòng riêng, KHÔNG đánh số, KHÔNG gạch đầu dòng.
   - Câu hỏi phải ngắn gọn (dưới 15 từ), liên quan trực tiếp đến nội dung vừa trả lời.
   - Ví dụ:
     [SUGGESTIONS]
     Triệu chứng nào cần đi khám bác sĩ ngay?
     Có cách phòng ngừa nào hiệu quả không?
     Chế độ ăn uống nên thay đổi như thế nào?

VÍ DỤ CẢNH BÁO AN TOÀN:
> **⚠️ CẢNH BÁO AN TOÀN:** Tôi thấy trong hồ sơ bạn có tiền sử dị ứng với Aspirin. Dù đây là phương pháp phổ biến, nhưng nó **CÓ THỂ GÂY NGUY HIỂM** cho bạn. Vui lòng không tự ý sử dụng và tham khảo ý kiến bác sĩ trực tiếp.

VÍ DỤ TRÍCH DẪN CUỐI ĐOẠN:
### Nguyên nhân gây đau
* **Viêm loét dạ dày** là nguyên nhân phổ biến nhất gây đau thượng vị đột ngột, kèm theo cảm giác nóng rát dữ dội sau khi ăn đồ cay nóng. [1]
* Bên cạnh đó, **hội chứng ruột kích thích (IBS)** cũng có thể dẫn tới những cơn đau co thắt dọc khung đại tràng khi gặp căng thẳng tâm lý kéo dài. [2][3]
* Nếu bạn thấy các cơn đau đi kèm với sốt cao hoặc đại tiện ra phân đen, hãy nhanh chóng tới khám trực tiếp tại bệnh viện gần nhất để đảm bảo an toàn y khoa.
"""

        history_text = ""
        if chat_history and len(chat_history) > 0:
            history_text = "\n---\n[LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY]\n"
            for msg in chat_history:
                role = "Bệnh nhân" if msg.get("role") == "user" else "Trợ lý AI"
                history_text += f"{role}: {msg.get('content')}\n\n"

        addon_text = ""
        if context_addon:
            addon_text = f"\n{context_addon}\n"

        prompt = f"""{system_prompt}
{addon_text}
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
        disclaimer = ""
        if not profile_completed:
            disclaimer = "*(Lưu ý: Không có hồ sơ sức khỏe cá nhân, thông tin dưới đây chỉ mang tính tham khảo)*\n\n"
        prompt = prompt.replace("HÃY TRẢ LỜI:", f"HÃY TRẢ LỜI:\n{disclaimer}")
        return prompt

    def is_configured(self) -> bool:
        """Check if LLM is configured"""
        return self.client is not None