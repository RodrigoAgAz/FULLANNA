#!/usr/bin/env python
"""
personalized_medical_advice_service.py

A production-ready, asynchronous module for generating personalized medical advice.
This service combines:
  - Patient-specific data from your FHIR server (via FHIRService from your codebase)
  - Recent conversation context (via your session/conversation manager)
  - Evidence-based guidelines from MedlinePlus Connect (queried via HTTP)
into a comprehensive prompt for GPT-4. The final advice always includes a prominent disclaimer.

Before deploying:
  - Ensure that your FHIR server (settings.FHIR_SERVER_URL) and credentials (from .env) are correct.
  - Verify that the MedlinePlus Connect query parameters match your requirements.
  - Confirm that your conversation manager functions are correctly integrated.
"""

import logging
import asyncio
from datetime import datetime
from typing import List, Dict
import requests
import xml.etree.ElementTree as ET
import openai

from django.conf import settings
from chatbot.views.services.fhir_service import FHIRService

# Configure logging
logger = logging.getLogger("PersonalizedMedicalAdvice")
logger.setLevel(logging.INFO)

# ------------------------------------------------------------------------------
# Evidence-Based Guidelines via MedlinePlus Connect
# ------------------------------------------------------------------------------
print ("29")
# Mapping from condition names to MedlinePlus Connect codes.
CONDITION_CODE_MAPPING = {
    "diabetes": "44054006",      # Example SNOMED code for Type 2 diabetes
    "hypertension": "38341003",  # Example SNOMED code for hypertension
    # Expand as needed
}

def get_medlineplus_guidelines(condition: str) -> str:
    """
    Query MedlinePlus Connect for guideline text for the given condition.
    Returns guideline text or None.
    """
    code = CONDITION_CODE_MAPPING.get(condition.lower())
    if not code:
        logger.warning(f"No mapping found for condition: {condition}")
        return None

    base_url = "https://connect.medlineplus.gov/service"
    params = {
        "mainSearchCriteria.v.c": code,
        "informationRecipient.language": "en"
    }
    try:
        response = requests.get(base_url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            guideline_text = None
            for desc in root.iter('description'):
                if desc.text:
                    guideline_text = desc.text.strip()
                    break
            if guideline_text:
                logger.info(f"Retrieved guideline for {condition}")
                return guideline_text
            else:
                logger.warning(f"No description found for {condition}")
                return None
        else:
            logger.error(f"MedlinePlus error {response.status_code} for condition {condition}")
            return None
    except Exception as e:
        logger.error(f"Error querying MedlinePlus for {condition}: {e}")
        return None

def get_evidence_based_guidelines(conditions: List[str]) -> Dict[str, str]:
    """
    For each condition in the list, query MedlinePlus Connect and return a mapping.
    """
    guidelines = {}
    for cond in conditions:
        text = get_medlineplus_guidelines(cond)
        if text:
            guidelines[cond] = text
    return guidelines

# ------------------------------------------------------------------------------
# Asynchronous Summarization of Conversation Context
# ------------------------------------------------------------------------------
def redact_sensitive_info(text: str) -> str:
    """
    Stub for redacting sensitive information. Replace with real redaction as needed.
    """
    return text

async def summarize_messages(messages: List[str], openai_client: "AsyncGPT4Client") -> str:
    """
    Uses GPT-4-turbo to generate a concise bullet-point summary of conversation context.
    Redacts sensitive data before summarization.
    """
    if not messages:
        return ""
    joined_messages = "\n".join(f"User: {redact_sensitive_info(m)}" for m in messages)
    system_prompt = (
        "You are an assistant that summarizes conversation context. "
        "Return a concise bullet list (max ~100 tokens) capturing key user info "
        "(symptoms, conditions, preferences) without including any sensitive data."
    )
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Conversation so far:\n{joined_messages}"}
    ]
    try:
        response = await openai_client.chat_completions_create(
            model="gpt-4-turbo",
            messages=prompt_messages,
            temperature=0.7,
            max_tokens=150
        )
        summary_text = response.choices[0].message.content.strip()
        return summary_text
    except Exception as e:
        logger.error(f"Error summarizing messages: {e}", exc_info=True)
        return ""

# ------------------------------------------------------------------------------
# Asynchronous GPT-4 Client Using OpenAI's Async API
# ------------------------------------------------------------------------------
class AsyncGPT4Client:
    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key

    async def chat_completions_create(self, model: str, messages: List[dict],
                                        temperature: float = 0.7,
                                        max_tokens: int = 300) -> dict:
        """
        Calls the OpenAI async ChatCompletion API.
        """
        try:
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response
        except Exception as e:
            logger.error(f"Error generating GPT-4 response: {e}")
            raise

    async def generate_advice(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat_completions_create(
            model="gpt-4-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()

# ------------------------------------------------------------------------------
# Conversation Context Retrieval (Replace with your real conversation/session management)
# ------------------------------------------------------------------------------
def get_conversation_context(patient_id: str) -> Dict[str, any]:
    """
    Retrieve recent conversation context for a patient.
    Replace this with your actual session/conversation manager call.
    """
    return {
        "recent_messages": [
            "I have been worried about my blood sugar levels.",
            "Last week I asked how to control my diabetes."
        ],
        "user_facts": {"diabetes": True}
    }

# ------------------------------------------------------------------------------
# Personalized Medical Advice Service (Hybrid Approach, Async)
# ------------------------------------------------------------------------------
class PersonalizedMedicalAdviceService:
    def __init__(self, gpt_client: AsyncGPT4Client):
        self.gpt_client = gpt_client
        # Use your actual FHIRService from your codebase
        self.fhir_service = FHIRService()

    async def get_personalized_advice(self, patient_id: str, user_query: str) -> str:
        """
        Combines patient data, conversation context, and evidence-based guidelines
        into a prompt for GPT-4, and returns personalized medical advice.
        """
        # Retrieve patient data via your FHIRService (using your real FHIR query)
        patient_resource = await asyncio.to_thread(self.fhir_service.get_patient, patient_id)
        if not patient_resource:
            return "Error: Patient data not found."

        patient_data = self._extract_patient_data(patient_resource)
        context = get_conversation_context(patient_id)
        recent_msgs = context.get("recent_messages", [])
        context_summary = await summarize_messages(recent_msgs, self.gpt_client)

        conditions = patient_data.get("conditions", [])
        guidelines = get_evidence_based_guidelines(conditions)

        prompt = self._build_prompt(user_query, patient_data, context_summary, guidelines)
        logger.info("Constructed prompt for GPT-4:")
        logger.info(prompt)

        advice = await self.gpt_client.generate_advice(prompt)
        advice = self._ensure_disclaimer(advice)
        return advice

    def _extract_patient_data(self, patient_resource: dict) -> dict:
        """
        Extracts relevant patient data from the FHIR Patient resource.
        Adjust extraction logic according to your actual FHIR resource structure.
        """
        data = {}
        birth_date_str = getattr(patient_resource, "birthDate", None)
        data["age"] = self._calculate_age(birth_date_str) if birth_date_str else "Unknown"
        # Replace these with your actual extraction calls, e.g., using self.fhir_service.get_patient_conditions
        data["conditions"] = ["diabetes", "hypertension"]
        data["medications"] = ["Metformin", "Lisinopril"]
        return data

    def _calculate_age(self, birth_date_str: str) -> int:
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
            today = datetime.today().date()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except Exception as e:
            logger.error(f"Error calculating age from {birth_date_str}: {e}")
            return 0

    def _build_prompt(self, user_query: str, patient_data: dict,
                      context_summary: str, guidelines: dict) -> str:
        system_message = (
            "You are a clinically accurate medical assistant providing personalized advice based on evidence-based guidelines. "
            "Always include this disclaimer at the end: 'This information is for educational purposes only and is not a substitute for professional medical advice.'"
        )
        prompt_lines = [system_message, "\nPatient Data:"]
        for key, value in patient_data.items():
            prompt_lines.append(f"- {key}: {value}")
        prompt_lines.append("\nEvidence-Based Guidelines:")
        if guidelines:
            for condition, rec in guidelines.items():
                prompt_lines.append(f"- {condition}: {rec}")
        else:
            prompt_lines.append("- None available")
        prompt_lines.append("\nConversation Context Summary:")
        prompt_lines.append(context_summary if context_summary else "No significant context.")
        prompt_lines.append("\nUser Query:")
        prompt_lines.append(user_query)
        return "\n".join(prompt_lines)

    def _ensure_disclaimer(self, advice_text: str) -> str:
        disclaimer = "This information is for educational purposes only and is not a substitute for professional medical advice."
        if disclaimer.lower() not in advice_text.lower():
            advice_text += "\n\n" + disclaimer
        return advice_text

# ------------------------------------------------------------------------------
# Stand-Alone Async Script Entry Point for Testing
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    async def main():
        gpt_client = AsyncGPT4Client(api_key=settings.OPENAI_API_KEY)
        advice_service = PersonalizedMedicalAdviceService(gpt_client)
        example_patient_id = "12345"  # Replace with a valid patient ID from your FHIR server
        user_query = "How should I manage my diabetes effectively?"
        advice = await advice_service.get_personalized_advice(example_patient_id, user_query)
        print("Personalized Medical Advice:")
        print(advice)

    asyncio.run(main())
print ("30")