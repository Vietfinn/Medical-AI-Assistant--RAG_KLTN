import re
import logging
from typing import List, Dict, Optional
from models.schemas import Warning, HealthProfile

logger = logging.getLogger(__name__)

class SafetyChecker:
    """Check for drug-disease and drug-allergy interactions"""
    
    # Common drug-disease interactions (simplified)
    DRUG_DISEASE_INTERACTIONS = {
        "aspirin": ["loét dạ dày", "viêm dạ dày", "đau dạ dày", "xuất huyết tiêu hóa"],
        "ibuprofen": ["loét dạ dày", "viêm dạ dày", "đau dạ dày", "suy thận"],
        "metformin": ["suy thận", "bệnh thận"],
        "corticosteroid": ["đái tháo đường", "tiểu đường", "loét dạ dày"],
        "nsaid": ["loét dạ dày", "viêm dạ dày", "suy thận", "tim mạch"],
    }
    
    # Common drug categories
    DRUG_CATEGORIES = {
        "thuốc giảm đau": ["aspirin", "ibuprofen", "paracetamol", "nsaid"],
        "kháng sinh": ["penicillin", "amoxicillin", "ciprofloxacin"],
        "thuốc tiểu đường": ["metformin", "insulin", "glipizide"],
    }
    
    def __init__(self):
        """Initialize safety checker"""
        pass
    
    def check_safety(
        self,
        response_text: str,
        health_profile: Optional[HealthProfile]
    ) -> List[Warning]:
        """
        Check response for safety issues based on health profile
        
        Args:
            response_text: Generated response text
            health_profile: User health profile
            
        Returns:
            List of warnings
        """
        warnings = []
        
        if not health_profile:
            return warnings
        
        # Check for drug-allergy interactions
        allergy_warnings = self._check_allergies(response_text, health_profile.allergies)
        warnings.extend(allergy_warnings)
        
        # Check for drug-disease interactions
        disease_warnings = self._check_disease_interactions(
            response_text,
            health_profile.chronic_diseases
        )
        warnings.extend(disease_warnings)
        
        # Check for existing medication interactions
        med_warnings = self._check_medication_interactions(
            response_text,
            health_profile.current_medications
        )
        warnings.extend(med_warnings)
        
        return warnings
    
    def _check_allergies(self, text: str, allergies: List[str]) -> List[Warning]:
        """Check for allergy-related warnings"""
        warnings = []
        text_lower = text.lower()
        
        for allergy in allergies:
            allergy_lower = allergy.lower()
            
            # Check if allergenic substance is mentioned
            if allergy_lower in text_lower:
                warning = Warning(
                    severity="high",
                    message=f"⚠️ CẢNH BÁO: Phát hiện đề cập đến {allergy}",
                    reason=f"Bạn có tiền sử dị ứng với {allergy}. KHÔNG NÊN sử dụng thuốc/thực phẩm chứa chất này.",
                    affected_conditions=[allergy]
                )
                warnings.append(warning)
        
        return warnings
    
    def _check_disease_interactions(
        self,
        text: str,
        chronic_diseases: List[str]
    ) -> List[Warning]:
        """Check for drug-disease interactions"""
        warnings = []
        text_lower = text.lower()
        
        for drug, contraindicated_diseases in self.DRUG_DISEASE_INTERACTIONS.items():
            if drug in text_lower:
                for disease in chronic_diseases:
                    disease_lower = disease.lower()
                    
                    # Check if user's disease is contraindicated
                    for contraindicated in contraindicated_diseases:
                        if contraindicated in disease_lower or disease_lower in contraindicated:
                            warning = Warning(
                                severity="high",
                                message=f"⚠️ CẢNH BÁO: {drug.upper()} có thể không phù hợp",
                                reason=f"Bạn có tiền sử {disease}. Thuốc {drug} có thể làm trầm trọng thêm tình trạng này. Vui lòng tham khảo bác sĩ trước khi sử dụng.",
                                affected_conditions=[disease, drug]
                            )
                            warnings.append(warning)
                            break
        
        return warnings
    
    def _check_medication_interactions(
        self,
        text: str,
        current_medications: List[str]
    ) -> List[Warning]:
        """Check for drug-drug interactions"""
        warnings = []
        text_lower = text.lower()
        
        # Simple check: warn if suggesting new medications while on existing ones
        drug_keywords = [
            "thuốc", "dùng", "uống", "aspirin", "ibuprofen", "paracetamol",
            "kháng sinh", "metformin"
        ]
        
        has_drug_suggestion = any(keyword in text_lower for keyword in drug_keywords)
        
        if has_drug_suggestion and current_medications:
            warning = Warning(
                severity="medium",
                message="ℹ️ LƯU Ý: Tương tác thuốc",
                reason=f"Bạn đang sử dụng: {', '.join(current_medications)}. Nếu định dùng thêm thuốc mới, vui lòng tham khảo bác sĩ hoặc dược sĩ để tránh tương tác thuốc.",
                affected_conditions=current_medications
            )
            warnings.append(warning)
        
        return warnings
    
    def extract_citations(self, text: str) -> List[str]:
        """
        Extract citation markers from text
        
        Args:
            text: Response text
            
        Returns:
            List of citation IDs
        """
        # Look for patterns like [Tài liệu 1], [Tài liệu 2], etc.
        pattern = r'\[Tài liệu (\d+)\]'
        matches = re.findall(pattern, text)
        return [f"doc_{m}" for m in matches]
    
    def highlight_warnings(self, text: str) -> str:
        """
        Add HTML highlighting to warning text
        
        Args:
            text: Response text
            
        Returns:
            Text with HTML tags for highlighting
        """
        # Highlight warning markers
        text = re.sub(
            r'(⚠️ CẢNH BÁO[^:]*:)',
            r'<span class="warning-high">\1</span>',
            text
        )
        
        text = re.sub(
            r'(ℹ️ LƯU Ý[^:]*:)',
            r'<span class="warning-medium">\1</span>',
            text
        )
        
        return text
