import requests
import json

def send_message(message, user_id):
    url = "http://localhost:8000/chatbot/chat/"
    headers = {'Content-Type': 'application/json'}
    data = {'message': message, 'user_id': user_id}
    
    print(f"DEBUG: Sending request with data: {data}")
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        print(f"DEBUG: Response status code: {response.status_code}")
        print(f"DEBUG: Response headers: {response.headers}")
        print(f"DEBUG: Response content: {response.text}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Server response status: {e.response.status_code}")
            print(f"Server response text: {e.response.text}")
        return {"error": "Error communicating with the server."}

def main():
    print("Chat with Anna (type 'exit' or 'quit' to stop)")
    user_id = input("Enter your user ID: ").strip()

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ('exit', 'quit'):
            break

        response = send_message(user_input, user_id)
        print(f"Anna: {response}")

if __name__ == "__main__":
    main()