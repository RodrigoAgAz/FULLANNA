from ..services.medication_service import MedicationReminderService
from .chat_handler import ChatHandler
print ("18")
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
            return self.create_response(
                "Thank you for confirming your medication. Stay healthy!"
            )
        return self.create_response(
            "I'm not sure what you mean. Please reply 'TAKEN' when you've taken your medication."
        )
print ("19")