# X-API-Key Quick Reference

## Getting Started (5 min)

### 1. Create an API Key

1. Sign in to the Asset Library: https://cms.itqan.dev
2. Open account settings → **API Keys**
3. Click **Create API Key**
4. Name it (e.g., `my-app-mobile`) and save
5. **Copy the key** (shown only once!)

Example key:
```
itq_abc123def456ghi789jkl012mno345pqr
```

### 2. Make Your First Request

#### JavaScript (Browser)

```javascript
const apiKey = 'itq_abc123...';  // Your API key

fetch('https://api.itqan.dev/recitations/', {
  headers: { 'X-API-Key': apiKey }
})
  .then(res => res.json())
  .then(data => console.log(data));
```

#### Python

```python
import requests

api_key = 'itq_abc123...'  # Your API key

response = requests.get(
    'https://api.itqan.dev/recitations/',
    headers={'X-API-Key': api_key}
)

print(response.json())
```

#### cURL

```bash
curl \
  -H 'X-API-Key: itq_abc123...' \
  https://api.itqan.dev/recitations/
```

---

## Common Tasks

### Authenticate an API Request

Add the header to every request:

```
X-API-Key: itq_abc123...
```

### Handle Authentication Errors

**Invalid key:**
```json
{
  "error_name": "authentication_error",
  "message": "Invalid API key."
}
```

**Expired key:**
```json
{
  "error_name": "authentication_error",
  "message": "API key has expired."
}
```

**Solution:** Create a new API key.

### Make Cross-Origin Requests (Browser)

No special setup needed. The API supports CORS:

```javascript
// Works from http://localhost:3000
fetch('https://api.itqan.dev/recitations/', {
  headers: { 'X-API-Key': apiKey }
})
```

### Rotate Your API Key

1. Create a new API key (keep the new one secret during transition)
2. Update your app to use the new key
3. Revoke the old key in the Asset Library

---

## Best Practices

### ✓ Do

- ✓ Create one API key per app/environment
- ✓ Store the key in environment variables
- ✓ Monitor your API usage in the dashboard
- ✓ Rotate keys periodically (e.g., yearly)
- ✓ Use the same key across multiple requests (no need to regenerate)

### ✗ Don't

- ✗ Commit API keys to version control
- ✗ Share API keys between apps
- ✗ Regenerate the key on every request (expensive)
- ✗ Log or display the raw key in user interfaces
- ✗ Use the same key for development and production

---

## Environment Setup

### Node.js + Express

```javascript
// .env
API_KEY=itq_abc123...

// app.js
require('dotenv').config();

const apiKey = process.env.API_KEY;

app.get('/api/recitations', async (req, res) => {
  const response = await fetch('https://api.itqan.dev/recitations/', {
    headers: { 'X-API-Key': apiKey }
  });
  const data = await response.json();
  res.json(data);
});
```

### React

```jsx
// App.jsx
import { useEffect, useState } from 'react';

const API_KEY = import.meta.env.VITE_API_KEY;

function Recitations() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch('https://api.itqan.dev/recitations/', {
      headers: { 'X-API-Key': API_KEY }
    })
      .then(res => res.json())
      .then(setData);
  }, []);

  return <div>{/* render data */}</div>;
}

export default Recitations;
```

### Python + Flask

```python
# .env
API_KEY=itq_abc123...

# app.py
import os
import requests
from flask import Flask

app = Flask(__name__)
api_key = os.getenv('API_KEY')

@app.route('/recitations')
def recitations():
    response = requests.get(
        'https://api.itqan.dev/recitations/',
        headers={'X-API-Key': api_key}
    )
    return response.json()

if __name__ == '__main__':
    app.run()
```

### .env File Format

```bash
# .env (do not commit to git)
API_KEY=itq_abc123...
API_BASE_URL=https://api.itqan.dev
ENVIRONMENT=production
```

### gitignore Entry

```bash
# .gitignore
.env
.env.local
*.key
api_key.txt
```

---

## HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | OK | Success! Data in response body |
| 400 | Bad Request | Invalid request (e.g., bad page number) |
| 401 | Unauthorized | Missing/invalid/expired API key |
| 403 | Forbidden | Authenticated but not allowed (e.g., asset access) |
| 404 | Not Found | Endpoint doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Bug on our side (report it!) |

---

## Rate Limits

API keys have rate limits based on usage tier:

- **Default:** 1,000 requests/hour
- **Pro:** 10,000 requests/hour
- **Enterprise:** Custom limits

**Current usage:** Check the `X-RateLimit-*` response headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1699564800
```

When you hit the limit:
```json
{
  "error_name": "rate_limit_exceeded",
  "message": "API rate limit exceeded. Reset at: 2023-11-10 12:00:00 UTC"
}
```

---

## Troubleshooting

### "API key not found" / 401

**Causes:**
1. Key was never created
2. Key is invalid/typo
3. Key was revoked
4. Key expired

**Check:**
1. Visit https://cms.itqan.dev → API Keys
2. Copy the full key (with prefix)
3. Verify no spaces/typos in your code

### CORS Error (Browser)

```
Access to XMLHttpRequest has been blocked by CORS policy
```

**Causes:**
1. Wrong domain in request
2. Missing X-API-Key header
3. Browser bug (unlikely)

**Check:**
1. Verify `https://api.itqan.dev` is correct
2. Include `X-API-Key` header in request
3. Check browser console for full error

### Requests Working Locally But Not in Production

**Cause:** Different API key or environment

**Check:**
1. Verify production environment has correct `API_KEY` env var
2. Use different keys for dev/prod
3. Check server logs for API errors

### Still Having Issues?

1. **Check the docs:** https://api.itqan.dev/docs/
2. **Check your code:** Enable logging, inspect request/response
3. **Contact support:** https://itqan.dev/support

---

## Code Samples

### Fetch All Recitations

```javascript
async function getRecitations() {
  const response = await fetch('https://api.itqan.dev/recitations/', {
    headers: { 'X-API-Key': apiKey }
  });
  const { results } = await response.json();
  return results;
}
```

### Fetch One Recitation

```javascript
async function getRecitation(id) {
  const response = await fetch(`https://api.itqan.dev/recitations/${id}/`, {
    headers: { 'X-API-Key': apiKey }
  });
  return response.json();
}
```

### Search Recitations

```javascript
async function searchRecitations(query) {
  const url = new URL('https://api.itqan.dev/recitations/');
  url.searchParams.set('search', query);
  
  const response = await fetch(url, {
    headers: { 'X-API-Key': apiKey }
  });
  const { results } = await response.json();
  return results;
}
```

### Paginate Results

```javascript
async function getPage(pageNum = 1, pageSize = 20) {
  const url = new URL('https://api.itqan.dev/recitations/');
  url.searchParams.set('page', pageNum);
  url.searchParams.set('page_size', pageSize);
  
  const response = await fetch(url, {
    headers: { 'X-API-Key': apiKey }
  });
  return response.json();
}
```

---

## Need Help?

- **API Docs:** https://api.itqan.dev/docs/
- **Getting Started:** https://docs.itqan.dev/api/
- **Support:** https://itqan.dev/support
- **Issues:** https://github.com/fanar-io/itqan-cms/issues
