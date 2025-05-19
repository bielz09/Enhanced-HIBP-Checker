"""
Manages secure storage of the HIBP API key using the system keyring.

This file provides functions to set and retrieve the API key, abstracting
the interaction with the `keyring` library.
"""
import keyring
import sys

SERVICE_NAME = "HIBP APP AI"
API_KEY_USERNAME = "hibp_api_key"

def set_api_key(api_key):
    """Securely store the HIBP API key."""
    try:
        keyring.set_password(SERVICE_NAME, API_KEY_USERNAME, api_key)
    except Exception as e:
        # Handle potential keyring errors (such as no backend available).
        # The exception is re-raised for the UI to handle.
        print(f"Error storing API key in keyring: {e}", file=sys.stderr) # Print the error
        raise # Re-raise the exception so the UI can potentially catch it

def get_api_key():
    """Retrieve the stored HIBP API key."""
    try:
        api_key = keyring.get_password(SERVICE_NAME, API_KEY_USERNAME)
        return api_key
    except Exception as e:
        print(f"Error retrieving API key from keyring: {e}", file=sys.stderr) # Print the error
        return None 