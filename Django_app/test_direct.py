import http.client
import json

def query_anna(message):
    """Send a query to ANNA's API endpoint"""
    conn = http.client.HTTPConnection("localhost", 8000)
    headers = {"Content-type": "application/json"}
    body = json.dumps({"message": message, "user_id": "test"})
    
    conn.request("POST", "/chatbot/chat/", body, headers)
    response = conn.getresponse()
    data = response.read().decode()
    
    try:
        json_data = json.loads(data)
        messages = json_data.get("messages", [])
        print(f"\nQuery: {message}")
        print("Response:")
        for msg in messages:
            print(f"- {msg}")
        return messages
    except:
        print("Error parsing response:", data)
        return []

def main():
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
        response = query_anna(query)
        results.append({"query": query, "response": response})
    
    # Save results to a file
    with open("anna_responses.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nAll queries completed. Results saved to anna_responses.json")

if __name__ == "__main__":
    main()