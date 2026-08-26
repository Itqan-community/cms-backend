# CORS and X-API-Key for Browser Clients

## What is CORS?

**CORS** (Cross-Origin Resource Sharing) is a security mechanism that allows browsers to make requests to servers on different domains.

Without CORS, this fails:
```javascript
// Page on localhost:3000 tries to access api.example.com
// Browser blocks it for security
fetch('https://api.example.com/data')  // ❌ BLOCKED
```

With CORS (and proper configuration), it works:
```javascript
fetch('https://api.example.com/data')  // ✓ ALLOWED
```

---

## Browser Preflight Request

When your browser makes a **cross-origin request with custom headers** (like `X-API-Key`), it first sends an invisible `OPTIONS` request to ask permission.

### What Happens Behind the Scenes

```
1. Browser sees you're making a cross-origin request with custom headers
   ↓
2. Browser sends preflight request (invisible to you):
   
   OPTIONS /recitations/
   Origin: http://localhost:3000
   Access-Control-Request-Method: GET
   Access-Control-Request-Headers: x-api-key
   
   ↓
3. Server responds with permission (or denies):
   
   200 OK
   Access-Control-Allow-Origin: http://localhost:3000
   Access-Control-Allow-Methods: GET, POST, PUT, DELETE
   Access-Control-Allow-Headers: x-api-key, content-type, ...
   
   ↓
4. Browser grants permission (if 200 OK)
   ↓
5. Browser sends your actual request:
   
   GET /recitations/
   Origin: http://localhost:3000
   X-API-Key: itq_abc123...
   
   ↓
6. Server responds with data
```

---

## Itqan API CORS Configuration

### What's Allowed

| Setting | Value |
|---------|-------|
| **Allowed Origins** | See [#allowed-domains](#allowed-domains) |
| **Allowed Headers** | `x-api-key`, `content-type`, `authorization`, and [others](#all-allowed-headers) |
| **Allowed Methods** | `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS` |
| **Credentials** | Yes (cookies, auth headers) |
| **Preflight Cache** | 3,600 seconds (1 hour) |

### Allowed Domains

**Development:**
- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `http://localhost:4200`
- `http://127.0.0.1:4200`

**Production:** Check with your admin or set via environment variable `CORS_ALLOWED_ORIGINS`.

### All Allowed Headers

```
accept
accept-encoding
authorization
baggage
content-type
dnt
origin
sentry-trace
user-agent
x-api-key           ← Your API key
x-csrftoken
x-requested-with
x-tenant
x-session-token
x-email-verification-key
x-password-reset-key
```

---

## Browser Examples

### Simple GET with API Key

```javascript
// ✓ Works: Simple GET request
fetch('https://api.itqan.dev/recitations/', {
  headers: { 'X-API-Key': 'itq_abc123...' }
})
```

**Preflight sent?** No (simple request)

---

### GET with Headers

```javascript
// ✓ Works: GET with custom header (preflight sent)
fetch('https://api.itqan.dev/recitations/', {
  method: 'GET',
  headers: { 'X-API-Key': 'itq_abc123...' }
})
```

**Preflight sent?** Yes (custom header `X-API-Key`)

**Preflight response should include:**
```
Access-Control-Allow-Headers: x-api-key, ...
```

---

### POST with JSON

```javascript
// ✓ Works: POST with JSON and API key
fetch('https://api.itqan.dev/recitations/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'itq_abc123...'
  },
  body: JSON.stringify({ name: 'New Recitation' })
})
```

**Preflight sent?** Yes (POST method + custom headers)

---

## Common CORS Errors & Solutions

### Error: "No 'Access-Control-Allow-Origin' Header"

```
Access to XMLHttpRequest at 'https://api.itqan.dev/recitations/' from origin 
'http://localhost:3000' has been blocked by CORS policy: Response to preflight 
request doesn't pass access control check: No 'Access-Control-Allow-Origin' header 
is present on the requested resource.
```

**Cause:** Server preflight response missing `Access-Control-Allow-Origin` header

**Solution:**
1. Verify your domain is in `CORS_ALLOWED_ORIGINS`
2. Check your `Origin` header matches exactly (scheme, host, port)
3. Contact admin if domain should be allowed

### Error: "Header X-API-Key is Not Allowed"

```
Access to XMLHttpRequest at 'https://api.itqan.dev/recitations/' from origin 
'http://localhost:3000' has been blocked by CORS policy: Request header field 
x-api-key is not allowed by Access-Control-Allow-Headers.
```

**Cause:** Server preflight response doesn't include `x-api-key` in allowed headers

**Solution:**
1. Verify API is properly configured (should include `x-api-key`)
2. Check the preflight response headers
3. Contact admin if this persists

### Error: "Method POST is Not Allowed"

```
Access to XMLHttpRequest at 'https://api.itqan.dev/recitations/' from origin 
'http://localhost:3000' has been blocked by CORS policy: Request method POST 
is not allowed by Access-Control-Allow-Methods.
```

**Cause:** Server doesn't allow POST method for this endpoint

**Solution:**
1. Check endpoint docs — does it support POST?
2. Use correct method (GET, POST, PUT, etc.)
3. Contact admin if method should be supported

---

## Testing CORS Locally

### Method 1: cURL (No CORS on Server Side)

cURL ignores browser CORS rules (useful for debugging):

```bash
curl -H 'X-API-Key: itq_abc123...' https://api.itqan.dev/recitations/
```

If this works but browser fails → CORS misconfiguration

### Method 2: Browser DevTools

1. Open DevTools (F12)
2. Go to **Network** tab
3. Make a request
4. Click on the request
5. Go to **Response Headers** tab
6. Look for `Access-Control-Allow-*` headers

**Expected headers:**
```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, ...
Access-Control-Allow-Headers: x-api-key, ...
```

### Method 3: Preflight Request

1. Open DevTools (F12)
2. Go to **Network** tab
3. Make a request
4. You should see an `OPTIONS` request before your actual request
5. Click on the `OPTIONS` request
6. Check **Request Headers** and **Response Headers**

---

## Local Development Setup

### Node + Express

```javascript
// server.js
const express = require('express');
const cors = require('cors');

const app = express();

app.use(cors({
  origin: 'http://localhost:3000',
  credentials: true
}));

app.get('/recitations', async (req, res) => {
  const response = await fetch('https://api.itqan.dev/recitations/', {
    headers: { 'X-API-Key': process.env.API_KEY }
  });
  const data = await response.json();
  res.json(data);
});

app.listen(3001);
```

Then make requests to your local proxy:
```javascript
fetch('http://localhost:3001/recitations')
```

### React Development Server

React's dev server (`react-scripts start`) already handles CORS forwarding via `package.json`:

```json
{
  "proxy": "https://api.itqan.dev"
}
```

Then:
```javascript
fetch('/recitations/', {
  headers: { 'X-API-Key': apiKey }
})
```

This requests `https://api.itqan.dev/recitations/` transparently!

---

## Production Considerations

### SSL/HTTPS

Always use HTTPS in production:

```javascript
// ✓ Production (HTTPS)
fetch('https://api.itqan.dev/recitations/', {
  headers: { 'X-API-Key': apiKey }
})

// ✗ Development only (HTTP)
fetch('http://api.itqan.dev/recitations/', {
  headers: { 'X-API-Key': apiKey }
})
```

### CORS Allow List

Add your production domain:

```
CORS_ALLOWED_ORIGINS=https://myapp.com,https://app.mycompany.com
```

### Credentials & Cookies

If your API includes cookies:

```javascript
fetch('https://api.itqan.dev/recitations/', {
  credentials: 'include',  // Include cookies
  headers: { 'X-API-Key': apiKey }
})
```

Server must respond with:
```
Access-Control-Allow-Credentials: true
```

---

## Debugging Checklist

- [ ] Is request URL on different domain than page?
- [ ] Does request use custom headers (like `X-API-Key`)?
- [ ] Is origin (scheme + host + port) in CORS_ALLOWED_ORIGINS?
- [ ] Does preflight response include correct `Access-Control-Allow-*` headers?
- [ ] Is `x-api-key` in `Access-Control-Allow-Headers`?
- [ ] Using HTTPS in production?
- [ ] API key valid and not expired?

---

## Further Reading

- **MDN: CORS:** https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- **MDN: Preflight Request:** https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request
- **django-cors-headers:** https://github.com/adamchainz/django-cors-headers
- **Browser DevTools Network Tab:** https://developer.chrome.com/docs/devtools/network/
