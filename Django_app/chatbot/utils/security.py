import re
import base64
import os
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def redact_pii(text: str) -> str:
    """
    Redact personally identifiable information (PII) from text
    
    Args:
        text: Raw text that might contain PII
        
    Returns:
        Redacted text with PII replaced by placeholders
    """
    # Phone numbers
    text = re.sub(r'\b\d{10}\b', '[PHONE]', text)
    text = re.sub(r'\b\(\d{3}\)\s*\d{3}[-\s]?\d{4}\b', '[PHONE]', text)
    text = re.sub(r'\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b', '[PHONE]', text)
    
    # Dates
    text = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', '[DATE]', text)
    text = re.sub(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?,? \d{4}\b', '[DATE]', text)
    
    # SSN
    text = re.sub(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', '[SSN]', text)
    
    # Email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Credit card numbers
    text = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[CREDIT_CARD]', text)
    
    # Ages above 90
    text = re.sub(r'\b(9\d|1[0-9]\d) years? old\b', '[AGE]', text)
    
    return text

def get_encryption_key():
    """
    Generate or retrieve the encryption key for message encryption
    Uses settings.SECRET_KEY as the password for the key derivation
    """
    # Use a static salt - in production this should be properly secured
    salt = b'ANNA_salt_for_key_derivation'
    
    # Use the Django secret key as the password
    password = settings.SECRET_KEY.encode()
    
    # Generate a key using PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

def encrypt_message(message: str) -> str:
    """
    Encrypt a message using Fernet symmetric encryption
    
    Args:
        message: The plaintext message to encrypt
        
    Returns:
        Base64-encoded encrypted message
    """
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(message.encode())
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_message(encrypted_message: str) -> str:
    """
    Decrypt a message using Fernet symmetric encryption
    
    Args:
        encrypted_message: Base64-encoded encrypted message
        
    Returns:
        Decrypted plaintext message
    """
    key = get_encryption_key()
    f = Fernet(key)
    decoded = base64.urlsafe_b64decode(encrypted_message)
    decrypted = f.decrypt(decoded)
    return decrypted.decode()