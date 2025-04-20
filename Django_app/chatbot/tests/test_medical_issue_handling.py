"""
Test the enhanced medical issue handling components.

This module tests the new functionality for handling any medical issue report,
including dynamic SNOMED code resolution and personalized medical advice.
"""

import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

from django.test import TestCase
from django.conf import settings

from chatbot.views.services.personalized_medical_advice_service import (
    PersonalizedMedicalAdviceService, 
    CONDITION_CODE_MAPPING,
    AsyncGPT4Client
)
from chatbot.views.services.intent_service import Intent


class TestResolveConditionCode(TestCase):
    """Test the resolve_condition_code function in PersonalizedMedicalAdviceService."""
    
    def setUp(self):
        """Set up test environment."""
        self.service = PersonalizedMedicalAdviceService()
        # Store original mapping to restore after tests
        self.original_mapping = CONDITION_CODE_MAPPING.copy()
    
    def tearDown(self):
        """Clean up after tests."""
        # Restore original mapping
        global CONDITION_CODE_MAPPING
        CONDITION_CODE_MAPPING = self.original_mapping
    
    @patch('chatbot.views.services.personalized_medical_advice_service.AsyncGPT4Client')
    async def test_existing_mapping(self, mock_gpt):
        """Test resolving a code for a condition that exists in the mapping."""
        # Test with a condition that exists in the mapping
        code = await self.service.resolve_condition_code("back_pain")
        self.assertEqual(code, "161891005")
        # Ensure GPT was not called
        mock_gpt.return_value.chat_completions_create.assert_not_called()
    
    @patch('chatbot.views.services.personalized_medical_advice_service.AsyncGPT4Client')
    async def test_normalized_mapping(self, mock_gpt):
        """Test resolving a code with normalization."""
        # Test with a condition that needs normalization
        code = await self.service.resolve_condition_code("back pain")
        self.assertEqual(code, "161891005")
        # Ensure GPT was not called
        mock_gpt.return_value.chat_completions_create.assert_not_called()
    
    @patch('chatbot.views.services.personalized_medical_advice_service.AsyncGPT4Client')
    async def test_partial_match_mapping(self, mock_gpt):
        """Test resolving a code with partial matching."""
        # Test with a condition that is a partial match
        code = await self.service.resolve_condition_code("severe back pain")
        self.assertEqual(code, "161891005")
        # Ensure GPT was not called
        mock_gpt.return_value.chat_completions_create.assert_not_called()
    
    @patch('chatbot.views.services.personalized_medical_advice_service.AsyncGPT4Client')
    async def test_gpt_mapping(self, mock_gpt):
        """Test resolving a code using GPT for unknown conditions."""
        # Mock GPT response
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(
                content=json.dumps({
                    "snomed_code": "387703003",  # Updated to match actual code
                    "condition_name": "insomnia",
                    "confidence": 0.9,
                    "explanation": "Insomnia is difficulty falling asleep or staying asleep."
                })
            ))
        ]
        mock_gpt.return_value.chat_completions_create.return_value = mock_completion
        
        # Test with a completely new condition
        code = await self.service.resolve_condition_code("insomnia")
        
        # Assert the code returned by GPT was used
        self.assertEqual(code, "387703003")
        
        # Verify it was added to the mapping
        self.assertIn("insomnia", CONDITION_CODE_MAPPING)
        self.assertEqual(CONDITION_CODE_MAPPING["insomnia"], "387703003")
    
    @patch('chatbot.views.services.personalized_medical_advice_service.AsyncGPT4Client')
    async def test_gpt_low_confidence(self, mock_gpt):
        """Test handling low confidence GPT mappings."""
        # Mock low confidence GPT response
        mock_completion = AsyncMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(
                content=json.dumps({
                    "snomed_code": "98765432",
                    "condition_name": "unknown_condition",
                    "confidence": 0.4,
                    "explanation": "No clear mapping found."
                })
            ))
        ]
        mock_gpt.return_value.chat_completions_create.return_value = mock_completion
        
        # Test with a completely unknown condition
        code = await self.service.resolve_condition_code("extremely rare condition xyz")
        
        # Should return None due to low confidence
        self.assertIsNone(code)
        
        # Verify it was NOT added to the mapping
        self.assertNotIn("unknown_condition", CONDITION_CODE_MAPPING)


class TestMedicalIssueEndToEnd(TestCase):
    """Test the end-to-end flow for handling medical issues."""
    
    @patch('chatbot.views.services.personalized_medical_advice_service.AsyncGPT4Client')
    async def test_issue_report_handling(self, mock_gpt):
        """Test the complete flow from issue report to personalized advice."""
        # Mock the keyphrase extraction
        keyphrase_completion = AsyncMock()
        keyphrase_completion.choices = [
            MagicMock(message=MagicMock(
                content=json.dumps({
                    "keyphrase": "neck stiffness",
                    "normalized_term": "cervical strain"
                })
            ))
        ]
        
        # Mock the SNOMED code resolution
        code_completion = AsyncMock()
        code_completion.choices = [
            MagicMock(message=MagicMock(
                content=json.dumps({
                    "snomed_code": "209565000",
                    "condition_name": "cervical strain",
                    "confidence": 0.9,
                    "explanation": "Cervical strain is a neck injury."
                })
            ))
        ]
        
        # Mock the relevant history detection
        history_completion = AsyncMock()
        history_completion.choices = [
            MagicMock(message=MagicMock(
                content=json.dumps({
                    "relevant_history": ["high blood pressure", "migraine"]
                })
            ))
        ]
        
        # Set up the mock to return different responses for different calls
        mock_gpt.return_value.chat_completions_create.side_effect = [
            keyphrase_completion,
            code_completion,
            history_completion
        ]
        
        # Create an instance of the service with mock dependencies
        service = PersonalizedMedicalAdviceService()
        
        # Mock any actual HTTP calls to MedlinePlus
        with patch('httpx.AsyncClient') as mock_client:
            # Set up the mock client to return a 404 to force using the fallback
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            # Set up test data
            message = "I'm having neck stiffness that won't go away"
            patient_data = {"id": "test-patient", "name": [{"given": ["Test"]}]}
            additional_data = {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "condition1",
                            "clinicalStatus": {"coding": [{"code": "active"}]},
                            "code": {"text": "High blood pressure"}
                        }
                    },
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "condition2",
                            "clinicalStatus": {"coding": [{"code": "active"}]},
                            "code": {"text": "Migraine"}
                        }
                    }
                ]
            }
            context_info = {"intent": "issue_report"}
            
            # Call the handle_symptom_query method with our test inputs
            result = await service.handle_symptom_query(
                message, 
                patient_data,
                topic=None,  # Will trigger keyphrase extraction
                additional_data=additional_data,
                conversation_context=context_info
            )
            
            # Verify result
            self.assertIn("messages", result)
            self.assertGreater(len(result["messages"]), 0)
            
            # Check for personalized note about relevant history
            history_note = next((msg for msg in result["messages"] if "⚠️ Note:" in msg), None)
            self.assertIsNotNone(history_note)
            self.assertIn("history of high blood pressure and migraine", history_note)
            
            # Check that we have the fallback generic advice
            advice_found = False
            for msg in result["messages"]:
                if "Rest and avoid exacerbating activities" in msg:
                    advice_found = True
                    break
            self.assertTrue(advice_found)
            
            # Check for the standard disclaimer
            from chatbot.views.utils.response_formatter import STANDARD_DISCLAIMER
            disclaimer_found = False
            for msg in result["messages"]:
                if STANDARD_DISCLAIMER in msg:
                    disclaimer_found = True
                    break
            self.assertTrue(disclaimer_found)


# Run tests when executed directly
if __name__ == '__main__':
    unittest.main()