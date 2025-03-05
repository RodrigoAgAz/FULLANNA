# chatbot/views/handlers/symptom_guidance_handler.py
from datetime import datetime
import json
from django.http import JsonResponse
import logging
from ..services.symptom_guidance_service import SymptomGuidanceService
from asgiref.sync import sync_to_async
print ("20")
logger = logging.getLogger('chatbot')

class SymptomGuidanceHandler:
    def __init__(self, session, user_message, user_id):
        self.session = session
        self.user_message = user_message
        self.user_id = user_id
        self.guidance_service = SymptomGuidanceService()
        self.patient = session.get('patient')
        self.patient_id = self.patient.get('id') if self.patient else None
        
    async def handle_symptom_guidance(self):
        """Handle symptom assessment and provide guidance"""
        try:
            logger.info(f"Processing symptom guidance for message: {self.user_message}")
            
            # 1. Check for red flags first - wrap sync method
            has_red_flags, red_flags = await sync_to_async(self.guidance_service.red_flag_checker)(self.user_message)
            
            if has_red_flags:
                logger.warning(f"Red flags detected: {red_flags}")
                emergency_response = await sync_to_async(self.guidance_service.response_formatter)({
                    'level': 'EMERGENCY',
                    'action': 'Seek immediate emergency care',
                    'red_flags': red_flags
                }, self.patient.get('resource') if self.patient else None)
                
                # Additionally provide detailed guidance for red flag cases
                specific_response = await sync_to_async(self.guidance_service.provide_specific_info)(
                    self.user_message,
                    emergency=True
                )
                
                # Combine emergency and specific guidance
                combined_messages = emergency_response['messages'] + specific_response['messages']
                
                return JsonResponse({
                    'messages': combined_messages,
                    'risk_level': 'EMERGENCY'
                })
            
            # 2. Analyze symptoms
            symptom_analysis = await sync_to_async(self.guidance_service.symptom_analyzer)(
                self.user_message,
                self.patient.get('resource') if self.patient else None
            )
            
            # 3. Determine risk level
            risk_assessment = await sync_to_async(self.guidance_service.risk_level_determiner)(
                symptom_analysis,
                red_flags if has_red_flags else None
            )
            
            # 4. Format response
            response = await sync_to_async(self.guidance_service.response_formatter)(
                risk_assessment,
                self.patient.get('resource') if self.patient else None
            )
            
            # 5. Get specific guidance based on symptoms
            specific_info = await sync_to_async(self.guidance_service.provide_specific_info)(
                self.user_message,
                emergency=False
            )
            
            # Combine general guidance with specific information
            response['messages'].extend(specific_info['messages'])
            
            # 6. Log the interaction
            await self._log_guidance_interaction(
                symptom_analysis,
                risk_assessment,
                response
            )
            
            return JsonResponse(response)
            
        except Exception as e:
            logger.error(f"Error in symptom guidance: {str(e)}", exc_info=True)
            return JsonResponse({
                'messages': [
                    "I apologize, but I encountered an error while analyzing your symptoms.",
                    "For your safety, please contact your healthcare provider or emergency services if you're concerned."
                ]
            })
    
    async def _log_guidance_interaction(self, analysis, assessment, response):
        """Log the guidance interaction for audit purposes"""
        try:
            interaction_log = {
                'timestamp': datetime.utcnow().isoformat(),
                'patient_id': self.patient_id,
                'original_message': self.user_message,
                'symptom_analysis': analysis,
                'risk_assessment': assessment,
                'response_given': response,
                'session_id': self.session.get('id')
            }
            
            await sync_to_async(logger.info)(f"Symptom guidance interaction logged: {json.dumps(interaction_log)}")
            
        except Exception as e:
            await sync_to_async(logger.error)(f"Error logging guidance interaction: {str(e)}")
print ("21")