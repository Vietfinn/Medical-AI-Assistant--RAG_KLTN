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

        # Load GROQ_LIST from settings/env as backup keys
        backup_keys = []
        try:
            from config import settings
            groq_list_str = getattr(settings, "GROQ_LIST", "") or ""
            if not groq_list_str:
                import os
                groq_list_str = os.getenv("GROQ_LIST", "")
            backup_keys = [k.strip() for k in groq_list_str.split(",") if k.strip()]
        except Exception:
            backup_keys = []

        # Build final rotation pool: start with initial api_key, followed by backup keys
        self.keys = [api_key]
        for k in backup_keys:
            if k not in self.keys:
                self.keys.append(k)

        self.current_key_idx = 0

    def _rotate_client_on_failure(self) -> bool:
        """Rotate to the next API key in the pool and reconfigure client"""
        if len(self.keys) <= 1:
            return False
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        next_key = self.keys[self.current_key_idx]
        logger.warning(
            f"Rotating Clinical Groq API Key to key index {self.current_key_idx} due to rate limit/failure."
        )
        self.client = Groq(api_key=next_key)
        return True

    def configure(self) -> bool:
        """Configure Groq client"""
        try:
            self.client = Groq(api_key=self.keys[self.current_key_idx])
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

        max_attempts = len(self.keys)
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "rate_limit" in err_msg or "429" in err_msg or "too many requests" in err_msg

                if is_rate_limit and attempt < max_attempts - 1:
                    if self._rotate_client_on_failure():
                        continue
                logger.error(f"Error generating clinical response from Groq on attempt {attempt+1}: {str(e)}")
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

        max_attempts = len(self.keys)
        for attempt in range(max_attempts):
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
                return
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "rate_limit" in err_msg or "429" in err_msg or "too many requests" in err_msg

                if is_rate_limit and attempt < max_attempts - 1:
                    if self._rotate_client_on_failure():
                        continue
                logger.error(f"Error in streaming response from Clinical Groq on attempt {attempt+1}: {str(e)}")
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
   - Trước khi đề xuất bất kỳ loại thuốc hay phương pháp điều trị nào, bạn bắt buộc phải đối chiếu cẩn thận với [Hồ sơ sức khỏe] của bệnh nhân (bao gồm Bệnh mãn tính, Dị ứng, và Thuốc đang dùng).
   - Nếu phát hiện xung đột nguy hiểm (chống chỉ định bệnh nền, dị ứng hoạt chất hoặc nguy cơ dị ứng chéo giữa các thuốc cùng nhóm, tương tác bất lợi giữa các thuốc):
     * Bạn bắt buộc phải hiển thị khối cảnh báo nổi bật ở đầu câu trả lời, bắt đầu chính xác bằng: "⚠️ CẢNH BÁO AN TOÀN:"
     * Trong phần cảnh báo này, không cảnh báo chung chung mà phải giải thích rõ ràng cơ chế y sinh học gây hại (ví dụ: giải thích cơ chế dị ứng chéo của hệ miễn dịch, cơ chế hoạt chất làm tổn thương/bào mòn niêm mạc cơ quan, hoặc tương tác đối kháng dược lực học, v.v.) để người đọc hiểu bản chất nguy hiểm.
     * Khuyên ngừng sử dụng hoặc không tự ý dùng thuốc/phương pháp đó.
     * CẤM TUYỆT ĐỐI chèn thêm bất kỳ câu khẳng định an toàn hay khuyến nghị tiêu chuẩn kiểu "không xung đột với hồ sơ sức khỏe..." ở cuối câu trả lời nếu phản hồi chứa cảnh báo nguy hiểm, để tránh mâu thuẫn trực tiếp.
    - Nếu câu trả lời có đề xuất hoặc đề cập đến việc sử dụng thuốc cụ thể, và toàn bộ các thuốc này hoàn toàn an toàn và KHÔNG có bất kỳ xung đột lâm sàng nào với hồ sơ bệnh nhân:
      * Tuyệt đối KHÔNG hiển thị khối cảnh báo đỏ "⚠️ CẢNH BÁO AN TOÀN" để tránh gây hoang mang bừa bãi. Tuyệt đối KHÔNG tự tạo cảnh báo giả hoặc dặn dò phòng ngừa thừa thãi nếu không có xung đột lâm sàng thực sự được xác nhận trong y văn đối với hồ sơ bệnh nhân.
      * Chỉ chèn một khuyến nghị tiêu chuẩn nhẹ nhàng ở cuối câu trả lời: "Lưu ý: Mặc dù thuốc được đề xuất không xung đột với hồ sơ sức khỏe hiện tại của bạn, hãy luôn tham khảo ý kiến của bác sĩ hoặc dược sĩ trước khi sử dụng để đảm bảo liều lượng phù hợp."
    - Nếu câu trả lời KHÔNG đề cập đến việc sử dụng thuốc cụ thể (ví dụ chỉ tư vấn về dinh dưỡng, sinh hoạt, tập luyện, hoặc giải thích cơ chế triệu chứng):
      * Tuyệt đối KHÔNG hiển thị khối cảnh báo đỏ "⚠️ CẢNH BÁO AN TOÀN".
      * Tuyệt đối KHÔNG được tự động chèn thêm bất kỳ câu "Lưu ý", câu miễn trừ trách nhiệm hoặc khuyến nghị chuẩn nào ở chân trang của câu trả lời. Kết thúc trực tiếp bằng nội dung tư vấn hữu ích.

3. YÊU CẦU NGÔN NGỮ (BẮT BUỘC):
    - Bạn bắt buộc phải trả lời 100% bằng tiếng Việt tự nhiên và chuẩn xác.
    - Tuyệt đối CẤM chèn các ký tự tiếng Trung (ví dụ như "是在", "的") hoặc từ ngữ tiếng Anh lẫn vào trong câu trả lời, trừ các tên riêng hoặc tên hoạt chất y văn quốc tế bắt buộc.

4. QUY TẮC ĐỊNH DẠNG & TRÌNH BÀY (BẮT BUỘC TUÂN THỦ NGHIÊM NGẶT):
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

5. GIỚI HẠN PHÁP LÝ:
   - KHÔNG đưa ra chẩn đoán bệnh chính thức.
   - KHÔNG kê đơn thuốc. Luôn khuyên bệnh nhân tham vấn bác sĩ trực tiếp.

6. CÂU HỎI GỢI Ý (BẮT BUỘC):
   - Sau khi trả lời XONG, bạn PHẢI chèn chuỗi [SUGGESTIONS] trên một dòng riêng biệt.
   - Ngay sau [SUGGESTIONS], liệt kê đúng 3 câu hỏi gợi ý liên quan mà người dùng có thể muốn hỏi tiếp.
   - Mỗi câu hỏi gợi ý trên một dòng riêng, KHÔNG đánh số, KHÔNG gạch đầu dòng.
   - Câu hỏi phải ngắn gọn (dưới 15 từ), liên quan trực tiếp đến nội dung vừa trả lời.
   - Ví dụ:
     [SUGGESTIONS]
     Triệu chứng nào cần đi khám bác sĩ ngay?
     Có cách phòng ngừa nào hiệu quả không?
     Chế độ ăn uống nên thay đổi như thế nào?

VÍ DỤ CẢNH BÁO AN TOÀN (KHI CÓ XUNG ĐỘT - DÙNG ĐỂ THAM KHẢO ĐỊNH DẠNG):
> **⚠️ CẢNH BÁO AN TOÀN:** Phát hiện nguy cơ [loại rủi ro]. Bạn có [bệnh nền / tiền sử dị ứng / thuốc đang dùng], do đó không được sử dụng [tên thuốc/phương pháp đề xuất]. [Giải thích cụ thể cơ chế sinh lý hoặc tương tác sinh học gây ra rủi ro cho cơ thể một cách trực quan, dễ hiểu]. Vui lòng không tự ý sử dụng và tham khảo ý kiến bác sĩ trực tiếp.



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