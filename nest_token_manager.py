#!/usr/bin/env python3
"""
Nest Token Management Utility
Handles initial authorization and token refresh for Google Nest SDM API
"""

import requests
import json
import os
import sys
import time
from datetime import datetime

class NestTokenManager:
    def __init__(self, config_file="client_secrets.json"):
        self.config_file = config_file
        self.token_file = "nest_tokens.json"
        self.load_config()
        
    def load_config(self):
        """Load client configuration"""
        try:
            # Try multiple possible config file names
            config_files = [self.config_file, "client_id.json", "client_secrets.json"]
            config_loaded = False
            
            for cf in config_files:
                if os.path.exists(cf):
                    with open(cf, "r") as f:
                        config = json.load(f)
                        # Handle nested structure
                        if "web" in config:
                            config = config["web"]
                        
                        self.client_id = config.get("client_id")
                        self.client_secret = config.get("client_secret")
                        self.redirect_uri = config.get("redirect_uris", ["http://localhost:8080/"])[0]
                        
                        # Use localhost if available
                        for uri in config.get("redirect_uris", []):
                            if "localhost" in uri:
                                self.redirect_uri = uri
                                break
                        
                        config_loaded = True
                        print(f"✓ Loaded configuration from {cf}")
                        break
            
            if not config_loaded:
                print("✗ No configuration file found!")
                print("Please create client_secrets.json or client_id.json with your OAuth2 credentials")
                sys.exit(1)
                
        except Exception as e:
            print(f"✗ Error loading config: {e}")
            sys.exit(1)
    
    def get_new_tokens(self):
        """Get new tokens through OAuth2 flow"""
        scope = "https://www.googleapis.com/auth/sdm.service"
        
        # Build authorization URL
        auth_url = (
            f"https://accounts.google.com/o/oauth2/auth"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&scope={scope}"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        
        print("\n" + "="*60)
        print("AUTHORIZATION REQUIRED")
        print("="*60)
        print("\n1. Open this URL in your browser:\n")
        print(auth_url)
        print("\n2. Approve the permissions")
        print("3. You'll be redirected to a URL like:")
        print(f"   {self.redirect_uri}?code=YOUR_CODE_HERE")
        print("\n4. Copy the 'code' parameter from that URL")
        print("="*60)
        
        auth_code = input("\nPaste the authorization code here: ").strip()
        
        # Exchange code for tokens
        print("\n⏳ Exchanging authorization code for tokens...")
        
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }
        
        try:
            response = requests.post(token_url, data=payload, timeout=10)
            
            if response.status_code == 200:
                tokens = response.json()
                self.save_tokens(tokens)
                return tokens
            else:
                print(f"\n✗ Token exchange failed:")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"\n✗ Request failed: {e}")
            return None
    
    def refresh_tokens(self, refresh_token=None):
        """Refresh access token using refresh token"""
        if not refresh_token:
            # Try to load from file
            tokens = self.load_tokens()
            if not tokens or "refresh_token" not in tokens:
                print("✗ No refresh token available")
                return None
            refresh_token = tokens["refresh_token"]
        
        print("\n⏳ Refreshing access token...")
        
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            response = requests.post(token_url, data=payload, timeout=10)
            
            if response.status_code == 200:
                new_tokens = response.json()
                # Preserve refresh token if not rotated
                if "refresh_token" not in new_tokens:
                    new_tokens["refresh_token"] = refresh_token
                
                self.save_tokens(new_tokens)
                return new_tokens
            else:
                print(f"\n✗ Token refresh failed:")
                print(f"   Status: {response.status_code}")
                error_data = response.json() if response.headers.get("content-type") == "application/json" else response.text
                print(f"   Error: {error_data}")
                
                if "invalid_grant" in str(error_data):
                    print("\n⚠ Refresh token is invalid or expired!")
                    print("  You need to re-authorize the application.")
                
                return None
                
        except Exception as e:
            print(f"\n✗ Request failed: {e}")
            return None
    
    def save_tokens(self, tokens):
        """Save tokens to file"""
        try:
            tokens["updated_at"] = datetime.now().isoformat()
            tokens["expires_at"] = datetime.fromtimestamp(
                time.time() + tokens.get("expires_in", 3600)
            ).isoformat()
            
            with open(self.token_file, "w") as f:
                json.dump(tokens, f, indent=2)
            
            print(f"\n✓ Tokens saved to {self.token_file}")
            print(f"  Access Token: {tokens.get('access_token', '')[:50]}...")
            if tokens.get("refresh_token"):
                print(f"  Refresh Token: {tokens.get('refresh_token', '')[:50]}...")
            print(f"  Expires at: {tokens['expires_at']}")
            
        except Exception as e:
            print(f"\n✗ Failed to save tokens: {e}")
    
    def load_tokens(self):
        """Load tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"✗ Failed to load tokens: {e}")
        return None
    
    def test_connection(self, enterprise_id=None):
        """Test the connection to Nest API"""
        tokens = self.load_tokens()
        if not tokens:
            print("✗ No tokens found")
            return False
        
        if not enterprise_id:
            enterprise_id = input("\nEnter your Enterprise ID (just the numbers): ").strip()
        
        print("\n⏳ Testing connection to Nest API...")
        
        headers = {
            "Authorization": f"Bearer {tokens.get('access_token')}",
            "Content-Type": "application/json"
        }
        
        url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{enterprise_id}/devices"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                devices = response.json().get("devices", [])
                print(f"\n✓ Connection successful!")
                print(f"  Found {len(devices)} device(s)")
                
                for device in devices:
                    device_type = device.get("type", "").split(".")[-1]
                    print(f"  - {device_type}")
                
                return True
            elif response.status_code == 401:
                print("\n✗ Authentication failed - token may be expired")
                print("  Try refreshing the token (option 2)")
            else:
                print(f"\n✗ API request failed:")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text}")
                
        except Exception as e:
            print(f"\n✗ Connection test failed: {e}")
        
        return False

def main():
    """Main menu"""
    manager = NestTokenManager()
    
    while True:
        print("\n" + "="*60)
        print("NEST TOKEN MANAGEMENT UTILITY")
        print("="*60)
        print("\n1. Get new authorization (first-time setup)")
        print("2. Refresh existing token")
        print("3. Test API connection")
        print("4. Show current tokens")
        print("5. Exit")
        print("\n" + "-"*60)
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            tokens = manager.get_new_tokens()
            if tokens:
                print("\n✓ Authorization successful!")
                print("  Copy the refresh token to your Domoticz plugin settings:")
                print(f"\n  {tokens.get('refresh_token', 'N/A')}\n")
        
        elif choice == "2":
            tokens = manager.refresh_tokens()
            if tokens:
                print("\n✓ Token refresh successful!")
        
        elif choice == "3":
            manager.test_connection()
        
        elif choice == "4":
            tokens = manager.load_tokens()
            if tokens:
                print("\n" + "="*60)
                print("CURRENT TOKENS")
                print("="*60)
                print(f"\nAccess Token: {tokens.get('access_token', 'N/A')[:50]}...")
                print(f"Refresh Token: {tokens.get('refresh_token', 'N/A')[:50]}...")
                print(f"Updated: {tokens.get('updated_at', 'N/A')}")
                print(f"Expires: {tokens.get('expires_at', 'N/A')}")
            else:
                print("\n✗ No tokens found")
        
        elif choice == "5":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("\n✗ Invalid option")

if __name__ == "__main__":
    main()
