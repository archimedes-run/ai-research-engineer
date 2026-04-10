#!/usr/bin/env python3
"""
Validate an Anthropic API key by making a test call to the API.
"""

import os
import sys
from anthropic import Anthropic, AuthenticationError, APIError

def validate_api_key():
    """
    Validate the ANTHROPIC_API_KEY environment variable by making a test API call.
    
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    
    # Check if API key exists
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        return False, "❌ ANTHROPIC_API_KEY environment variable not set"
    
    if not api_key.strip():
        return False, "❌ ANTHROPIC_API_KEY is empty"
    
    # Try to make a test API call
    try:
        client = Anthropic(api_key=api_key)
        
        # Make a minimal test call
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": "Say 'hello'"
                }
            ]
        )
        
        return True, f"✅ API key is valid!\n\nTest response: {response.content[0].text}"
    
    except AuthenticationError as e:
        return False, f"❌ Authentication failed: Invalid API key\n   Error: {str(e)}"
    
    except APIError as e:
        return False, f"❌ API error: {str(e)}"
    
    except Exception as e:
        return False, f"❌ Unexpected error: {str(e)}"


if __name__ == "__main__":
    is_valid, message = validate_api_key()
    print(message)
    sys.exit(0 if is_valid else 1)