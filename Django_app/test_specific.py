"""
Test script to verify if new templates are being used for specific medical conditions.
"""

import os
import sys
import json
import asyncio
import http.client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def query_anna(message, user_id="test_specific"):
    """Send a query to ANNA's API endpoint"""
    conn = http.client.HTTPConnection("localhost", 8000)
    headers = {"Content-type": "application/json"}
    body = json.dumps({"message": message, "user_id": user_id})
    
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
    # Test one specific medical condition to see if the template is triggering
    query_anna("What are the symptoms of diabetes?")
    print("\nWaiting 3 seconds before next query...")
    import time
    time.sleep(3)
    
    # Test another condition
    query_anna("What is cholesterol?")

if __name__ == "__main__":
    main()