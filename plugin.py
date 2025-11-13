import Domoticz
import requests
import time
import base64
import threading
import json
from datetime import datetime, timedelta

"""
<plugin key="GoogleNestSDM" name="Google Nest SDM Plugin" author="Lukasz Bartuzi" version="2.0.0" wikilink="">
    <description>
        <h2>Google Nest SDM Plugin v2.0</h2>
        Integrates Google Nest thermostats with Domoticz using the Smart Device Management (SDM) API.
        
        <b>Features:</b>
        • Automatic token refresh with better error handling
        • Persistent token storage
        • Connection retry logic
        • Improved error recovery
        
        <b>Required fields</b><br/>
        • <b>Client ID / Client Secret</b> – from the OAuth2 credentials screen.<br/>
        • <b>Refresh Token</b> – long-lived token received after authorising the app.<br/>
        • <b>Enterprise ID</b> – the numeric part of enterprises/123456 in the SDM dashboard.
        
        <b>Optional fields</b><br/>
        • <b>Auth Username / Auth Password</b> – only if your Domoticz UI is protected by HTTP Basic-Auth. Leave blank otherwise.
    </description>
    <params>
        <param field="Mode1" label="Client ID"         width="350px" required="true"  default=""/>
        <param field="Mode2" label="Client Secret"     width="350px" required="true"  default=""/>
        <param field="Mode3" label="Refresh Token"     width="350px" required="true"  default=""/>
        <param field="Mode4" label="Enterprise ID"     width="200px" required="true"  default=""/>
        <param field="Mode5" label="Auth Username"     width="200px" required="false" default=""/>
        <param field="Mode6" label="Auth Password"     width="200px" required="false" default=""/>
    </params>
</plugin>
"""

class BasePlugin:
    def __init__(self):
        # Google credentials
        self.client_id = ""
        self.client_secret = ""
        self.refresh_token = ""
        self.access_token = ""
        self.token_expiry = 0
        self.enterprise_id = ""
        self.api_url = "https://smartdevicemanagement.googleapis.com/v1/"
        
        # Domoticz state
        self.devices = {}            # SDM path → base unit
        self.unit_to_device_id = {}  # Domoticz unit → SDM path
        
        # Domoticz Basic-Auth
        self.domo_user = None
        self.domo_pass = None
        
        # Polling and retry settings
        self.last_update = 0
        self.update_interval = 30  # Increased from 10 to reduce API calls
        self.retry_count = 0
        self.max_retries = 3
        self.backoff_time = 60  # Seconds to wait before retry
        self.last_error_time = 0
        
        # Token management
        self._token_lock = threading.Lock()
        self.token_refresh_attempts = 0
        self.max_token_refresh_attempts = 3
        self.token_file_path = "nest_tokens.json"
        
        # Connection state
        self.connection_healthy = True
        self.last_successful_update = 0

    def _save_tokens_to_file(self):
        """Save tokens to a local file as backup"""
        try:
            tokens = {
                "refresh_token": self.refresh_token,
                "access_token": self.access_token,
                "token_expiry": self.token_expiry,
                "last_update": datetime.now().isoformat()
            }
            with open(self.token_file_path, 'w') as f:
                json.dump(tokens, f, indent=2)
            Domoticz.Log("Tokens saved to backup file")
        except Exception as e:
            Domoticz.Error(f"Failed to save tokens to file: {e}")

    def _load_tokens_from_file(self):
        """Load tokens from backup file if available"""
        try:
            if os.path.exists(self.token_file_path):
                with open(self.token_file_path, 'r') as f:
                    tokens = json.load(f)
                    if tokens.get("refresh_token"):
                        self.refresh_token = tokens["refresh_token"]
                        Domoticz.Log("Loaded refresh token from backup file")
                        return True
        except Exception as e:
            Domoticz.Error(f"Failed to load tokens from file: {e}")
        return False

    def _urlfetch_with_retry(self, params, max_attempts=3):
        """URL fetch with retry logic"""
        for attempt in range(max_attempts):
            try:
                req = {
                    "url": "http://127.0.0.1:8080/json.htm",
                    "params": params,
                    "timeout": 10
                }
                if self.domo_user and self.domo_pass:
                    token = base64.b64encode(f"{self.domo_user}:{self.domo_pass}".encode()).decode()
                    req["headers"] = {"Authorization": "Basic " + token}
                
                Domoticz.UrlFetch(req)
                return True
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    Domoticz.Error(f"URL fetch failed after {max_attempts} attempts: {e}")
                    return False

    def onStart(self):
        """Initialize plugin"""
        Domoticz.Log("Nest SDM plugin starting (v2.0.0)")
        
        # Read parameters
        self.client_id = Parameters["Mode1"].strip()
        self.client_secret = Parameters["Mode2"].strip()
        self.refresh_token = Parameters["Mode3"].strip()
        self.enterprise_id = Parameters["Mode4"].strip()
        self.domo_user = Parameters["Mode5"].strip() or None
        self.domo_pass = Parameters["Mode6"].strip() or None
        
        # Try to load backup tokens if refresh token is missing
        if not self.refresh_token:
            self._load_tokens_from_file()
        
        # Re-attach existing Domoticz devices
        for unit, dev in Devices.items():
            if dev.DeviceID:
                self.unit_to_device_id[unit] = dev.DeviceID
                self.devices.setdefault(dev.DeviceID, unit)
        
        # Initial token refresh and device discovery
        if self.getAccessToken():
            self.discoverDevices()
        else:
            Domoticz.Error("Failed to get initial access token")

    def getAccessToken(self):
        """Get or refresh access token with improved error handling"""
        with self._token_lock:
            # Check if current token is still valid
            if self.access_token and time.time() < self.token_expiry - 60:
                return True
            
            # Reset token refresh attempts if enough time has passed
            if self.token_refresh_attempts >= self.max_token_refresh_attempts:
                if time.time() - self.last_error_time > 3600:  # Reset after 1 hour
                    self.token_refresh_attempts = 0
                else:
                    Domoticz.Error(f"Max token refresh attempts reached. Waiting...")
                    return False
            
            Domoticz.Log("Refreshing access token...")
            
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
            
            try:
                # Try token refresh with timeout and retry
                for attempt in range(3):
                    try:
                        r = requests.post(
                            "https://oauth2.googleapis.com/token",
                            data=payload,
                            timeout=10,
                            headers={'Content-Type': 'application/x-www-form-urlencoded'}
                        )
                        
                        if r.status_code == 200:
                            break
                        elif r.status_code == 400 and "invalid_grant" in r.text:
                            Domoticz.Error("Refresh token is invalid. Need to re-authenticate.")
                            self.token_refresh_attempts = self.max_token_refresh_attempts
                            return False
                        elif attempt < 2:
                            time.sleep(2 ** attempt)
                            continue
                        
                    except requests.exceptions.RequestException as e:
                        if attempt < 2:
                            time.sleep(2 ** attempt)
                            continue
                        raise e
                
                if r.status_code != 200:
                    Domoticz.Error(f"Token refresh failed with status {r.status_code}: {r.text}")
                    self.token_refresh_attempts += 1
                    self.last_error_time = time.time()
                    return False
                
                # Parse response
                data = r.json()
                self.access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self.token_expiry = time.time() + expires_in
                
                # Handle refresh token rotation
                new_refresh = data.get("refresh_token")
                if new_refresh and new_refresh != self.refresh_token:
                    self.refresh_token = new_refresh
                    Domoticz.Log("Refresh token rotated - saving to hardware settings")
                    
                    # Save to Domoticz hardware settings
                    self._urlfetch_with_retry({
                        "type": "command",
                        "param": "updatehardware",
                        "hid": Parameters["HardwareID"],
                        "data1": self.client_id,
                        "data2": self.client_secret,
                        "data3": self.refresh_token,
                        "data4": self.enterprise_id,
                        "enabled": "true"
                    })
                
                # Save tokens to backup file
                self._save_tokens_to_file()
                
                Domoticz.Log(f"Access token refreshed successfully (expires in {expires_in}s)")
                self.token_refresh_attempts = 0
                self.connection_healthy = True
                return True
                
            except Exception as e:
                Domoticz.Error(f"Token refresh exception: {e}")
                self.token_refresh_attempts += 1
                self.last_error_time = time.time()
                return False

    def _api_request_with_retry(self, method, url, headers, json_data=None, max_retries=3):
        """Make API request with retry logic"""
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = requests.get(url, headers=headers, timeout=10)
                else:
                    response = requests.post(url, headers=headers, json=json_data, timeout=10)
                
                # Check for token expiry
                if response.status_code == 401:
                    Domoticz.Log("Token expired, refreshing...")
                    if self.getAccessToken():
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        continue
                    else:
                        return None
                
                return response
                
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    Domoticz.Log(f"Connection error, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    Domoticz.Error(f"Connection failed after {max_retries} attempts: {e}")
                    self.connection_healthy = False
                    return None
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    Domoticz.Error("Request timeout after retries")
                    return None
            except Exception as e:
                Domoticz.Error(f"Unexpected error in API request: {e}")
                return None
        
        return None

    def discoverDevices(self):
        """Discover and update Nest devices"""
        if not self.getAccessToken():
            return
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.api_url}enterprises/{self.enterprise_id}/devices"
        
        response = self._api_request_with_retry("GET", url, headers)
        if not response:
            return
        
        if response.status_code != 200:
            Domoticz.Error(f"Device list failed {response.status_code}: {response.text}")
            return
        
        try:
            devices_data = response.json()
            
            for device in devices_data.get("devices", []):
                device_id = device["name"]
                traits = device.get("traits", {})
                base_unit = self.devices.get(device_id)
                
                # Create devices if they don't exist
                if base_unit is None:
                    base_unit = len(Devices) + 1
                    self.devices[device_id] = base_unit
                    description = f"Device Path: {device_id}"
                    
                    # Create thermostat setpoint device
                    if "sdm.devices.traits.ThermostatTemperatureSetpoint" in traits:
                        Domoticz.Device(
                            Name="Thermostat Set",
                            Unit=base_unit,
                            Type=242,
                            Subtype=1,
                            Used=1,
                            Description=description,
                            DeviceID=device_id
                        ).Create()
                        self.unit_to_device_id[base_unit] = device_id
                    
                    # Create temperature sensor
                    if "sdm.devices.traits.Temperature" in traits:
                        Domoticz.Device(
                            Name="Temperature",
                            Unit=base_unit + 1,
                            Type=80,
                            Subtype=5,
                            Used=1,
                            Description=description,
                            DeviceID=device_id
                        ).Create()
                        self.unit_to_device_id[base_unit + 1] = device_id
                    
                    # Create humidity sensor
                    if "sdm.devices.traits.Humidity" in traits:
                        Domoticz.Device(
                            Name="Humidity",
                            Unit=base_unit + 2,
                            Type=81,
                            Subtype=1,
                            Used=1,
                            Description=description,
                            DeviceID=device_id
                        ).Create()
                        self.unit_to_device_id[base_unit + 2] = device_id
                
                # Update device values
                if "sdm.devices.traits.ThermostatTemperatureSetpoint" in traits:
                    setpoint = traits["sdm.devices.traits.ThermostatTemperatureSetpoint"].get("heatCelsius", 20.0)
                    if base_unit in Devices:
                        Devices[base_unit].Update(nValue=1, sValue=str(setpoint))
                
                if "sdm.devices.traits.Temperature" in traits:
                    temperature = traits["sdm.devices.traits.Temperature"].get("ambientTemperatureCelsius", 0.0)
                    if (base_unit + 1) in Devices:
                        Devices[base_unit + 1].Update(nValue=1, sValue=str(temperature))
                
                if "sdm.devices.traits.Humidity" in traits:
                    humidity = traits["sdm.devices.traits.Humidity"].get("ambientHumidityPercent", 0)
                    if (base_unit + 2) in Devices:
                        Devices[base_unit + 2].Update(nValue=humidity, sValue=str(humidity))
            
            self.last_successful_update = time.time()
            self.connection_healthy = True
            self.retry_count = 0
            
        except Exception as e:
            Domoticz.Error(f"Error processing device data: {e}")

    def onCommand(self, Unit, Command, Level, Hue):
        """Handle commands from Domoticz"""
        device_id = self.unit_to_device_id.get(Unit)
        if not device_id:
            Domoticz.Error(f"Unknown unit {Unit}")
            return
        
        if not self.getAccessToken():
            Domoticz.Error("Cannot execute command - no valid token")
            return
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        if Command == "Set Level":
            # Validate temperature range
            if Level < 9 or Level > 32:
                Domoticz.Error(f"Temperature {Level}°C out of range (9-32°C)")
                return
            
            payload = {
                "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
                "params": {"heatCelsius": Level}
            }
            
            url = f"{self.api_url}{device_id}:executeCommand"
            
            response = self._api_request_with_retry("POST", url, headers, payload)
            if not response:
                Domoticz.Error("Failed to send command after retries")
                return
            
            if response.status_code == 200:
                Domoticz.Log(f"Temperature set to {Level}°C")
                Devices[Unit].Update(nValue=1, sValue=str(Level))
            else:
                Domoticz.Error(f"SetHeat failed {response.status_code}: {response.text}")

    def onHeartbeat(self):
        """Regular polling with smart backoff"""
        current_time = time.time()
        
        # If connection is unhealthy, use longer intervals
        if not self.connection_healthy:
            if current_time - self.last_error_time < self.backoff_time:
                return
            
        # Check if it's time for an update
        if current_time - self.last_update < self.update_interval:
            return
        
        self.last_update = current_time
        
        # Check token expiry proactively
        if self.token_expiry - current_time < 300:  # Refresh if less than 5 minutes left
            Domoticz.Log("Token expiring soon, refreshing proactively")
            self.getAccessToken()
        
        # Discover and update devices
        self.discoverDevices()

    def onStop(self):
        """Clean shutdown"""
        Domoticz.Log("Nest SDM plugin stopping")
        # Save current tokens before shutdown
        self._save_tokens_to_file()

# Plugin instance
import os
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onStop():
    global _plugin
    _plugin.onStop()
