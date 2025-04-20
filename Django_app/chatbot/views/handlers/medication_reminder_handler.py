from ..services.medication_service import MedicationReminderService
from .chat_handler import ChatHandler
import logging

logger = logging.getLogger('chatbot')
logger.debug("Medication reminder handler initialized")
class MedicationReminderHandler(ChatHandler):
    def __init__(self):
        super().__init__()
        self.reminder_service = MedicationReminderService()

    def handle_reminder_response(self, message, session):
        """Handle patient responses to medication reminders."""
        response_text = message.lower().strip()
        patient_id = session.get('patient_id')
        
        if not patient_id:
            return self.create_error_response("Patient not identified")

        success = self.reminder_service.process_reminder_response(
            patient_id, 
            response_text
        )

        if success:
            # Log successful medication adherence confirmation
            from audit.utils import log_event
            log_event(
                actor=patient_id,
                action="medication.adherence_confirmed",
                resource=f"Patient/{patient_id}",
                meta={
                    "response": response_text,
                    "success": True
                }
            )
            
            return self.create_response(
                "Thank you for confirming your medication. Stay healthy!"
            )
        return self.create_response(
            "I'm not sure what you mean. Please reply 'TAKEN' when you've taken your medication."
        )
logger.debug("Medication reminder handler initialization complete")