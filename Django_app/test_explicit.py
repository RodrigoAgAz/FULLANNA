import requests
import json

def test_explicit():
    url = "http://localhost:8000/chatbot/chat/"
    headers = {'Content-Type': 'application/json'}
    data = {'user_id': 'test', 'message': 'Hello from test'}
    
    print(f"DEBUG: Sending request to {url}")
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response content: {response.text}")
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    result = test_explicit()
    print(f"Result: {result}")