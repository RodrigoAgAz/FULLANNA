"""
Simple test script to test the chat endpoint
"""
import requests
import json

def test_chat():
    """Test the chat endpoint"""
    print("Testing chat endpoint...")
    
    url = "http://localhost:8000/chatbot/chat/"
    headers = {"Content-Type": "application/json"}
    data = {
        "user_id": "test_user",
        "message": "Hello, this is a test message"
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_chat()