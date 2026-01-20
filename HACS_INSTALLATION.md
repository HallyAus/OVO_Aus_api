# HACS Installation Guide - OVO Energy Australia

This guide shows you how to install OVO Energy Australia integration using HACS (Home Assistant Community Store).

## Prerequisites

- Home Assistant 2024.1.0 or newer
- HACS installed ([Installation Guide](https://hacs.xyz/docs/setup/download))
- OVO Energy Australia account

---

## Installation Methods

Choose one of these methods:

### Method 1: HACS (Recommended) ⭐

Easiest method with automatic updates.

### Method 2: Auto Install Script

One-command installation.

### Method 3: Manual Installation

For advanced users.

---

## Method 1: HACS Installation (Recommended)

### Step 1: Add Custom Repository

1. **Open HACS** in Home Assistant
   - Go to HACS in the sidebar

2. **Add Custom Repository**
   - Click the **3 dots** (⋮) in the top right corner
   - Select **"Custom repositories"**

3. **Add Repository Details**
   - **Repository:** `https://github.com/HallyAus/OVO_Aus_api`
   - **Category:** `Integration`
   - Click **"Add"**

### Step 2: Install Integration

1. **Search for Integration**
   - In HACS, search for **"OVO Energy Australia"**

2. **Download**
   - Click on **"OVO Energy Australia"**
   - Click **"Download"**
   - Select the latest version
   - Click **"Download"** again

3. **Restart Home Assistant**
   - Go to **Settings → System → Restart**

### Step 3: Get Authentication Tokens

**You need to extract tokens from the OVO website:**

1. **Open Browser** (Chrome/Edge recommended)
   - Go to https://my.ovoenergy.com.au

2. **Open DevTools**
   - Press **F12** (or Right-click → Inspect)
   - Go to **Network** tab

3. **Log in to OVO**
   - Enter your credentials
   - Click **"Usage"** in the menu

4. **Extract Tokens**
   - In Network tab, type **"graphql"** in the filter box
   - Click on any **graphql** request
   - Go to **Headers** tab
   - Find and copy:
     - `authorization` header → **access_token** (includes "Bearer ")
     - `myovo-id-token` header → **id_token**

5. **Get Account ID**
   - In the same request, go to **Payload** tab
   - Find `accountId` in the variables
   - Copy the number (e.g., "30264061")

**Example tokens:**
```
access_token: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5q...
id_token: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5qSTBO...
account_id: 30264061
```

### Step 4: Configure Integration

**Option A: configuration.yaml (Simple)**

Edit your `configuration.yaml`:

```yaml
ovo_energy_au:
  access_token: "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5q..."
  id_token: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5qSTBO..."
  account_id: "30264061"
```

**Option B: secrets.yaml (Recommended - More Secure)**

Edit `secrets.yaml`:

```yaml
ovo_access_token: "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5q..."
ovo_id_token: "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5qSTBO..."
ovo_account_id: "30264061"
```

Edit `configuration.yaml`:

```yaml
ovo_energy_au:
  access_token: !secret ovo_access_token
  id_token: !secret ovo_id_token
  account_id: !secret ovo_account_id
```

### Step 5: Restart Again

- Go to **Settings → System → Restart**

### Step 6: Verify Sensors

1. **Go to Developer Tools**
   - Settings → Developer Tools → States

2. **Check for Sensors**
   - Filter by "ovo_energy"
   - You should see 5 sensors

**Available Sensors:**
- `sensor.ovo_energy_solar_generation_current_hour`
- `sensor.ovo_energy_grid_export_current_hour`
- `sensor.ovo_energy_solar_generation_today`
- `sensor.ovo_energy_grid_export_today`
- `sensor.ovo_energy_cost_savings_today`

---

## Method 2: Auto Install Script

### Linux/macOS

```bash
# Download and run install script
wget https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/claude/create-github-project-rWeUP/install.sh
chmod +x install.sh
./install.sh
```

Or one-liner:

```bash
bash <(curl -s https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/claude/create-github-project-rWeUP/install.sh)
```

### Windows PowerShell

```powershell
# Run as Administrator
iwr https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/claude/create-github-project-rWeUP/install.ps1 -UseBasicParsing | iex
```

### Docker/Home Assistant OS

```bash
# SSH into your Home Assistant
# Run:
wget -O - https://raw.githubusercontent.com/HallyAus/OVO_Aus_api/claude/create-github-project-rWeUP/install.sh | bash
```

The script will:
1. Auto-detect your Home Assistant config directory
2. Create `custom_components` directory if needed
3. Download and install the integration
4. Show you next steps for configuration

---

## Method 3: Manual Installation

### Git Clone Method

```bash
# Clone repository
cd /config/custom_components
git clone https://github.com/HallyAus/OVO_Aus_api.git temp
mv temp/custom_components/ovo_energy_au ./
rm -rf temp
```

### Manual Download Method

1. Download: https://github.com/HallyAus/OVO_Aus_api/archive/refs/heads/claude/create-github-project-rWeUP.zip
2. Unzip the file
3. Copy `custom_components/ovo_energy_au` to your HA config's `custom_components` folder
4. Restart Home Assistant

---

## Updating the Integration

### Via HACS (Automatic)

1. Go to HACS → Integrations
2. Find "OVO Energy Australia"
3. If update available, click "Update"
4. Restart Home Assistant

### Via Install Script

```bash
# Re-run the install script
./install.sh
# Choose option 1 (Clone from GitHub)
```

### Manual Update

```bash
cd /config/custom_components
rm -rf ovo_energy_au
# Then reinstall using Method 3
```

---

## Token Management

### ⚠️ Important: Token Expiry

**Tokens expire after 5 minutes!**

You'll need to update them periodically until OAuth is integrated into the HA component.

### Create Update Alert Automation

Add this to automatically notify when tokens expire:

```yaml
automation:
  - alias: "OVO Tokens Expired"
    trigger:
      - platform: state
        entity_id: sensor.ovo_energy_solar_generation_today
        to: "unavailable"
        for:
          minutes: 1
    action:
      - service: notify.persistent_notification
        data:
          title: "OVO Energy Tokens Expired"
          message: "Update tokens in configuration.yaml and restart HA"
```

### Quick Token Update Process

1. Extract fresh tokens from browser (see Step 3 above)
2. Update `secrets.yaml` or `configuration.yaml`
3. Restart Home Assistant
4. Sensors should become available again

---

## Troubleshooting

### HACS Shows "Repository structure is not compliant"

**Solution:** Make sure you're using the latest version of HACS and the repository URL is correct.

### Integration Not Showing in HACS

**Solution:**
1. Make sure you added it as a custom repository
2. Check category is set to "Integration"
3. Reload HACS: Settings → System → Reload HACS

### Sensors Show "Unavailable"

**Check 1: Token Format**
```yaml
# ✅ Correct
access_token: "Bearer eyJhbGc..."  # Must include "Bearer "
id_token: "eyJhbGc..."              # No "Bearer "

# ❌ Wrong
access_token: "eyJhbGc..."         # Missing "Bearer "
```

**Check 2: Tokens Expired**
- Extract fresh tokens from browser
- Update configuration
- Restart HA

**Check 3: Logs**
```
Settings → System → Logs
Filter: "ovo"
```

### Component Not Loading

**Check Installation:**
```bash
ls /config/custom_components/ovo_energy_au/
# Should show: __init__.py, manifest.json, sensor.py, etc.
```

**Check manifest.json is valid:**
```bash
cat /config/custom_components/ovo_energy_au/manifest.json
```

### Install Script Fails

**Linux/macOS:**
```bash
# Make sure you have permissions
sudo ./install.sh

# Or specify config directory manually
HA_CONFIG=/path/to/config ./install.sh
```

**Windows:**
```powershell
# Run PowerShell as Administrator
# If execution policy error:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Uninstalling

### Via HACS

1. Go to HACS → Integrations
2. Find "OVO Energy Australia"
3. Click **⋮** → **Remove**
4. Remove configuration from `configuration.yaml`
5. Restart Home Assistant

### Manual

```bash
rm -rf /config/custom_components/ovo_energy_au
```

Remove from `configuration.yaml` and restart.

---

## Getting Help

- 📖 **Documentation:** [Main README](https://github.com/HallyAus/OVO_Aus_api)
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/HallyAus/OVO_Aus_api/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/HallyAus/OVO_Aus_api/discussions)
- 📚 **HACS Docs:** [hacs.xyz](https://hacs.xyz)

---

## What's Next?

After installation, check out:

- [Home Assistant Dashboard Examples](home_assistant_example/README.md#example-dashboard)
- [Python Client with OAuth](README.md#usage-examples)
- [API Documentation](OVO_AU_API_DOCUMENTATION.md)

---

**Made with ☀️ for the Australian solar community**
