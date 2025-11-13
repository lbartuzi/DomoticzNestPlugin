# Nest SDM Plugin for Domoticz

A robust Python plugin for integrating Google Nest devices with Domoticz home automation system using the Smart Device Management (SDM) API.

## 🌟 Features

- **Automatic token management** with refresh and rotation handling
- **Persistent token storage** with backup recovery
- **Connection retry logic** with exponential backoff
- **Comprehensive error handling** and recovery
- **Support for multiple Nest devices**:
  - Nest Thermostats (temperature control & monitoring)
  - Temperature sensors
  - Humidity sensors
- **Diagnostic tools** for troubleshooting connection issues
- **HTTP Basic Auth support** for protected Domoticz instances

## 📋 Prerequisites

- Domoticz home automation system (version 2020.1 or later)
- Python 3.7 or higher
- Google Nest device(s) activated with a Google account
- US$5 for Google Device Access registration (one-time fee)
- A Google Cloud Project with OAuth 2.0 credentials

## 🚀 Quick Start Guide

### Step 1: Register for Google Device Access

1. Go to the [Device Access Console](https://console.nest.google.com/device-access/)
2. Accept the Terms of Service
3. Pay the one-time US$5 registration fee
4. Note: You must use a consumer Google Account (e.g., gmail.com) - Google Workspace accounts are not supported

### Step 2: Set up Google Cloud Platform

1. **Enable the Smart Device Management API**:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Use the "Enable the API and get an OAuth 2.0 Client ID" button or manually enable the Smart Device Management API
   - Create a new project or select an existing one

2. **Create OAuth 2.0 Credentials**:
   - Go to APIs & Services > Credentials
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Web application" and add the following redirect URIs:
     - `https://www.google.com`
     - `https://www.getpostman.com/oauth2/callback`
     - `http://localhost:8080/`
     - `https://where your domoticz runs if exposed.com`
   - Save your Client ID and Client Secret

### Step 3: Create Device Access Project

1. Return to the [Device Access Console](https://console.nest.google.com/device-access/)
2. Click "Create project"
3. Enter a project name and your OAuth 2.0 Client ID
4. Initially leave "Enable events" unchecked (can be enabled later)
5. Save your Project ID (UUID format like `32c4c2bc-fe0d-461b-b51c-f3885afff2f0`)

### Step 4: Authorize Your Account

1. **Get Authorization Code**:
   Open this URL in your browser (replace with your values):
   ```
   https://nestservices.google.com/partnerconnections/YOUR_PROJECT_ID/auth?
   redirect_uri=https://www.google.com&
   client_id=YOUR_CLIENT_ID&
   access_type=offline&
   prompt=consent&
   response_type=code&
   scope=https://www.googleapis.com/auth/sdm.service
   ```

2. **Get Initial Tokens**:
   Use the included `nest_token_manager.py` script:
   ```bash
   python3 nest_token_manager.py
   # Select option 1: Get new authorization
   # Paste the authorization code when prompted
   ```

### Step 5: Install the Plugin

1. **Clone this repository**:
   ```bash
   cd ~/domoticz/plugins
   git clone https://github.com/yourusername/nest-sdm-domoticz.git Nest
   cd Nest
   ```

2. **Install Python dependencies**:
   ```bash
   pip3 install requests psutil
   ```

3. **Set up configuration**:
   Create `client_secrets.json`:
   ```json
   {
     "web": {
       "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
       "client_secret": "YOUR_CLIENT_SECRET",
       "redirect_uris": ["http://localhost:8080/"]
     }
   }
   ```

4. **Restart Domoticz**:
   ```bash
   sudo systemctl restart domoticz
   ```

### Step 6: Configure in Domoticz

1. Go to Setup > Hardware in Domoticz
2. Add new hardware:
   - Name: `Nest Thermostat` (or your preference)
   - Type: `Google Nest SDM Plugin`
   - Fill in:
     - Client ID: Your OAuth Client ID
     - Client Secret: Your OAuth Client Secret
     - Refresh Token: Token from Step 4
     - Enterprise ID: Numbers only from your Project ID
     - Auth Username/Password: (Only if Domoticz uses Basic Auth)
3. Click "Add"

## 🛠️ Utility Scripts

### nest_token_manager.py
Interactive tool for token management:
- Initial OAuth authorization
- Token refresh
- API connection testing
- Token display

Usage:
```bash
python3 nest_token_manager.py
```

### nest_connection_monitor.py
Diagnostic tool for connection issues:
- DNS resolution testing
- SSL/TLS verification
- Token validity checking
- Continuous monitoring mode
- Transport endpoint error diagnosis

Usage:
```bash
python3 nest_connection_monitor.py
```

## 🔧 Troubleshooting

### Common Issues

#### "Transport endpoint is not connected" Error
This typically indicates network connectivity issues. Run diagnostics:
```bash
python3 nest_connection_monitor.py
# Select option 3: Diagnose transport endpoint error
```

Common solutions:
- Restart Domoticz: `sudo systemctl restart domoticz`
- Check network connectivity: `ping smartdevicemanagement.googleapis.com`
- Increase file descriptor limits: `ulimit -n 4096`

#### Token Expired
The plugin should handle this automatically, but if issues persist:
```bash
python3 nest_token_manager.py
# Select option 2: Refresh existing token
```

#### Invalid Grant Error
Your refresh token has expired or been revoked. Re-authorize:
```bash
python3 nest_token_manager.py
# Select option 1: Get new authorization
```

### Debug Logging

Enable debug logging in Domoticz:
1. Go to Setup > Settings > Other
2. Set "Debug log level" to "Normal + Status + Error + Debug"
3. Check logs at: `/var/log/domoticz/domoticz.log`

## 📁 File Structure

```
Nest/
├── plugin.py                    # Main plugin file
├── nest_token_manager.py        # Token management utility
├── nest_connection_monitor.py   # Connection diagnostic tool
├── client_secrets.json          # OAuth credentials (create this)
├── nest_tokens.json            # Token storage (auto-created)
└── README.md                   # This file
```

## 🔒 Security Notes

- **Never commit credentials** to version control
- Add these files to `.gitignore`:
  - `client_secrets.json`
  - `client_id.json`
  - `nest_tokens.json`
  - `*.pickle`
- Access tokens expire after 1 hour and are automatically refreshed
- Refresh tokens should be used within 6 months to prevent expiration

## 📚 API Documentation

- [Google Nest Device Access Documentation](https://developers.google.com/nest/device-access)
- [Smart Device Management API Reference](https://developers.google.com/nest/device-access/api)
- [Authorization Guide](https://developers.google.com/nest/device-access/authorize)
- [Supported Devices](https://developers.google.com/nest/device-access/supported-devices)

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test your changes thoroughly
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This is an unofficial plugin and is not affiliated with, endorsed by, or connected to Google or Nest. Use at your own risk.

## 🙏 Acknowledgments

- Domoticz community for the plugin framework
- Google Nest team for the SDM API
- Contributors and testers

## 💬 Support

- **Issues**: Please use the [GitHub Issues](https://github.com/yourusername/nest-sdm-domoticz/issues) page
- **Domoticz Forum**: [Third Party Integrations](https://www.domoticz.com/forum/)
- **Google Support**: [Nest Device Access Support](https://developers.google.com/nest/device-access/support)

## 📈 Version History

### v2.0.0 (Current)
- Improved token refresh mechanism
- Added persistent token storage
- Enhanced error handling and recovery
- Added diagnostic tools
- Better connection retry logic

### v1.0.4
- Initial release
- Basic Nest thermostat integration
- OAuth2 authentication

---

**Note**: The Device Access registration fee is US$5 per account and is non-refundable. Each Google Account can create up to 3 Device Access projects.

For commercial use, you'll need to apply for [Commercial Development](https://developers.google.com/nest/device-access/commercial) which includes additional requirements and assessments.
