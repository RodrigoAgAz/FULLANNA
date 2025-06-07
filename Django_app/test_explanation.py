import json
import asyncio
import sys
import os

# Add the Django project to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anna_project.settings')

# Setup Django
import django
django.setup()

# Import the chat handler
from chatbot.views.handlers.chat_handler import ChatHandler
from chatbot.views.services.session import get_session, update_session
from chatbot.views.services.intent_service import detect_intent

async def test_query(query, user_id="test_explanation"):
    """Test a query with ANNA directly and return the response"""
    print(f"\nQuery: {query}")
    
    # Get user session
    session_data = await get_session(user_id)
    
    # Create and initialize the chat handler
    handler = ChatHandler(session_data, query, user_id)
    await handler.initialize()
    
    # Process the message
    result = await handler.handle_message()
    
    # Extract messages from the response
    if isinstance(result, tuple) and len(result) >= 1:
        response = result[0]
        updated_session = result[1]
    else:
        response = result
        updated_session = session_data
        
    if hasattr(response, 'content'):
        content = json.loads(response.content.decode('utf-8'))
        messages = content.get('messages', [])
    else:
        messages = response.get('messages', [])
    
    # Check what intent was detected
    intent_data = await detect_intent(query, {})
    detected_intent = intent_data.get('intent', 'unknown')
    
    print(f"Detected Intent: {detected_intent}")
    print("ANNA's response:")
    for msg in messages:
        print(f"- {msg}")
    
    # Check if current_topic was updated correctly in the session
    if 'current_topic' in updated_session:
        topic_info = updated_session['current_topic']
        print(f"\nSession topic: {topic_info.get('name')} (type: {topic_info.get('type')})")
    
    return {
        "query": query,
        "intent": detected_intent,
        "messages": messages,
        "session_topic": updated_session.get('current_topic')
    }

async def main():
    """Test explanation queries and verify they're handling properly"""
    
    # Test the colonoscopy explanation query that was previously broken
    colonoscopy_result = await test_query("Why do I need a colonoscopy?")
    
    # Test another explanation query to verify broader functionality
    mammogram_result = await test_query("What is a mammogram used for?")
    
    # Test a symptom query to verify it's still handled correctly
    symptom_result = await test_query("I have a headache and fever")
    
    # Compare the session topic types
    explanation_type = colonoscopy_result.get('session_topic', {}).get('type')
    symptom_type = symptom_result.get('session_topic', {}).get('type')
    
    print("\n--- TEST RESULTS ---")
    print(f"Explanation query topic type: {explanation_type}")
    print(f"Symptom query topic type: {symptom_type}")
    
    # Verify success
    if explanation_type == 'explanation' and symptom_type in ['symptom_report', 'issue_report']:
        print("\n✅ SUCCESS: Explanation queries are now correctly identified and handled separately from symptom reports!")
    else:
        print("\n❌ ISSUE: The fix didn't properly distinguish between explanation and symptom queries.")

if __name__ == "__main__":
    asyncio.run(main())