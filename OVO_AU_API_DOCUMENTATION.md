# OVO Energy Australia API Documentation

Complete technical documentation for the OVO Energy Australia GraphQL API.

**Reverse-Engineered:** January 2026
**Status:** Unofficial - not endorsed by OVO Energy
**API Version:** Unknown (no versioning detected)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [GraphQL Endpoint](#graphql-endpoint)
4. [Queries](#queries)
5. [Data Structures](#data-structures)
6. [Error Handling](#error-handling)
7. [Rate Limits](#rate-limits)
8. [Examples](#examples)

---

## Overview

### Architecture

OVO Energy Australia uses a **GraphQL API** hosted at `my.ovoenergy.com.au`.

Key differences from OVO UK:
- **GraphQL** (not REST)
- **Auth0** for authentication (not custom OAuth)
- **Different data structures**
- **No public API documentation**

### Base URLs

| Service | URL |
|---------|-----|
| GraphQL API | `https://my.ovoenergy.com.au/graphql` |
| Web App | `https://my.ovoenergy.com.au` |
| Auth0 | `https://login.ovoenergy.com.au` |

### Content Delivery

- **CDN**: CloudFront (Amazon Web Services)
- **Region**: Likely Sydney, Australia (ap-southeast-2)
- **SSL/TLS**: Yes, enforced

---

## Authentication

### Auth0 OAuth 2.0

OVO Australia uses **Auth0** for authentication with OAuth 2.0 + PKCE.

#### Auth0 Configuration

```
Domain:     login.ovoenergy.com.au
Client ID:  5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR
Audience:   Unknown (likely https://api.ovoenergy.com.au)
```

#### Authentication Flow

```
1. POST /usernamepassword/login
   ↓
2. GET /authorize/resume?state=...
   ↓
3. POST /oauth/token
   ↓
4. Redirect to /login/callback
   ↓
5. Final redirect with authorization code
   ↓
6. Exchange code for tokens
```

#### Token Types

| Token | Header | Format | Expiry |
|-------|--------|--------|--------|
| Access Token | `authorization` | `Bearer eyJ...` | 5 minutes |
| ID Token | `myovo-id-token` | `eyJ...` | 5 minutes |
| Refresh Token | N/A | Unknown | Unknown |

#### JWT Token Structure

**Access Token Claims:**
```json
{
  "iss": "https://login.ovoenergy.com.au/",
  "sub": "auth0|68e5088a3d30935999afa84a",
  "aud": "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR",
  "iat": 1737334000,
  "exp": 1737334300,
  "azp": "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR",
  "scope": "openid profile email"
}
```

**ID Token Claims:**
```json
{
  "iss": "https://login.ovoenergy.com.au/",
  "sub": "auth0|68e5088a3d30935999afa84a",
  "aud": "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR",
  "iat": 1737334000,
  "exp": 1737334300,
  "email": "user@example.com",
  "email_verified": true,
  "name": "User Name"
}
```

---

## GraphQL Endpoint

### Request Format

```http
POST /graphql HTTP/1.1
Host: my.ovoenergy.com.au
Content-Type: application/json
authorization: Bearer eyJ...
myovo-id-token: eyJ...
Origin: https://my.ovoenergy.com.au
Referer: https://my.ovoenergy.com.au/usage

{
  "query": "query GetHourlyData($input: GetHourlyDataInput!) { ... }",
  "variables": {
    "input": { ... }
  }
}
```

### Required Headers

| Header | Value | Required |
|--------|-------|----------|
| `Content-Type` | `application/json` | ✅ Yes |
| `authorization` | `Bearer {access_token}` | ✅ Yes |
| `myovo-id-token` | `{id_token}` | ✅ Yes |
| `Origin` | `https://my.ovoenergy.com.au` | ⚠️ Recommended |
| `Referer` | `https://my.ovoenergy.com.au/*` | ⚠️ Recommended |
| `User-Agent` | Any modern browser | ⚠️ Recommended |

### Response Format

```json
{
  "data": {
    "queryName": {
      // Query results
    }
  },
  "errors": [
    {
      "message": "Error description",
      "locations": [{"line": 1, "column": 1}],
      "path": ["queryName"]
    }
  ]
}
```

---

## Queries

### GetHourlyData

Retrieves hourly energy data for a specified date range.

#### Query Definition

```graphql
query GetHourlyData($input: GetHourlyDataInput!) {
  getHourlyData(input: $input) {
    solar {
      periodFrom
      periodTo
      consumption
      readType
      charge {
        amount
        currency
      }
    }
    export {
      periodFrom
      periodTo
      consumption
      readType
      charge {
        amount
        currency
      }
    }
    savings {
      periodFrom
      periodTo
      consumption
      readType
      charge {
        amount
        currency
      }
    }
  }
}
```

#### Input Type

```graphql
input GetHourlyDataInput {
  accountId: String!
  dateRange: DateRangeInput!
}

input DateRangeInput {
  startDate: String!  # Format: "YYYY-MM-DD"
  endDate: String!    # Format: "YYYY-MM-DD"
}
```

#### Variables Example

```json
{
  "input": {
    "accountId": "30264061",
    "dateRange": {
      "startDate": "2026-01-20",
      "endDate": "2026-01-20"
    }
  }
}
```

#### Response Example

```json
{
  "data": {
    "getHourlyData": {
      "solar": [
        {
          "periodFrom": "2026-01-20T00:00:00+11:00",
          "periodTo": "2026-01-20T01:00:00+11:00",
          "consumption": 0.0,
          "readType": "ACTUAL",
          "charge": {
            "amount": 0.0,
            "currency": "AUD"
          }
        },
        {
          "periodFrom": "2026-01-20T06:00:00+11:00",
          "periodTo": "2026-01-20T07:00:00+11:00",
          "consumption": 1.25,
          "readType": "ACTUAL",
          "charge": {
            "amount": 0.35,
            "currency": "AUD"
          }
        }
        // ... more hours
      ],
      "export": [
        // Same structure
      ],
      "savings": [
        // Same structure
      ]
    }
  }
}
```

#### Tested Date Ranges

| Range | Status | Notes |
|-------|--------|-------|
| Same day (today) | ✅ Works | Most recent hour may be incomplete |
| Yesterday | ✅ Works | Complete data |
| Last 7 days | ✅ Works | All data available |
| Last 30 days | ✅ Works | Tested successfully |
| 3+ months historical | ⚠️ Unknown | Not tested |
| Future dates | ❌ Fails | Returns empty arrays |

### Other Queries (Discovered but Not Documented)

The following queries exist in the GraphQL schema but haven't been fully documented:

- `getAccountDetails` - Likely returns account information
- `getBillingHistory` - Likely returns billing statements
- `getDailyData` - Similar to GetHourlyData but daily granularity
- `getMonthlyData` - Monthly aggregated data
- `getCurrentPlan` - Current tariff/plan details
- `getPaymentMethods` - Saved payment methods

**Contribution Welcome:** If you discover and document these queries, please submit a PR!

---

## Data Structures

### HourlyDataPoint

```typescript
interface HourlyDataPoint {
  periodFrom: string;      // ISO 8601 datetime with timezone
  periodTo: string;        // ISO 8601 datetime with timezone
  consumption: number;     // Float, kWh
  readType: ReadType;      // "ACTUAL" | "ESTIMATED"
  charge: Charge | null;   // Optional cost information
}
```

### Charge

```typescript
interface Charge {
  amount: number;    // Float, dollars
  currency: string;  // Always "AUD"
}
```

### ReadType

```typescript
type ReadType = "ACTUAL" | "ESTIMATED";
```

- **ACTUAL**: Real meter reading from smart meter
- **ESTIMATED**: Calculated/interpolated value

### Timezone Handling

All timestamps include timezone offset:
- Format: `2026-01-20T14:30:00+11:00`
- Timezone: Australia/Sydney (AEDT/AEST)
- Offset varies: `+11:00` (AEDT) or `+10:00` (AEST)

**Daylight Saving:**
- AEDT: October - April (+11:00)
- AEST: April - October (+10:00)

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Parse response |
| 400 | Bad Request | Check query syntax |
| 401 | Unauthorized | Refresh tokens |
| 403 | Forbidden | Check headers |
| 429 | Too Many Requests | Implement backoff |
| 500 | Server Error | Retry later |
| 502/503 | Service Unavailable | Retry with backoff |

### GraphQL Errors

```json
{
  "errors": [
    {
      "message": "Variable \"$input\" got invalid value ...",
      "locations": [{"line": 1, "column": 20}],
      "extensions": {
        "code": "BAD_USER_INPUT"
      }
    }
  ]
}
```

#### Common Error Codes

| Code | Cause | Solution |
|------|-------|----------|
| `BAD_USER_INPUT` | Invalid variables | Check input format |
| `UNAUTHENTICATED` | Missing/expired tokens | Re-authenticate |
| `FORBIDDEN` | Insufficient permissions | Check account access |
| `INTERNAL_SERVER_ERROR` | Server issue | Retry later |

### Error Examples

**Invalid Account ID:**
```json
{
  "errors": [{
    "message": "Account not found",
    "extensions": {"code": "NOT_FOUND"}
  }]
}
```

**Invalid Date Format:**
```json
{
  "errors": [{
    "message": "Variable \"$input\" got invalid value \"20-01-2026\" at \"input.dateRange.startDate\"; Expected type \"String\"",
    "extensions": {"code": "BAD_USER_INPUT"}
  }]
}
```

**Expired Tokens:**
```http
HTTP/1.1 401 Unauthorized
```

---

## Rate Limits

### Observed Behavior

- No explicit rate limits detected in responses
- No `X-RateLimit-*` headers observed
- CloudFront CDN may have per-IP limits
- Recommended: Max 100 requests/hour

### Best Practices

```python
import time
from functools import wraps

def rate_limit(min_interval=1):
    """Ensure minimum interval between requests"""
    last_call = [0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result
        return wrapper
    return decorator

@rate_limit(min_interval=1)
def make_request():
    # Your request code
    pass
```

### Retry Strategy

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(requests.RequestException)
)
def make_api_request():
    # Your request code
    pass
```

---

## Examples

### cURL Request

```bash
curl -X POST https://my.ovoenergy.com.au/graphql \
  -H "Content-Type: application/json" \
  -H "authorization: Bearer eyJ..." \
  -H "myovo-id-token: eyJ..." \
  -H "Origin: https://my.ovoenergy.com.au" \
  -d '{
    "query": "query GetHourlyData($input: GetHourlyDataInput!) { getHourlyData(input: $input) { solar { periodFrom consumption } } }",
    "variables": {
      "input": {
        "accountId": "30264061",
        "dateRange": {
          "startDate": "2026-01-20",
          "endDate": "2026-01-20"
        }
      }
    }
  }'
```

### Python with requests

```python
import requests

url = "https://my.ovoenergy.com.au/graphql"

headers = {
    "Content-Type": "application/json",
    "authorization": "Bearer eyJ...",
    "myovo-id-token": "eyJ...",
    "Origin": "https://my.ovoenergy.com.au"
}

query = """
query GetHourlyData($input: GetHourlyDataInput!) {
  getHourlyData(input: $input) {
    solar { periodFrom consumption }
  }
}
"""

variables = {
    "input": {
        "accountId": "30264061",
        "dateRange": {
            "startDate": "2026-01-20",
            "endDate": "2026-01-20"
        }
    }
}

response = requests.post(
    url,
    json={"query": query, "variables": variables},
    headers=headers
)

data = response.json()
print(data)
```

### JavaScript with fetch

```javascript
const url = 'https://my.ovoenergy.com.au/graphql';

const query = `
  query GetHourlyData($input: GetHourlyDataInput!) {
    getHourlyData(input: $input) {
      solar { periodFrom consumption }
    }
  }
`;

const variables = {
  input: {
    accountId: "30264061",
    dateRange: {
      startDate: "2026-01-20",
      endDate: "2026-01-20"
    }
  }
};

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'authorization': 'Bearer eyJ...',
    'myovo-id-token': 'eyJ...',
    'Origin': 'https://my.ovoenergy.com.au'
  },
  body: JSON.stringify({ query, variables })
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## Discovery Process

This API was reverse-engineered using browser DevTools. See `BROWSER_TESTING_GUIDE.md` for detailed methodology.

### Tools Used

- Chrome DevTools (Network tab)
- JWT.io (token inspection)
- GraphQL Playground (query testing)
- Postman (API testing)

### Discoveries Timeline

1. ✅ Identified GraphQL endpoint
2. ✅ Extracted Auth0 configuration
3. ✅ Discovered GetHourlyData query
4. ✅ Documented data structures
5. ⚠️ OAuth flow partially mapped (needs implementation)
6. ❌ Refresh token mechanism not found

---

## Known Limitations

1. **No Official Documentation** - All information is reverse-engineered
2. **Token Expiry** - 5-minute lifespan, no refresh implemented
3. **Incomplete Schema** - Only GetHourlyData fully documented
4. **No Webhooks** - No real-time data push
5. **Solar-Focused** - Primarily tested with solar accounts

---

## Contributing

Help improve this documentation:

1. **Discover new queries** - Use GraphQL introspection
2. **Document data structures** - Add type definitions
3. **Test edge cases** - Try different account types
4. **Implement OAuth** - Complete the authentication flow
5. **Find rate limits** - Test and document

Submit PRs to: https://github.com/HallyAus/OVO_Aus_api

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-20 | 0.1.0 | Initial documentation |

---

## Legal Notice

This is an **unofficial, reverse-engineered API documentation**. It is not endorsed, supported, or affiliated with OVO Energy Australia.

Use at your own risk. The API may change without notice.

---

**Last Updated:** January 20, 2026
**Maintainer:** Community Maintained
**Status:** Active Development
