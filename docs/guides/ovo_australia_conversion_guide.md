# OVO UK vs OVO Australia API - Conversion Guide

This guide explains the differences between OVO UK and OVO Australia APIs, and how to adapt existing OVO UK integrations for the Australian market.

**Target Audience:** Developers with existing OVO UK integrations

---

## Quick Comparison

| Feature | OVO UK | OVO Australia |
|---------|---------|---------------|
| **API Type** | REST | GraphQL |
| **Authentication** | Custom OAuth 2.0 | Auth0 OAuth 2.0 |
| **Base URL** | `https://smartpaym.ovoenergy.com` | `https://my.ovoenergy.com.au` |
| **Token Format** | Single JWT | Dual JWT (access + ID) |
| **Token Lifespan** | ~1 hour | ~5 minutes |
| **Data Format** | JSON (REST endpoints) | JSON (GraphQL) |
| **Timezone** | GMT/BST | AEST/AEDT |
| **Currency** | GBP | AUD |
| **Public Docs** | Limited | None (reverse-engineered) |

---

## Architecture Differences

### API Protocol

**OVO UK (REST):**
```http
GET /api/v1/usage/daily
```

**OVO Australia (GraphQL):**
```http
POST /graphql
Body: {"query": "...", "variables": {...}}
```

**Migration Impact:** Complete rewrite required. Cannot simply change base URLs.

### Authentication

**OVO UK:**
```python
# Single OAuth token
headers = {
    "Authorization": f"Bearer {access_token}"
}
```

**OVO Australia:**
```python
# Dual tokens required
headers = {
    "authorization": f"Bearer {access_token}",
    "myovo-id-token": id_token
}
```

**Migration Impact:**
- Must handle two tokens instead of one
- Token refresh logic needs updating
- Shorter token lifespan (5 min vs 60 min)

---

## Authentication Comparison

### OVO UK OAuth Flow

```
1. GET /oauth/authorize
2. User logs in
3. Redirect with code
4. POST /oauth/token (exchange code for token)
5. Receive single access_token
```

**Token Refresh (UK):**
```http
POST /oauth/token
grant_type=refresh_token
refresh_token={refresh_token}
```

### OVO Australia OAuth Flow

```
1. POST /usernamepassword/login (Auth0)
2. GET /authorize/resume?state=...
3. POST /oauth/token
4. Redirect to /login/callback
5. Receive access_token + id_token + refresh_token
```

**Token Refresh (Australia):**
```
⚠️ NOT YET IMPLEMENTED
Mechanism exists but not documented
```

---

## Data Structure Comparison

### Daily Usage Data

**OVO UK:**
```json
GET /api/v1/usage/daily?from=2026-01-01&to=2026-01-31

{
  "data": [
    {
      "date": "2026-01-01",
      "consumption": 12.5,
      "cost": 3.25,
      "unit": "kWh"
    }
  ]
}
```

**OVO Australia:**
```json
POST /graphql
{
  "query": "query GetHourlyData($input: GetHourlyDataInput!) { ... }",
  "variables": {
    "input": {
      "accountId": "30264061",
      "dateRange": {"startDate": "2026-01-01", "endDate": "2026-01-31"}
    }
  }
}

Response:
{
  "data": {
    "getHourlyData": {
      "solar": [
        {
          "periodFrom": "2026-01-01T00:00:00+11:00",
          "periodTo": "2026-01-01T01:00:00+11:00",
          "consumption": 0.5,
          "readType": "ACTUAL",
          "charge": {"amount": 0.12, "currency": "AUD"}
        }
      ]
    }
  }
}
```

**Key Differences:**
- ✅ UK: Daily granularity by default
- ⚠️ Australia: Hourly granularity (must aggregate for daily)
- ✅ UK: Simple array of objects
- ⚠️ Australia: Nested structure with multiple data types (solar/export/savings)

---

## Code Migration Examples

### Before: OVO UK

```python
import requests

class OVOEnergyUK:
    BASE_URL = "https://smartpaym.ovoenergy.com"

    def __init__(self, access_token):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def get_daily_usage(self, start_date, end_date):
        url = f"{self.BASE_URL}/api/v1/usage/daily"
        params = {"from": start_date, "to": end_date}
        response = self.session.get(url, params=params)
        return response.json()

# Usage
client = OVOEnergyUK(access_token="...")
data = client.get_daily_usage("2026-01-01", "2026-01-31")
for day in data["data"]:
    print(f"{day['date']}: {day['consumption']} kWh")
```

### After: OVO Australia

```python
import requests
from datetime import datetime

class OVOEnergyAU:
    API_URL = "https://my.ovoenergy.com.au/graphql"

    def __init__(self, access_token, id_token, account_id):
        self.access_token = access_token
        self.id_token = id_token
        self.account_id = account_id
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "authorization": access_token,  # Already includes "Bearer "
            "myovo-id-token": id_token
        })

    def get_daily_usage(self, start_date, end_date):
        query = """
        query GetHourlyData($input: GetHourlyDataInput!) {
          getHourlyData(input: $input) {
            solar { consumption }
          }
        }
        """
        variables = {
            "input": {
                "accountId": self.account_id,
                "dateRange": {
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d")
                }
            }
        }
        response = self.session.post(
            self.API_URL,
            json={"query": query, "variables": variables}
        )
        hourly_data = response.json()["data"]["getHourlyData"]["solar"]

        # Aggregate hourly to daily
        return self._aggregate_to_daily(hourly_data)

    def _aggregate_to_daily(self, hourly_data):
        daily = {}
        for hour in hourly_data:
            date = hour["periodFrom"][:10]  # Extract date from ISO string
            daily[date] = daily.get(date, 0) + hour["consumption"]
        return daily

# Usage
client = OVOEnergyAU(
    access_token="Bearer ...",
    id_token="...",
    account_id="30264061"
)
data = client.get_daily_usage(
    datetime(2026, 1, 1),
    datetime(2026, 1, 31)
)
for date, consumption in data.items():
    print(f"{date}: {consumption:.2f} kWh")
```

---

## Feature Mapping

### Common Features

| Feature | UK Endpoint | AU GraphQL Query | Status |
|---------|-------------|------------------|--------|
| Daily Usage | `GET /usage/daily` | `GetHourlyData` (aggregate) | ✅ Available |
| Account Info | `GET /account` | `getAccountDetails` (?) | ⚠️ Not documented |
| Billing History | `GET /billing` | `getBillingHistory` (?) | ⚠️ Not documented |
| Current Plan | `GET /plan` | `getCurrentPlan` (?) | ⚠️ Not documented |

### UK-Only Features

| Feature | Notes |
|---------|-------|
| Half-hourly data | AU has hourly (closer granularity unavailable) |
| Gas usage | AU doesn't serve gas markets |
| Payment methods API | Unknown if available in AU |

### AU-Only Features

| Feature | Notes |
|---------|-------|
| Solar generation | Separate data stream (`solar`) |
| Grid export | Separate data stream (`export`) |
| Cost savings | Separate data stream (`savings`) |

---

## GraphQL Primer for REST Developers

### Query Structure

**REST (UK):**
```http
GET /api/v1/resource?param1=value1&param2=value2
```

**GraphQL (AU):**
```graphql
query QueryName($input: InputType!) {
  queryName(input: $input) {
    field1
    field2
  }
}

Variables:
{
  "input": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

### Requesting Specific Fields

**REST:** Returns all fields (or use `?fields=...` if supported)

**GraphQL:** Request only needed fields
```graphql
{
  getHourlyData(input: $input) {
    solar {
      consumption  # Only request consumption, ignore timestamps
    }
  }
}
```

**Benefit:** Smaller payloads, faster responses

### Error Handling

**REST:**
```json
HTTP 400
{
  "error": "Invalid parameter",
  "message": "Date format must be YYYY-MM-DD"
}
```

**GraphQL:**
```json
HTTP 200
{
  "data": null,
  "errors": [
    {
      "message": "Invalid date format",
      "path": ["getHourlyData"],
      "extensions": {"code": "BAD_USER_INPUT"}
    }
  ]
}
```

**Note:** GraphQL always returns 200 (even on errors). Check `errors` array.

---

## Migration Checklist

### 1. Authentication

- [ ] Update OAuth flow to Auth0
- [ ] Handle two tokens (access + ID)
- [ ] Implement 5-minute token refresh
- [ ] Test token expiry handling

### 2. API Client

- [ ] Replace REST calls with GraphQL
- [ ] Update request method (GET → POST)
- [ ] Change payload structure
- [ ] Update headers (add `myovo-id-token`)

### 3. Data Handling

- [ ] Adjust for hourly granularity
- [ ] Implement daily aggregation if needed
- [ ] Handle timezone differences (AEST/AEDT vs GMT/BST)
- [ ] Update currency (GBP → AUD)

### 4. Error Handling

- [ ] Check `errors` array in responses
- [ ] Handle GraphQL-specific errors
- [ ] Update retry logic for shorter token lifespan

### 5. Testing

- [ ] Test with Australian account
- [ ] Verify date range queries
- [ ] Test token refresh
- [ ] Validate data accuracy

---

## Common Pitfalls

### 1. Forgetting ID Token

**Error:**
```json
{
  "errors": [{
    "message": "Unauthorized",
    "extensions": {"code": "UNAUTHENTICATED"}
  }]
}
```

**Cause:** Missing `myovo-id-token` header

**Fix:**
```python
headers["myovo-id-token"] = id_token
```

### 2. Wrong Date Format

**Error:**
```json
{
  "errors": [{
    "message": "Variable \"$input\" got invalid value ...",
    "extensions": {"code": "BAD_USER_INPUT"}
  }]
}
```

**Cause:** Date not in `YYYY-MM-DD` format

**Fix:**
```python
date.strftime("%Y-%m-%d")  # Not "%d/%m/%Y" or other formats
```

### 3. Not Checking GraphQL Errors

**Pitfall:**
```python
response = requests.post(...)
data = response.json()["data"]  # May be None!
```

**Fix:**
```python
result = response.json()
if "errors" in result:
    raise APIError(result["errors"])
data = result.get("data")
if data is None:
    raise APIError("No data returned")
```

### 4. Timezone Issues

**Pitfall:**
```python
# Assuming UTC
timestamp = datetime.fromisoformat(period_from)
```

**Fix:**
```python
# Parse with timezone
from dateutil import parser
timestamp = parser.isoparse(period_from)
# Result: 2026-01-20T14:00:00+11:00 (aware datetime)
```

---

## Home Assistant Integration Differences

### OVO UK Integration

```yaml
# Uses built-in integration
ovo_energy:
  username: your@email.com
  password: your_password
```

### OVO Australia Integration

```yaml
# Requires custom component
ovo_energy_au:
  access_token: "Bearer eyJ..."
  id_token: "eyJ..."
  account_id: "30264061"
```

**Migration Notes:**
- UK integration is official (in HA core)
- AU integration is custom (manual installation)
- AU requires manual token extraction (temporary)

---

## Libraries and Tools

### OVO UK

**Available Libraries:**
- `ovoenergy` (Python, unofficial)
- Various Node.js packages

**Home Assistant:**
- Built-in integration

### OVO Australia

**Available Libraries:**
- ❌ None (yet)
- ✅ This repository provides first implementation

**Home Assistant:**
- ✅ Custom component in this repo

---

## Performance Comparison

| Metric | OVO UK | OVO Australia |
|--------|---------|---------------|
| **Avg Response Time** | ~200ms | ~300ms |
| **Payload Size** | Smaller (REST) | Larger (GraphQL overhead) |
| **Request Flexibility** | Fixed endpoints | Custom queries |
| **Bandwidth** | Higher (all fields) | Lower (select fields) |

---

## Future Considerations

### If OVO Australia Adds REST API

**Unlikely:** GraphQL is their chosen architecture
**Impact:** This guide becomes obsolete
**Action:** Monitor OVO developer communications

### If OVO UK Switches to GraphQL

**Likelihood:** Medium
**Impact:** UK/AU APIs become similar
**Benefit:** Unified client possible

---

## Summary

### Biggest Changes

1. **Protocol:** REST → GraphQL
2. **Auth:** Single token → Dual tokens
3. **Granularity:** Daily → Hourly (requires aggregation)
4. **Token Lifespan:** 60 min → 5 min

### Effort Estimate

- **Small Integration:** 4-8 hours (basic data fetching)
- **Medium Integration:** 2-3 days (full features + testing)
- **Large Integration:** 1-2 weeks (HA component, OAuth, etc.)

### Recommended Approach

1. Start with manual tokens (quick prototype)
2. Implement GraphQL queries for needed data
3. Add proper error handling
4. Implement OAuth flow (hardest part)
5. Add token refresh mechanism
6. Thorough testing

---

## Resources

- **OVO UK API Docs:** Limited availability
- **OVO AU API Docs:** This repository
- **GraphQL:** https://graphql.org/learn/
- **Auth0:** https://auth0.com/docs

---

## Getting Help

- **OVO UK Integration Issues:** Official support channels
- **OVO AU Integration Issues:** https://github.com/HallyAus/OVO_Aus_api/issues
- **GraphQL Questions:** Stack Overflow, GraphQL Community
- **Auth0 Questions:** Auth0 Community Forum

---

**Last Updated:** January 20, 2026
**Migration Difficulty:** Medium-High
**Estimated Time:** 2-14 days (depending on scope)
