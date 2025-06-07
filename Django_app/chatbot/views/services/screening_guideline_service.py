"""
screening_guideline_service.py

Service for determining if a patient should undergo specific screening procedures
based on their age, risk factors, and medical history.
"""

import logging
from datetime import datetime
from typing import Dict, Tuple, Optional, Any, List

logger = logging.getLogger(__name__)

class ScreeningGuidelineService:
    """
    Service that implements evidence-based screening guidelines.
    Determines if a patient should undergo specific screening procedures
    based on their age, risk factors, and medical history.
    """
    
    # Age-based screening guidelines (based on USPSTF recommendations)
    COLONOSCOPY_MIN_AGE = 45
    MAMMOGRAM_MIN_AGE = 40
    PSA_MIN_AGE = 55
    
    def __init__(self):
        # Initialize any needed resources
        pass
        
    def should_get_screening(self, 
                            screening_type: str, 
                            patient_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Determine if a patient should get a specific screening based on guidelines
        
        Args:
            screening_type: Type of screening (colonoscopy, mammogram, etc.)
            patient_data: Patient FHIR data dictionary
            
        Returns:
            Tuple of (recommendation boolean, explanation string)
        """
        screening_type = screening_type.lower()
        
        if not patient_data:
            return False, "Unable to provide a personalized recommendation without patient information."
        
        # Calculate patient age
        patient_age = self._calculate_age(patient_data)
        if patient_age is None:
            return False, "Unable to determine your age from record. Please consult your healthcare provider."
        
        # Check for specific screening types
        if "colonoscopy" in screening_type:
            return self._evaluate_colonoscopy_need(patient_age, patient_data)
        elif "mammogram" in screening_type:
            return self._evaluate_mammogram_need(patient_age, patient_data)
        elif any(term in screening_type for term in ["psa", "prostate"]):
            return self._evaluate_prostate_screening_need(patient_age, patient_data)
        else:
            return False, f"Specific guidelines for {screening_type} screening are not available. Please consult your healthcare provider."
    
    def _calculate_age(self, patient_data: Dict[str, Any]) -> Optional[int]:
        """Calculate patient age from birth date in FHIR data"""
        try:
            if "birthDate" in patient_data:
                birth_date = datetime.fromisoformat(patient_data["birthDate"].replace('Z', '+00:00'))
                today = datetime.now()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                return age
            return None
        except (ValueError, TypeError):
            logger.error("Unable to parse birthDate from patient data")
            return None
    
    def _has_risk_factors(self, patient_data: Dict[str, Any], condition_list: List[str]) -> bool:
        """Check if patient has specific risk factors based on conditions"""
        try:
            # Check if there are conditions in the patient data
            if "conditions" in patient_data and isinstance(patient_data["conditions"], list):
                conditions = patient_data["conditions"]
                for condition in conditions:
                    if "code" in condition and "text" in condition["code"]:
                        condition_text = condition["code"]["text"].lower()
                        if any(risk.lower() in condition_text for risk in condition_list):
                            return True
            return False
        except Exception as e:
            logger.error(f"Error checking risk factors: {str(e)}")
            return False
    
    def _evaluate_colonoscopy_need(self, age: int, patient_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Evaluate if patient needs a colonoscopy based on age and risk factors"""
        # List of risk factors that might necessitate earlier or more frequent screening
        colon_risk_factors = [
            "colorectal cancer", "colon cancer", "rectal cancer", "polyp", 
            "inflammatory bowel disease", "crohn", "ulcerative colitis",
            "lynch syndrome", "familial adenomatous polyposis"
        ]
        
        # Check for family history
        has_family_history = False
        if "family_history" in patient_data and isinstance(patient_data["family_history"], list):
            for history in patient_data["family_history"]:
                if any(risk in str(history).lower() for risk in colon_risk_factors):
                    has_family_history = True
                    break
        
        # Check for personal risk factors
        has_risk_factors = self._has_risk_factors(patient_data, colon_risk_factors)
        
        # Make recommendation based on guidelines
        if age >= self.COLONOSCOPY_MIN_AGE:
            return True, f"Based on your age ({age}), the US Preventive Services Task Force recommends colorectal cancer screening starting at age {self.COLONOSCOPY_MIN_AGE}."
        elif has_risk_factors or has_family_history:
            return True, "Based on your medical or family history, you may need earlier colorectal cancer screening. Please consult with your healthcare provider."
        else:
            return False, f"Current guidelines don't recommend routine colonoscopy screening before age {self.COLONOSCOPY_MIN_AGE} unless you have specific risk factors."

    def _evaluate_mammogram_need(self, age: int, patient_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Evaluate if patient needs a mammogram based on age and risk factors"""
        # Implementation similar to colonoscopy evaluation
        gender = patient_data.get("gender", "").lower()
        
        if gender == "male":
            return False, "Routine mammogram screening is not typically recommended for men, but please consult your provider if you have specific concerns."
        
        # Check age and risk factors
        if age >= self.MAMMOGRAM_MIN_AGE:
            return True, f"Based on your age ({age}), mammogram screening is recommended starting at age {self.MAMMOGRAM_MIN_AGE}."
        else:
            return False, f"Current guidelines don't recommend routine mammogram screening before age {self.MAMMOGRAM_MIN_AGE} unless you have specific risk factors."
    
    def _evaluate_prostate_screening_need(self, age: int, patient_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Evaluate if patient needs prostate screening"""
        gender = patient_data.get("gender", "").lower()
        
        if gender != "male":
            return False, "Prostate cancer screening is only applicable to men."
            
        if age >= self.PSA_MIN_AGE:
            return True, f"For men aged {self.PSA_MIN_AGE} and older, discussing prostate cancer screening with your doctor is recommended to make an informed decision."
        else:
            return False, f"Current guidelines don't routinely recommend prostate cancer screening for men under age {self.PSA_MIN_AGE} unless you have specific risk factors."

# Singleton instance
screening_guideline_service = ScreeningGuidelineService()