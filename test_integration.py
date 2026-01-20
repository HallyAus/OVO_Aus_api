#!/usr/bin/env python3
"""
Quick test script to verify OVO Energy Australia API connection
"""

import sys
sys.path.insert(0, 'custom_components/ovo_energy_au')

from ovo_client import OVOEnergyAU

# Replace with your values
ACCESS_TOKEN = "Bearer YOUR_ACCESS_TOKEN_HERE"
ID_TOKEN = "YOUR_ID_TOKEN_HERE"
REFRESH_TOKEN = "YOUR_REFRESH_TOKEN_HERE"  # Optional but recommended
ACCOUNT_ID = "30264061"  # Your account ID

print("=" * 60)
print("OVO Energy Australia API Test")
print("=" * 60)

# Create client
print("\n1. Creating client...")
client = OVOEnergyAU(
    account_id=ACCOUNT_ID,
    refresh_token=REFRESH_TOKEN
)

# Set tokens
print("2. Setting tokens...")
client.set_tokens(ACCESS_TOKEN, ID_TOKEN, REFRESH_TOKEN)

# Test API call
print("3. Fetching today's data...")
try:
    data = client.get_today_data()
    print("✅ SUCCESS! Received data:")
    print(f"   - Solar data points: {len(data.get('solar', []))}")
    print(f"   - Export data points: {len(data.get('export', []))}")
    print(f"   - Savings data points: {len(data.get('savings', []))}")

    # Calculate totals
    solar_total = sum(p.get('consumption', 0) for p in data.get('solar', []))
    export_total = sum(p.get('consumption', 0) for p in data.get('export', []))

    print(f"\n   Solar today: {solar_total:.2f} kWh")
    print(f"   Export today: {export_total:.2f} kWh")

    if solar_total == 0 and export_total == 0:
        print("\n   ⚠️  WARNING: All values are 0")
        print("   This could mean:")
        print("   - It's nighttime (no generation)")
        print("   - Wrong account ID")
        print("   - No solar data available")

except Exception as e:
    print(f"❌ FAILED: {e}")
    print("\nPossible issues:")
    print("- Tokens expired (get fresh ones)")
    print("- Wrong account ID")
    print("- Network issue")

finally:
    client.close()

print("\n" + "=" * 60)
