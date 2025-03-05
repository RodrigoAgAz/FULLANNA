# test_sms.py
from twilio.rest import Client
import os

# Your Twilio Account SID and Auth Token
account_sid = 'your_account_sid'
auth_token = 'your_auth_token'

client = Client(account_sid, auth_token)

message = client.messages.create(
    body="Test message",
    from_='+14243532443',  # Your Twilio number
    to='+393341913506'     # Your UK number
)

print(f"Message SID: {message.sid}")