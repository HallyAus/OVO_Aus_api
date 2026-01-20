# Browser Testing Guide - How We Discovered the API

This guide explains the methodology used to reverse-engineer the OVO Energy Australia API using browser Developer Tools.

**Use Case:** Learn how to discover undocumented APIs for legitimate purposes (personal use, integration, automation).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step-by-Step Discovery Process](#step-by-step-discovery-process)
3. [Analyzing Network Requests](#analyzing-network-requests)
4. [Extracting Authentication](#extracting-authentication)
5. [Testing Queries](#testing-queries)
6. [Advanced Techniques](#advanced-techniques)

---

## Prerequisites

### Tools Needed

- **Modern Web Browser:**
  - Google Chrome (recommended)
  - Microsoft Edge
  - Firefox
  - Safari (with Developer Menu enabled)

- **Optional Tools:**
  - Postman or Insomnia (API testing)
  - JWT.io (token inspection)
  - GraphQL Playground (query testing)

### Skills Required

- Basic understanding of HTTP requests
- Familiarity with JSON
- Basic knowledge of authentication concepts

---

## Step-by-Step Discovery Process

### Phase 1: Initial Reconnaissance

#### 1.1 Open the Target Website

```
URL: https://my.ovoenergy.com.au
```

#### 1.2 Open Browser DevTools

**Chrome/Edge:**
- Press `F12`, OR
- Right-click → "Inspect", OR
- Menu → More Tools → Developer Tools

**Firefox:**
- Press `F12`, OR
- Right-click → "Inspect Element"

**Safari:**
- Enable Developer Menu: Safari → Preferences → Advanced → Show Develop menu
- Press `Cmd+Option+I`

#### 1.3 Navigate to Network Tab

```
DevTools → Network Tab
```

**Pro Tips:**
- Check "Preserve log" to keep requests after page navigation
- Clear existing requests with the 🚫 button for clarity
- Enable "Disable cache" to see all requests

### Phase 2: Capture Authentication Flow

#### 2.1 Clear Network Log

Click the clear button (🚫) to start fresh.

#### 2.2 Log In

1. Enter your OVO credentials
2. Click "Sign In"
3. Watch the Network tab fill with requests

#### 2.3 Identify Authentication Requests

Look for requests to `login.ovoenergy.com.au`:

```
Observed Sequence:
1. POST login.ovoenergy.com.au/usernamepassword/login
2. GET  login.ovoenergy.com.au/authorize/resume?state=...
3. POST login.ovoenergy.com.au/oauth/token
4. GET  my.ovoenergy.com.au/login/callback?code=...
```

**Key Discovery:** Auth0 OAuth 2.0 is used for authentication.

#### 2.4 Extract Client ID

Click on the `/authorize` request:
- Go to "Headers" tab
- Look in "Query String Parameters"
- Find `client_id`: `5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR`

### Phase 3: Discover API Endpoints

#### 3.1 Navigate to Usage Page

After logging in:
- Click "Usage" in the menu
- Wait for data to load
- Observe new requests in Network tab

#### 3.2 Filter for API Calls

In the Network tab filter box, try:
- `graphql` - Found it! 🎉
- `api`
- `v1`
- `json`

**Discovery:** All data requests go to `/graphql` endpoint.

#### 3.3 Examine GraphQL Request

Click on a `graphql` request:

**URL:**
```
POST https://my.ovoenergy.com.au/graphql
```

**Headers Tab:**
```
Content-Type: application/json
authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik...
myovo-id-token: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik5qSTBOa...
Origin: https://my.ovoenergy.com.au
Referer: https://my.ovoenergy.com.au/usage
```

**Payload Tab:**
```json
{
  "query": "query GetHourlyData($input: GetHourlyDataInput!) { getHourlyData(input: $input) { solar { periodFrom periodTo consumption readType charge { amount currency } } export { periodFrom periodTo consumption readType charge { amount currency } } savings { periodFrom periodTo consumption readType charge { amount currency } } } }",
  "variables": {
    "input": {
      "accountId": "30264061",
      "dateRange": {
        "startDate": "2025-12-31",
        "endDate": "2026-02-01"
      }
    }
  }
}
```

**Response Tab:**
```json
{
  "data": {
    "getHourlyData": {
      "solar": [ /* array of hourly data */ ],
      "export": [ /* array of hourly data */ ],
      "savings": [ /* array of hourly data */ ]
    }
  }
}
```

**Key Discoveries:**
- ✅ GraphQL API
- ✅ Requires two JWT tokens (dual-token auth)
- ✅ Account ID is in request variables
- ✅ Query name: `GetHourlyData`

### Phase 4: Extract Tokens

#### 4.1 Copy Access Token

In the `graphql` request:
1. Go to "Headers" tab
2. Scroll to "Request Headers"
3. Find `authorization` header
4. Copy entire value: `Bearer eyJ...`

#### 4.2 Copy ID Token

In the same headers:
1. Find `myovo-id-token` header
2. Copy entire value: `eyJ...`

#### 4.3 Inspect Tokens (Optional)

Go to https://jwt.io and paste tokens to decode:

**Access Token Payload:**
```json
{
  "iss": "https://login.ovoenergy.com.au/",
  "sub": "auth0|68e5088a3d30935999afa84a",
  "aud": "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR",
  "iat": 1737334000,
  "exp": 1737334300,  // ← 5 minutes later!
  "azp": "5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR",
  "scope": "openid profile email"
}
```

**Key Discovery:** Tokens expire after 300 seconds (5 minutes).

#### 4.4 Extract Account ID

In the `graphql` request:
1. Go to "Payload" or "Request" tab
2. Find `variables` → `input` → `accountId`
3. Copy the number (e.g., "30264061")

---

## Analyzing Network Requests

### Request Anatomy

#### Headers to Note

```http
POST /graphql HTTP/1.1
Host: my.ovoenergy.com.au
Content-Type: application/json          ← Required
authorization: Bearer eyJ...             ← Required (JWT access token)
myovo-id-token: eyJ...                   ← Required (JWT ID token)
Origin: https://my.ovoenergy.com.au     ← CORS - Recommended
Referer: https://my.ovoenergy.com.au/usage ← Context - Recommended
User-Agent: Mozilla/5.0...              ← Browser identity
```

**Critical Headers:**
1. `authorization` - Access token with "Bearer " prefix
2. `myovo-id-token` - ID token (no prefix)
3. `Content-Type` - Must be `application/json`

**Optional but Recommended:**
- `Origin` - For CORS
- `Referer` - Provides context
- `User-Agent` - Identifies client

### Payload Structure

```json
{
  "query": "GraphQL query string...",
  "variables": {
    "input": {
      // Query-specific input
    }
  },
  "operationName": "GetHourlyData"  // Optional
}
```

### Response Structure

**Success:**
```json
{
  "data": {
    "queryName": { /* results */ }
  }
}
```

**Error:**
```json
{
  "errors": [
    {
      "message": "Error description",
      "locations": [{"line": 1, "column": 20}],
      "path": ["queryName", "field"]
    }
  ]
}
```

---

## Extracting Authentication

### Method 1: Copy from Network Tab

As shown above - simplest method.

### Method 2: Copy from Application Storage

**Chrome/Edge:**
1. DevTools → Application tab
2. Storage → Local Storage → `https://my.ovoenergy.com.au`
3. Look for keys like `auth_token`, `access_token`, etc.

**Note:** OVO doesn't store tokens in localStorage - only in memory.

### Method 3: Intercept JavaScript

**Console Method:**
```javascript
// In browser console
// (This won't work for OVO since tokens aren't exposed globally)
console.log(window.localStorage);
console.log(window.sessionStorage);
```

### Method 4: Use Copy as cURL

**Quick Token Extraction:**
1. Right-click on `graphql` request in Network tab
2. Select "Copy" → "Copy as cURL (bash)"
3. Paste into text editor
4. Extract tokens from `--header` lines

Example output:
```bash
curl 'https://my.ovoenergy.com.au/graphql' \
  --header 'authorization: Bearer eyJ...' \
  --header 'myovo-id-token: eyJ...' \
  # ... more headers
```

---

## Testing Queries

### Using Postman

#### 1. Create New Request

- Method: `POST`
- URL: `https://my.ovoenergy.com.au/graphql`

#### 2. Add Headers

```
Content-Type: application/json
authorization: Bearer eyJ...
myovo-id-token: eyJ...
```

#### 3. Add Body (raw JSON)

```json
{
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
}
```

#### 4. Send Request

Click "Send" and view response.

### Using cURL

```bash
curl -X POST https://my.ovoenergy.com.au/graphql \
  -H "Content-Type: application/json" \
  -H "authorization: Bearer eyJ..." \
  -H "myovo-id-token: eyJ..." \
  -d '{
    "query": "query GetHourlyData($input: GetHourlyDataInput!) { getHourlyData(input: $input) { solar { consumption } } }",
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

### Using Python

```python
import requests

url = "https://my.ovoenergy.com.au/graphql"
headers = {
    "Content-Type": "application/json",
    "authorization": "Bearer eyJ...",
    "myovo-id-token": "eyJ..."
}
payload = {
    "query": "query GetHourlyData($input: GetHourlyDataInput!) { ... }",
    "variables": {
        "input": {
            "accountId": "30264061",
            "dateRange": {"startDate": "2026-01-20", "endDate": "2026-01-20"}
        }
    }
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

---

## Advanced Techniques

### GraphQL Introspection

**Query the Schema:**
```graphql
{
  __schema {
    queryType {
      name
      fields {
        name
        description
      }
    }
  }
}
```

**Note:** OVO may have introspection disabled. Try it and see!

### Discover Hidden Queries

1. **Method 1: Navigate Every Page**
   - Visit all pages in OVO web app
   - Capture all GraphQL requests
   - Document unique query names

2. **Method 2: Search JavaScript**
   - DevTools → Sources tab
   - Search for "query " in JavaScript files
   - Look for GraphQL query definitions

3. **Method 3: Network Search**
   - Use network tab search (Cmd+F / Ctrl+F)
   - Search for: `"query"`, `"mutation"`, `"subscription"`

### Token Refresh Discovery

**Look for refresh requests:**
```
Filter: /token OR /refresh
```

**Expected pattern:**
```http
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&refresh_token=...
```

**Status:** Not yet found for OVO Australia.

### Modify and Replay Requests

**Chrome/Edge:**
1. Right-click request → "Copy as fetch"
2. Paste in Console
3. Modify variables
4. Press Enter to execute

**Example:**
```javascript
fetch("https://my.ovoenergy.com.au/graphql", {
  headers: {
    "authorization": "Bearer eyJ...",
    "myovo-id-token": "eyJ...",
    "content-type": "application/json"
  },
  body: JSON.stringify({
    query: "...",
    variables: {
      input: {
        accountId: "30264061",
        dateRange: {
          startDate: "2026-01-15",  // ← Modified date
          endDate: "2026-01-20"
        }
      }
    }
  }),
  method: "POST"
})
.then(r => r.json())
.then(console.log);
```

---

## Troubleshooting

### No Requests Showing

**Problem:** Network tab is empty

**Solutions:**
- Ensure "Preserve log" is checked
- Clear and reload page
- Check if filtering is hiding requests

### Can't Find Authorization Headers

**Problem:** No `authorization` header visible

**Solutions:**
- Scroll down in Headers section
- Look under "Request Headers" (not Response Headers)
- Ensure you're looking at the right request

### CORS Errors in Console

**Problem:** When testing from browser console

**Solution:**
- Use Postman/cURL instead
- Or install a CORS browser extension (for testing only)

### 401 Unauthorized

**Problem:** API returns 401

**Causes:**
- Tokens expired (> 5 minutes old)
- Tokens not copied correctly
- Missing "Bearer " prefix on access_token

**Solution:**
- Get fresh tokens
- Verify tokens are complete
- Check header names exactly match

---

## Ethical Considerations

### Legal and Responsible Use

✅ **Acceptable:**
- Personal use for your own account
- Automation for your own data
- Educational purposes
- Creating integrations for personal use

❌ **Not Acceptable:**
- Accessing other users' accounts
- Scraping data at scale
- Commercial use without permission
- Bypassing rate limits maliciously

### Best Practices

1. **Rate Limiting:** Don't hammer the API
2. **Respect ToS:** Check OVO's Terms of Service
3. **Secure Tokens:** Never share or expose your tokens
4. **Attribution:** Credit the discovery process
5. **Reporting Issues:** Report security issues responsibly

---

## Summary

### What We Discovered

1. ✅ OVO Australia uses GraphQL (not REST)
2. ✅ Auth0 OAuth 2.0 for authentication
3. ✅ Dual JWT tokens required (access + ID)
4. ✅ Tokens expire after 5 minutes
5. ✅ Client ID: `5JHnPn71qgV3LmF3I3xX0KvfRBdROVhR`
6. ✅ Main query: `GetHourlyData`
7. ⚠️ Refresh token mechanism not found

### What We Don't Know

1. ❌ How to programmatically get initial tokens (OAuth flow)
2. ❌ How to refresh tokens
3. ❌ Complete GraphQL schema
4. ❌ Rate limits
5. ❌ Other available queries

### Next Steps

- Implement OAuth flow (high priority)
- Discover refresh token mechanism
- Document additional queries
- Test with non-solar accounts

---

## Tools Reference

| Tool | Purpose | URL |
|------|---------|-----|
| Chrome DevTools | Network analysis | Built-in (F12) |
| JWT.io | Token inspection | https://jwt.io |
| Postman | API testing | https://postman.com |
| GraphQL Playground | Query testing | https://github.com/graphql/graphql-playground |
| cURL | Command-line testing | Built-in (Unix) |

---

## Further Reading

- [GraphQL Documentation](https://graphql.org/)
- [Auth0 OAuth 2.0](https://auth0.com/docs/get-started/authentication-and-authorization-flow)
- [JWT Introduction](https://jwt.io/introduction)
- [Chrome DevTools Network Guide](https://developer.chrome.com/docs/devtools/network/)

---

**Last Updated:** January 20, 2026
**Methodology:** Browser DevTools reverse engineering
**Status:** Documented and reproducible
