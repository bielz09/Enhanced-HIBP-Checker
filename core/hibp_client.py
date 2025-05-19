"""
File for interacting with the Have I Been Pwned (HIBP) API.

This file provides functionality to check for account breaches using the HIBP service.
It requires an API key for access and a user agent as per HIBP's requirements.
"""
import requests
import json

HIBP_API_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{account}"
USER_AGENT = "HIBP_APP_AI (Python)" 

class HibpError(Exception):
    """Custom exception for HIBP API errors."""
    pass

def check_hibp(account: str, api_key: str) -> list:
    """Checks the HIBP API for breaches associated with the given account.

    Args:
        account: The email address or username to check.
        api_key: The HIBP API key.

    Returns:
        A list of breach dictionaries if found, an empty list if no breaches.

    Raises:
        HibpError: If there's an API error (such as rate limiting, invalid key, or if not found).
        requests.exceptions.RequestException: If there's a network-related error.
    """
    if not api_key:
        raise HibpError("HIBP API Key is missing. Please set it in Settings.")
    if not account:
        raise HibpError("Account cannot be empty.")

    headers = {
        "hibp-api-key": api_key,
        "User-Agent": USER_AGENT,
        "format": "json"
    }
    url = HIBP_API_URL.format(account=account)

    try:
        response = requests.get(url, headers=headers, params={'truncateResponse': 'false'}, timeout=30)

        if response.status_code == 200:
            try:
                breaches = response.json()
                return breaches
            except json.JSONDecodeError as e:
                raise HibpError("Failed to decode HIBP API response.")
        elif response.status_code == 404:
            return []
        elif response.status_code == 400:
            raise HibpError(f"Bad Request: Invalid account format? ({response.text})")
        elif response.status_code == 401:
            raise HibpError("Unauthorized: Invalid API Key?")
        elif response.status_code == 403:
            raise HibpError("Forbidden: Check User-Agent header?")
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            raise HibpError(f"Rate Limited. Please wait {retry_after} seconds before trying again.")
        elif response.status_code == 503:
             raise HibpError("Service Unavailable. HIBP might be down or undergoing maintenance.")
        else:
            raise HibpError(f"HIBP API Error: {response.status_code} - {response.text}")

    except requests.exceptions.Timeout:
        raise HibpError("Request to HIBP API timed out.")
    except requests.exceptions.ConnectionError as e:
        raise HibpError(f"Could not connect to HIBP API: {e}")
    except requests.exceptions.RequestException as e:
        raise HibpError(f"An unexpected network error occurred: {e}") 