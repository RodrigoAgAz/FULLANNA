import requests
import json
import argparse

def send_message(message, user_id, verbose=False):
    url = "http://localhost:8000/chatbot/chat/"
    headers = {'Content-Type': 'application/json'}
    data = {'message': message, 'user_id': user_id}
    
    if verbose:
        print(f"DEBUG: Sending request with data: {data}")
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        
        if verbose:
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response headers: {response.headers}")
            print(f"DEBUG: Response content: {response.text}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        if hasattr(e, 'response') and e.response is not None and verbose:
            print(f"Server response status: {e.response.status_code}")
            print(f"Server response text: {e.response.text}")
        return {"error": "Error communicating with the server."}

def format_response(response):
    """Format the response for clean output"""
    if 'messages' in response:
        return '\n'.join(response['messages'])
    elif 'error' in response:
        return f"Error: {response['error']}"
    else:
        return str(response)

def main():
    parser = argparse.ArgumentParser(description='ANNA Healthcare Chatbot Client')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose debug output')
    parser.add_argument('--user', '-u', type=str, default='test', help='User ID for the session')
    args = parser.parse_args()
    
    print("Chat with ANNA Healthcare Assistant (type 'exit' or 'quit' to stop)")
    user_id = args.user

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ('exit', 'quit'):
            break

        response = send_message(user_input, user_id, args.verbose)
        print(f"\nAnna: {format_response(response)}")

if __name__ == "__main__":
    main()