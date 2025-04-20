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
from chatbot.views.services.session import get_session

async def test_query(query, user_id="test"):
    """Test a query with ANNA and return the response"""
    print(f"\nQuery: {query}")
    session_data = await get_session(user_id)
    handler = ChatHandler(session_data, query, user_id)
    await handler.initialize()
    result = await handler.handle_message()
    
    # Extract messages from the response
    if isinstance(result, tuple) and len(result) >= 1:
        response = result[0]
    else:
        response = result
        
    if hasattr(response, 'content'):
        content = json.loads(response.content.decode('utf-8'))
        messages = content.get('messages', [])
    else:
        messages = response.get('messages', [])
    
    print("ANNA's response:")
    for msg in messages:
        print(f"- {msg}")
    
    return messages

async def main():
    queries = [
        "What are the symptoms of diabetes?",
        "How do I know if I have high blood pressure?",
        "Can stress cause headaches?",
        "What's the difference between a cold and the flu?",
        "Is it normal to feel tired all the time?",
        "What should I do for a sprained ankle?",
        "Can you explain what cholesterol is?",
        "Should I be worried about chest pain?",
        "What foods are good for heart health?",
        "How much sleep do I need each night?"
    ]
    
    results = []
    
    for query in queries:
        response = await test_query(query)
        results.append({"query": query, "response": response})
        
    # Save results to a file for analysis
    with open('anna_responses.json', 'w') as f:
        json.dump(results, f, indent=2)
        
    print("\nAll queries completed. Results saved to anna_responses.json")

if __name__ == "__main__":
    asyncio.run(main())