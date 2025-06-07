"""
explanation_service.py

Service for generating explanations about medical topics, procedures, and conditions.
This service is separate from symptom analysis to ensure clear educational responses
for questions that are asking for information rather than reporting health issues.
"""

import logging
import json
import asyncio
import httpx
from typing import Dict, List, Any, Optional

from django.conf import settings
from ...utils.openai_manager import openai_manager

from ..utils.medical_info_templates import get_template_for_topic
from ..utils.response_formatter import STANDARD_DISCLAIMER, format_medical_info_response

# Configure logging
logger = logging.getLogger(__name__)

class ExplanationService:
    """
    Service for providing educational explanations about medical topics.
    Focuses on medical procedures, tests, conditions, and general health information.
    """
    
    def __init__(self):
        """Initialize the service"""
        pass
    
    async def get_explanation(self, topic: str, patient_data: Optional[Dict] = None) -> Dict[str, List[str]]:
        """
        Get an explanation for a medical topic.
        
        Args:
            topic: The medical topic or procedure to explain
            patient_data: Optional patient data for personalization
            
        Returns:
            Dictionary with message list for the response
        """
        try:
            logger.info(f"Generating explanation for topic: {topic}")
            
            # 1. Check for template match first
            template = get_template_for_topic(topic)
            if template:
                logger.info(f"Found template for {topic}")
                return {"messages": format_medical_info_response(
                    topic=topic,
                    summary=template.get("brief_answer", ""),
                    details=template.get("detailed_info", {}),
                    include_disclaimer=True
                )}
            
            # 2. Try MedlinePlus Health Topic lookup
            medline_info = await self._fetch_health_topic(topic)
            if medline_info:
                logger.info(f"Found MedlinePlus info for {topic}")
                return {"messages": medline_info}
            
            # 3. Generate an explanation with AI
            gpt_explanation = await self._generate_ai_explanation(topic, patient_data)
            return {"messages": gpt_explanation}
            
        except Exception as e:
            logger.error(f"Error generating explanation for {topic}: {str(e)}")
            # Fallback response
            return {"messages": [
                f"I apologize, but I don't have specific information about {topic} at the moment.",
                "I recommend discussing this with your healthcare provider for accurate information.",
                STANDARD_DISCLAIMER
            ]}
    
    async def _fetch_health_topic(self, topic: str) -> List[str]:
        """
        Fetch information from MedlinePlus Health Topics API.
        Different from symptom lookup - this targets educational content.
        """
        try:
            # Use MedlinePlus Health Topics API
            base_url = "https://wsearch.nlm.nih.gov/ws/query"
            params = {
                "db": "healthTopics",
                "term": f"{topic} site:medlineplus.gov",
                "retmax": 1,
                "rettype": "json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(base_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract the relevant information
                    if "result" in data and data["result"].get("documentList", {}).get("document"):
                        document = data["result"]["documentList"]["document"][0]
                        title = document.get("title", "")
                        snippet = document.get("snippet", "")
                        url = document.get("accessibleVersion", "")
                        
                        messages = [
                            f"# {title}",
                            "",
                            snippet,
                            "",
                            f"For more information: {url}",
                            "",
                            STANDARD_DISCLAIMER
                        ]
                        return messages
                        
            return []
        except Exception as e:
            logger.error(f"Error fetching health topic information: {str(e)}")
            return []
    
    async def _generate_ai_explanation(self, topic: str, patient_data: Optional[Dict] = None) -> List[str]:
        """
        Generate an explanation using AI when no template or MedlinePlus data is available.
        """
        try:
            # Create a prompt for the topic
            prompt = self._create_explanation_prompt(topic, patient_data)
            
            response = await openai_manager.chat_completion(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a medical education assistant providing accurate, structured explanations of medical topics."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            explanation = response.choices[0].message.content.strip()
            
            # Format into paragraphs
            paragraphs = [p.strip() for p in explanation.split('\n') if p.strip()]
            
            # Ensure we have the disclaimer
            if STANDARD_DISCLAIMER not in explanation:
                paragraphs.append(STANDARD_DISCLAIMER)
                
            return paragraphs
            
        except Exception as e:
            logger.error(f"Error generating AI explanation: {str(e)}")
            return [
                f"I'm sorry, I couldn't generate specific information about {topic}.",
                "Please consult with your healthcare provider for accurate information.",
                STANDARD_DISCLAIMER
            ]
    
    def _create_explanation_prompt(self, topic: str, patient_data: Optional[Dict] = None) -> str:
        """Create a prompt for generating an explanation about a medical topic."""
        prompt = f"""Provide a clear, structured explanation about {topic} covering:

1. WHAT IS IT: Brief definition and description
2. PURPOSE: Why it's done or recommended
3. WHAT TO EXPECT: The procedure or experience
4. BENEFITS: Key benefits or reasons for it
5. RISKS/SIDE EFFECTS: Potential risks or side effects 
6. PREPARATION: How patients should prepare (if applicable)
7. ALTERNATIVES: Alternative options (if applicable)

Format your response in clear paragraphs with headings (using Markdown # for headings).
Focus on educational information rather than diagnostic advice.
Keep your explanation accurate, balanced, and easy to understand.
End with a clear reminder that this is educational information, not personalized medical advice.
"""
        
        # Add patient context if available
        if patient_data and isinstance(patient_data, dict):
            # Extract relevant demographic info without revealing PII
            age = None
            gender = None
            
            if "birthDate" in patient_data:
                from datetime import datetime
                try:
                    birth_date = datetime.fromisoformat(patient_data["birthDate"].replace('Z', '+00:00'))
                    today = datetime.now()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                except (ValueError, TypeError):
                    pass
            
            if "gender" in patient_data:
                gender = patient_data["gender"]
            
            if age or gender:
                prompt += f"\n\nConsider demographics: "
                if age:
                    prompt += f"age {age}, "
                if gender:
                    prompt += f"{gender}, "
                prompt = prompt.rstrip(", ")
                prompt += " when providing relevant information."
        
        return prompt

# Singleton instance
explanation_service = ExplanationService()