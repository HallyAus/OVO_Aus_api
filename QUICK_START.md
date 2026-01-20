# OVO Energy Australia API - Quick Start Guide

Get started with the OVO Energy Australia Python client in 5 minutes.

**NEW:** OAuth 2.0 authentication is now available! You can log in with just your email and password.

## Prerequisites

- Python 3.11 or higher
- OVO Energy Australia account with active service
- Solar panels (optional, but recommended for full functionality)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/HallyAus/OVO_Aus_api.git
cd OVO_Aus_api
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install requests python-dateutil
```

## Authentication Methods

You have two options for authentication:

1. **OAuth Login (Recommended)** - Log in with email and password
2. **Manual Tokens** - Extract tokens from browser (fallback option)

## Option 1: OAuth Authentication (Recommended)

### Using OAuth Login

```python
from ovo_australia_client import OVOEnergyAU

# Create client
client = OVOEnergyAU()

# Login with email and password
client.authenticate("your.email@example.com", "your_password")

# Set your account ID
client.account_id = "30264061"  # Your account ID

# Start using the API!
data = client.get_today_data()
print(f"Solar today: {sum(p['consumption'] for p in data['solar']):.2f} kWh")

# Tokens refresh automatically every 4 minutes
client.close()
```

**Advantages:**
- ✅ No need to extract tokens manually
- ✅ Automatic token refresh (no 5-minute expiry hassle)
- ✅ Simpler to use
- ✅ More secure (credentials not exposed in code)

**Note:** If OAuth fails (e.g., MFA/2FA enabled), the client will guide you to use manual tokens.

## Option 2: Manual Token Extraction (Fallback)

### Extract Tokens from Browser

Use this method if OAuth authentication doesn't work for your account.

#### Step-by-Step Instructions

1. **Open your browser and go to:**
   ```
   https://my.ovoenergy.com.au
   ```

2. **Open Developer Tools:**
   - Chrome/Edge: Press `F12` or Right-click → Inspect
   - Firefox: Press `F12` or Right-click → Inspect Element
   - Safari: Enable Developer Menu, then press `Cmd+Option+I`

3. **Go to Network Tab:**
   - Click on the "Network" tab in DevTools
   - Keep it open during the next steps

4. **Log in to OVO:**
   - Enter your username and password
   - Complete the login process

5. **Navigate to Usage Page:**
   - Click on "Usage" in the OVO web app menu
   - Wait for the page to load

6. **Find the GraphQL Request:**
   - In the Network tab, type "graphql" in the filter box
   - Click on any `graphql` request in the list
   - Click on the "Headers" tab

7. **Extract the Tokens:**

   **Access Token:**
   - Scroll down to "Request Headers"
   - Find the `authorization` header
   - Copy the ENTIRE value (including "Bearer ")
   - Example: `Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik...`

   **ID Token:**
   - In the same Request Headers section
   - Find the `myovo-id-token` header
   - Copy the entire value (JWT token)
   - Example: `eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5qSTBOa...`

8. **Extract Your Account ID:**
   - Click on the "Payload" or "Request" tab
   - Look for the JSON payload
   - Find `"accountId"` in the variables
   - Copy the number (without quotes)
   - Example: `30264061`

### Visual Guide

```
DevTools → Network Tab → Filter "graphql" → Click request → Headers Tab

Request Headers:
  authorization: Bearer eyJ...    ← Copy this (access_token)
  myovo-id-token: eyJ...          ← Copy this (id_token)

Payload Tab:
  {
    "variables": {
      "input": {
        "accountId": "30264061"   ← Copy this number
      }
    }
  }
```

## Usage

### Quick Test

```bash
python3 ovo_australia_client.py
```

When prompted, paste:
1. Your access token (with "Bearer " prefix)
2. Your ID token
3. Your account ID

You should see today's solar generation and export data.

### Python Script Example

```python
from ovo_australia_client import OVOEnergyAU
from datetime import datetime, timedelta

# Create client
client = OVOEnergyAU(account_id="30264061")

# Set tokens (replace with your actual tokens)
client.set_tokens(
    access_token="Bearer eyJ...",
    id_token="eyJ..."
)

# Get today's data
data = client.get_today_data()

# Display solar generation
for point in data['solar']:
    print(f"{point['periodFrom']}: {point['consumption']} kWh")

# Get yesterday's data
yesterday_data = client.get_yesterday_data()

# Get last 7 days
week_data = client.get_last_7_days()

# Clean up
client.close()
```

### Context Manager Usage

```python
from ovo_australia_client import OVOEnergyAU

with OVOEnergyAU(account_id="30264061") as client:
    client.set_tokens(
        access_token="Bearer eyJ...",
        id_token="eyJ..."
    )

    data = client.get_today_data()
    print(f"Solar today: {sum(p['consumption'] for p in data['solar'])} kWh")
```

## Understanding the Data

### Response Structure

```python
{
  'solar': [
    {
      'periodFrom': '2026-01-20T00:00:00+11:00',
      'periodTo': '2026-01-20T01:00:00+11:00',
      'consumption': 0.45,
      'readType': 'ACTUAL',
      'charge': {
        'amount': 0.12,
        'currency': 'AUD'
      }
    },
    # ... more hours
  ],
  'export': [
    # Same structure as solar
  ],
  'savings': [
    # Same structure
  ]
}
```

### Fields Explained

- **periodFrom/periodTo**: Hour time range (ISO 8601 format)
- **consumption**: Energy in kWh
- **readType**:
  - `ACTUAL` - Real meter reading
  - `ESTIMATED` - Estimated value
- **charge**: Cost/savings information
  - `amount`: Dollar amount
  - `currency`: Always "AUD"

### Example: Calculate Total Solar Today

```python
data = client.get_today_data()
total_solar = sum(point['consumption'] for point in data['solar'])
print(f"Total solar generated today: {total_solar:.2f} kWh")
```

### Example: Find Peak Solar Hour

```python
data = client.get_today_data()
peak = max(data['solar'], key=lambda x: x['consumption'])
print(f"Peak solar: {peak['consumption']} kWh at {peak['periodFrom']}")
```

## Common Issues

### "Not authenticated" Error

**Cause:** Tokens not set or invalid

**Solution:**
```python
# Make sure to set tokens before making API calls
client.set_tokens(access_token="Bearer ...", id_token="...")
```

### "Access tokens expired" Error

**Cause:** Tokens are older than 5 minutes

**Solution:**
- Extract fresh tokens from browser (repeat steps above)
- This is a known limitation until OAuth is implemented

### "Network error" / Timeout

**Cause:**
- No internet connection
- OVO API is down
- Firewall blocking requests

**Solution:**
- Check internet connection
- Try again in a few minutes
- Check OVO website is accessible

### Empty Data Arrays

**Cause:**
- No solar panels on account
- Data not yet available for today
- Wrong account ID

**Solution:**
- Verify you have solar panels
- Try getting yesterday's data instead
- Double-check account ID

## Advanced Usage

### Custom Date Ranges

```python
from datetime import datetime

# Specific date range
start = datetime(2026, 1, 1)
end = datetime(2026, 1, 31)
data = client.get_hourly_data(start, end)
```

### Error Handling

```python
from ovo_australia_client import (
    OVOEnergyAU,
    OVOAuthenticationError,
    OVOAPIError,
    OVOTokenExpiredError
)

try:
    client = OVOEnergyAU(account_id="30264061")
    client.set_tokens(access_token="...", id_token="...")
    data = client.get_today_data()

except OVOTokenExpiredError:
    print("Tokens expired - please get fresh tokens from browser")

except OVOAPIError as e:
    print(f"API error: {e}")

except Exception as e:
    print(f"Unexpected error: {e}")

finally:
    client.close()
```

### Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

client = OVOEnergyAU(account_id="30264061")
# Now you'll see detailed API requests/responses
```

## Next Steps

- **Home Assistant Integration**: See `home_assistant_example/README.md`
- **API Documentation**: See `OVO_AU_API_DOCUMENTATION.md` for complete API reference
- **Browser Testing Guide**: See `BROWSER_TESTING_GUIDE.md` to discover more API endpoints
- **Contribute**: Help implement OAuth flow (see handover document)

## Getting Help

- **GitHub Issues**: https://github.com/HallyAus/OVO_Aus_api/issues
- **API Documentation**: `OVO_AU_API_DOCUMENTATION.md`
- **Home Assistant Help**: `home_assistant_example/README.md`

## Security Warning

⚠️ **Never commit tokens to git!**

```bash
# Add to .gitignore
*.env
config.yaml
tokens.txt
```

Store tokens securely:
- Use environment variables
- Use a password manager
- Never share tokens publicly

## Token Lifespan

| Token Type | Lifespan | Can Refresh? |
|------------|----------|--------------|
| access_token | 5 minutes | ❌ (not yet implemented) |
| id_token | 5 minutes | ❌ (not yet implemented) |
| refresh_token | Unknown | ❌ (not extracted yet) |

**Note:** Automatic token refresh is the #1 priority for future development.

## FAQ

**Q: Do I need solar panels?**
A: No, but the client is optimized for solar accounts. Non-solar accounts may work but haven't been tested.

**Q: How often does data update?**
A: Hourly data is available shortly after each hour ends. Real-time data is not available.

**Q: Can I get data from last year?**
A: Unknown - only tested up to ~3 months. Try it and report back!

**Q: Why GraphQL instead of REST?**
A: OVO Australia uses a different backend than OVO UK. The Australian version uses GraphQL exclusively.

**Q: Will this break when OVO updates their API?**
A: Possibly. This is reverse-engineered and not officially supported. Report issues if it breaks.

## What's Next?

1. **Try the client** with your tokens
2. **Set up Home Assistant integration** (if applicable)
3. **Read the API documentation** to discover more features
4. **Contribute** to the project (OAuth implementation needed!)

Happy solar tracking! ☀️
