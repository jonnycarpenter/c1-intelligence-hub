# Logo.dev Integration Guide

Complete guide for implementing Logo.dev API integration correctly across projects.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Pattern](#architecture-pattern)
3. [Backend Implementation](#backend-implementation)
4. [Frontend Implementation](#frontend-implementation)
5. [Deployment & Secrets](#deployment--secrets)
6. [Common Issues & Solutions](#common-issues--solutions)
7. [Testing](#testing)

---

## Overview

Logo.dev provides company logos via their API. This integration uses a **backend proxy pattern** to:
- Keep API tokens secure (never exposed to frontend)
- Add caching headers for performance
- Handle CORS issues
- Provide graceful fallbacks

**API Endpoint**: `https://img.logo.dev/{domain}?token={token}&size={size}&format=png`

---

## Architecture Pattern

```
┌──────────────┐         ┌───────────────┐         ┌──────────────┐
│   Frontend   │────────▶│ Backend Proxy │────────▶│  Logo.dev    │
│  Component   │◀────────│   /api/logo   │◀────────│     API      │
└──────────────┘  image  └───────────────┘  image  └──────────────┘
                  bytes        ▲                    
                               │ LOGO_DEV_TOKEN
                               │ (kept secure)
```

**Key Principles:**
1. Frontend NEVER calls logo.dev directly (CORS + security)
2. Backend proxies requests and injects token
3. Use caching headers to minimize API calls
4. Always provide fallback UI (initials or icon)

---

## Backend Implementation

### Step 1: Environment Configuration

**File:** `backend/app/config/settings.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application settings."""
    
    # Logo.dev API (for company logos)
    logo_dev_token: str = ""
    
    model_config = ConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

# Singleton
settings = Settings()
```

**Environment Variable:**
```bash
LOGO_DEV_TOKEN=your_token_here
```

### Step 2: Logo Service

**File:** `backend/app/services/logo_service.py`

```python
"""Logo.dev Service for Company Logo Fetching"""

import httpx
from typing import Optional
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def extract_domain(url: str) -> str:
    """
    Extract clean domain from URL.
    
    Examples:
        "https://www.gulfstream.com/about" -> "gulfstream.com"
        "compositesone.com" -> "compositesone.com"
        "http://www.example.co.uk/page" -> "example.co.uk"
    """
    if not url:
        return ""
    
    try:
        from urllib.parse import urlparse
        
        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Remove port if present
        domain = domain.split(":")[0]
        
        return domain.lower().strip()
    except Exception as e:
        logger.debug(f"Error extracting domain from {url}: {e}")
        return ""


class LogoService:
    """Service for fetching company logos via Logo.dev."""
    
    def __init__(self):
        self.token = settings.logo_dev_token
        if not self.token:
            logger.warning("LOGO_DEV_TOKEN not found in environment variables")
        else:
            # Log first 10 chars only for security
            logger.info(f"Logo.dev service initialized with token: {self.token[:10]}...")
    
    def get_logo_url(self, domain: str, size: int = 128) -> Optional[str]:
        """
        Get the Logo.dev URL for a domain.
        
        This returns the proxy URL path for the frontend.
        
        Args:
            domain: Company domain (e.g., "gulfstream.com")
            size: Logo size in pixels (default 128)
        
        Returns:
            Logo URL path for the proxy, or None if no domain
        """
        if not domain:
            return None
        
        # Clean the domain
        domain = extract_domain(domain) if "/" in domain else domain.lower().strip()
        
        if not domain:
            return None
        
        # Return the proxy path (frontend will call /api/logo/{domain})
        return f"/api/logo/{domain}"
    
    async def fetch_logo(self, domain: str) -> Optional[bytes]:
        """
        Fetch logo image bytes from Logo.dev.
        
        This is called by the proxy endpoint.
        
        Args:
            domain: Company domain
        
        Returns:
            Image bytes or None if not found
        """
        if not self.token:
            logger.error("Cannot fetch logo: LOGO_DEV_TOKEN not configured")
            return None
        
        if not domain:
            return None
        
        # Construct Logo.dev API URL
        url = f"https://img.logo.dev/{domain}?token={self.token}&size=128&format=png"
        
        # Log without exposing full token
        logger.info(f"Fetching logo from: https://img.logo.dev/{domain}?token=***&size=128&format=png")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                logger.info(f"Logo.dev response for {domain}: status={response.status_code}, content-length={len(response.content)}")
                
                if response.status_code == 200:
                    return response.content
                else:
                    logger.warning(f"Logo.dev returned {response.status_code} for {domain}: {response.text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching logo for {domain}: {e}")
            return None


# Singleton instance
logo_service = LogoService()
```

### Step 3: API Proxy Endpoint

**File:** `backend/app/api/routes/logos.py` (or add to existing routes)

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.services.logo_service import logo_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["logos"])
logger = get_logger(__name__)


@router.get("/logo/{domain}")
async def get_company_logo(domain: str):
    """
    Proxy endpoint for fetching company logos from Logo.dev.
    
    This keeps the API token server-side and adds caching headers.
    
    Args:
        domain: Company domain (e.g., "gulfstream.com")
    
    Returns:
        PNG image of company logo, or 404 if not found
    """
    logger.debug(f"GET /api/logo/{domain}")
    
    try:
        logo_bytes = await logo_service.fetch_logo(domain)
        
        if logo_bytes:
            return Response(
                content=logo_bytes,
                media_type="image/png",
                headers={
                    # Cache logos for 7 days (they rarely change)
                    "Cache-Control": "public, max-age=604800, immutable",
                    "X-Logo-Domain": domain,
                }
            )
        else:
            # Return 404 - frontend will show fallback
            raise HTTPException(status_code=404, detail=f"Logo not found for {domain}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching logo for {domain}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching logo: {str(e)}")
```

**Register the router in your main app:**

```python
# backend/app/main.py
from fastapi import FastAPI
from app.api.routes import logos

app = FastAPI()
app.include_router(logos.router)
```

---

## Frontend Implementation

### Reusable Logo Component

**File:** `frontend/src/components/CompanyLogo.tsx`

```tsx
'use client'

import { useState } from 'react'
import { Building2 } from 'lucide-react'

interface CompanyLogoProps {
  /** Domain (e.g., "gulfstream.com") */
  domain?: string | null
  /** Logo proxy URL from API response (e.g., "/api/logo/gulfstream.com") */
  logoUrl?: string | null
  /** Size in pixels (default 40) */
  size?: number
  /** Additional CSS classes */
  className?: string
}

/**
 * Company logo component with fallback.
 * 
 * Fetches company logos via the backend proxy to keep API tokens secure.
 * Shows a building icon fallback if logo fails to load.
 * 
 * Usage:
 * ```tsx
 * // Using domain directly
 * <CompanyLogo domain="gulfstream.com" size={48} />
 * 
 * // Using logo_url from API response
 * <CompanyLogo logoUrl={company.logo_url} size={48} />
 * ```
 */
export default function CompanyLogo({ 
  domain, 
  logoUrl,
  size = 40, 
  className = ''
}: CompanyLogoProps) {
  const [imgError, setImgError] = useState(false)
  
  // Determine the logo URL to use
  const getLogoUrl = (): string | null => {
    if (logoUrl) {
      // If it's already an absolute URL, use as-is
      if (logoUrl.startsWith('http')) {
        return logoUrl
      }
      // If it's a relative path, use directly (same origin)
      if (logoUrl.startsWith('/')) {
        return logoUrl
      }
    }
    
    if (domain) {
      // Clean the domain and construct proxy URL
      const cleanDomain = domain
        .toLowerCase()
        .replace(/^https?:\/\//, '')
        .replace(/^www\./, '')
        .split('/')[0]
      
      return `/api/logo/${cleanDomain}`
    }
    
    return null
  }
  
  const finalLogoUrl = getLogoUrl()
  
  // Show fallback if no URL or image failed to load
  if (!finalLogoUrl || imgError) {
    return (
      <div 
        className={`bg-gradient-to-br from-slate-100 to-slate-200 rounded-lg flex items-center justify-center ${className}`}
        style={{ width: size, height: size }}
        title={domain || 'Company'}
      >
        <Building2 
          className="text-slate-400" 
          style={{ width: size * 0.5, height: size * 0.5 }}
        />
      </div>
    )
  }
  
  return (
    <img 
      src={finalLogoUrl}
      alt={domain || 'Company logo'}
      className={`rounded-lg object-contain bg-white border border-slate-200 ${className}`}
      style={{ width: size, height: size }}
      onError={() => setImgError(true)}
      loading="lazy"
    />
  )
}
```

### Usage Examples

**Simple usage:**
```tsx
import CompanyLogo from '@/components/CompanyLogo'

function CompanyCard({ company }) {
  return (
    <div className="flex items-center gap-3">
      <CompanyLogo domain={company.domain} size={48} />
      <div>
        <h3>{company.name}</h3>
        <p>{company.description}</p>
      </div>
    </div>
  )
}
```

**With API response:**
```tsx
// If your API returns { name, domain, logo_url }
function CompanyList({ companies }) {
  return (
    <div className="space-y-4">
      {companies.map(company => (
        <div key={company.domain} className="flex items-center gap-3">
          <CompanyLogo logoUrl={company.logo_url} size={40} />
          <span>{company.name}</span>
        </div>
      ))}
    </div>
  )
}
```

**Inline logos with text (initials fallback):**
```tsx
function CompanyBadge({ company }) {
  const [imageError, setImageError] = useState(false)
  
  const logoUrl = company.domain 
    ? `/api/logo/${company.domain}`
    : null

  if (!logoUrl || imageError) {
    // Fallback to initials
    const initials = company.name
      .split(' ')
      .map(w => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase()

    return (
      <div className="inline-flex items-center gap-2">
        <div className="w-5 h-5 rounded bg-slate-200 flex items-center justify-center text-[8px] font-bold text-slate-500">
          {initials}
        </div>
        <span>{company.name}</span>
      </div>
    )
  }

  return (
    <div className="inline-flex items-center gap-2">
      <img
        src={logoUrl}
        alt={company.name}
        className="w-5 h-5 rounded object-contain"
        onError={() => setImageError(true)}
      />
      <span>{company.name}</span>
    </div>
  )
}
```

---

## Deployment & Secrets

### Local Development (.env file)

```bash
# backend/.env
LOGO_DEV_TOKEN=your_logo_dev_token_here
```

### GCP Secret Manager (Production)

**⚠️ CRITICAL: Use `-n` flag with echo to prevent trailing newlines!**

This is the #1 cause of Logo.dev integration failures. Trailing `\r` or `\n` characters will break URL parsing.

```bash
# ✅ CORRECT - No trailing newline
echo -n "your-logo-dev-token" | gcloud secrets create LOGO_DEV_TOKEN \
  --data-file=- \
  --project=your-project-id

# ❌ WRONG - Will add trailing newline
echo "your-logo-dev-token" | gcloud secrets create LOGO_DEV_TOKEN \
  --data-file=- \
  --project=your-project-id
```

**Update existing secret:**
```bash
# Create new version without trailing characters
echo -n "your-logo-dev-token" | gcloud secrets versions add LOGO_DEV_TOKEN \
  --data-file=- \
  --project=your-project-id
```

**Verify secret (should NOT show `\r` or `\n`):**
```bash
gcloud secrets versions access latest --secret="LOGO_DEV_TOKEN" --project=your-project-id | od -c
```

### Cloud Build / Cloud Run

**File:** `cloudbuild.yaml`

```yaml
steps:
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'your-service-name'
      - '--image=gcr.io/$PROJECT_ID/your-image:$SHORT_SHA'
      - '--region=us-central1'
      - '--platform=managed'
      - '--set-secrets=LOGO_DEV_TOKEN=LOGO_DEV_TOKEN:latest'
      # Add other secrets as needed
```

**Grant Cloud Run service account access:**
```bash
# Get Cloud Run service account
SERVICE_ACCOUNT=$(gcloud run services describe your-service-name \
  --region=us-central1 \
  --format='value(spec.template.spec.serviceAccountName)')

# Grant access to secret
gcloud secrets add-iam-policy-binding LOGO_DEV_TOKEN \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=your-project-id
```

### Docker / Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    environment:
      - LOGO_DEV_TOKEN=${LOGO_DEV_TOKEN}
    ports:
      - "8000:8000"
```

```bash
# Load from .env
docker-compose --env-file .env up
```

### Kubernetes

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: logo-dev-secret
type: Opaque
stringData:
  token: your_logo_dev_token_here

---
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: your-app
spec:
  template:
    spec:
      containers:
      - name: backend
        image: your-image
        env:
        - name: LOGO_DEV_TOKEN
          valueFrom:
            secretKeyRef:
              name: logo-dev-secret
              key: token
```

---

## Common Issues & Solutions

### Issue 1: "Invalid non-printable ASCII character in URL"

**Error:**
```
ValueError: Invalid non-printable ASCII character in URL, '\r' at position 86
```

**Cause:** Trailing carriage return (`\r`) or newline (`\n`) in `LOGO_DEV_TOKEN`

**Solution:**
```bash
# Recreate secret with -n flag
echo -n "your-logo-dev-token" | gcloud secrets create LOGO_DEV_TOKEN \
  --data-file=- \
  --project=your-project-id

# Or create new version
echo -n "your-logo-dev-token" | gcloud secrets versions add LOGO_DEV_TOKEN \
  --data-file=- \
  --project=your-project-id

# Force Cloud Run to use new version
gcloud run services update your-service-name \
  --region=us-central1 \
  --update-secrets=LOGO_DEV_TOKEN=LOGO_DEV_TOKEN:latest
```

### Issue 2: CORS Errors

**Error:** Browser console shows CORS policy error

**Cause:** Frontend trying to call logo.dev directly

**Solution:** Always use backend proxy endpoint:
```tsx
// ❌ WRONG - Direct call
<img src={`https://img.logo.dev/${domain}?token=${token}`} />

// ✅ CORRECT - Via proxy
<img src={`/api/logo/${domain}`} />
```

### Issue 3: 404 Errors for Valid Domains

**Possible Causes:**
1. Domain spelling/formatting issue
2. Logo.dev doesn't have logo for that company
3. Token not configured

**Debug Steps:**
```bash
# 1. Check backend logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=your-service" \
  --limit=50 \
  --format=json

# 2. Test logo service directly
curl https://img.logo.dev/boeing.com?token=YOUR_TOKEN&size=128&format=png -I

# 3. Check token is loaded
# Should see log: "Logo.dev service initialized with token: xxx..."
```

### Issue 4: Logos Not Caching

**Cause:** Missing or incorrect cache headers

**Solution:** Verify headers in proxy endpoint:
```python
return Response(
    content=logo_bytes,
    media_type="image/png",
    headers={
        "Cache-Control": "public, max-age=604800, immutable",  # 7 days
        "X-Logo-Domain": domain,
    }
)
```

### Issue 5: Token Not Found Warning

**Error:** `"LOGO_DEV_TOKEN not found in environment variables"`

**Debug Steps:**
```python
# Add to your settings logging
import os
print(f"Environment variables: {list(os.environ.keys())}")
print(f"LOGO_DEV_TOKEN present: {'LOGO_DEV_TOKEN' in os.environ}")
```

**Solutions:**
- Check `.env` file location and format
- Verify secret is mounted in Cloud Run
- Check service account has `secretAccessor` role
- Restart service after updating secrets

---

## Testing

### Manual Testing

```bash
# 1. Test backend proxy endpoint
curl http://localhost:8000/api/logo/boeing.com -o test_logo.png

# 2. Verify it's a valid image
file test_logo.png
# Should output: test_logo.png: PNG image data, 128 x 128, 8-bit/color RGBA

# 3. Test multiple domains
for domain in boeing.com airbus.com spacex.com; do
  echo "Testing $domain..."
  curl -s -w "Status: %{http_code}\n" http://localhost:8000/api/logo/$domain -o /dev/null
done
```

### Automated Tests

```python
# tests/test_logo_service.py
import pytest
from app.services.logo_service import logo_service, extract_domain

def test_extract_domain():
    assert extract_domain("https://www.gulfstream.com/about") == "gulfstream.com"
    assert extract_domain("compositesone.com") == "compositesone.com"
    assert extract_domain("http://example.co.uk:8080/page") == "example.co.uk"

@pytest.mark.asyncio
async def test_fetch_logo():
    """Test fetching a known company logo."""
    logo_bytes = await logo_service.fetch_logo("boeing.com")
    
    assert logo_bytes is not None
    assert len(logo_bytes) > 0
    # PNG magic bytes
    assert logo_bytes[:8] == b'\x89PNG\r\n\x1a\n'

@pytest.mark.asyncio
async def test_fetch_logo_not_found():
    """Test handling of non-existent domain."""
    logo_bytes = await logo_service.fetch_logo("this-domain-definitely-does-not-exist-123456.com")
    
    assert logo_bytes is None
```

### Frontend Testing

```tsx
// components/__tests__/CompanyLogo.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import CompanyLogo from '@/components/CompanyLogo'

describe('CompanyLogo', () => {
  it('renders logo image for valid domain', async () => {
    render(<CompanyLogo domain="boeing.com" size={48} />)
    
    const img = screen.getByAltText(/Company logo/i)
    expect(img).toBeInTheDocument()
    expect(img).toHaveAttribute('src', '/api/logo/boeing.com')
  })
  
  it('shows fallback icon on image error', async () => {
    const { container } = render(<CompanyLogo domain="invalid.com" size={48} />)
    
    const img = screen.getByAltText(/Company logo/i)
    
    // Simulate image load error
    img.dispatchEvent(new Event('error'))
    
    await waitFor(() => {
      expect(screen.getByTitle('invalid.com')).toBeInTheDocument()
      expect(container.querySelector('svg')).toBeInTheDocument() // Building icon
    })
  })
  
  it('handles missing domain gracefully', () => {
    const { container } = render(<CompanyLogo domain={null} size={48} />)
    
    // Should show fallback immediately
    expect(container.querySelector('svg')).toBeInTheDocument()
  })
})
```

### Load Testing

```bash
# Test concurrent logo requests
ab -n 100 -c 10 http://localhost:8000/api/logo/boeing.com

# Monitor cache effectiveness
curl -I http://localhost:8000/api/logo/boeing.com | grep -i cache-control
```

---

## Best Practices

1. **Always Use Backend Proxy** - Never expose Logo.dev token to frontend
2. **Set Cache Headers** - Logos rarely change, cache for 7+ days
3. **Provide Fallbacks** - Show initials or icon when logo unavailable
4. **Lazy Load Images** - Use `loading="lazy"` attribute for performance
5. **Clean Domain Input** - Remove `www.`, protocols, and paths
6. **Log Errors Appropriately** - Don't log full tokens, use `token[:10]`
7. **Use `-n` Flag** - Always when creating secrets with echo
8. **Test in Production** - Verify secrets are correctly mounted
9. **Monitor 404 Rates** - Track which domains don't have logos
10. **Handle Race Conditions** - Frontend may render before image loads

---

## Troubleshooting Checklist

When logos aren't working, check in this order:

- [ ] Environment variable `LOGO_DEV_TOKEN` is set
- [ ] Token has no trailing `\r` or `\n` characters
- [ ] Backend proxy endpoint returns 200 for known domains
- [ ] Frontend uses proxy URL, not direct logo.dev URL
- [ ] Cache headers are set correctly
- [ ] Service account has `secretAccessor` role (Cloud Run)
- [ ] Secret is mounted in deployment config
- [ ] CORS is not blocking requests (should use same origin)
- [ ] Image error handlers are implemented
- [ ] Fallback UI is shown when logo unavailable

---

## API Reference

### Backend Endpoints

#### GET /api/logo/{domain}

Fetch company logo via proxy.

**Parameters:**
- `domain` (path): Company domain (e.g., "boeing.com")

**Response:**
- Success: `200 OK` with PNG image bytes
- Not Found: `404 Not Found` 
- Error: `500 Internal Server Error`

**Headers:**
- `Content-Type: image/png`
- `Cache-Control: public, max-age=604800, immutable`
- `X-Logo-Domain: {domain}`

**Example:**
```bash
curl https://your-api.com/api/logo/boeing.com -o logo.png
```

### Logo Service Methods

#### `logo_service.get_logo_url(domain: str, size: int = 128) -> Optional[str]`

Returns the proxy URL path for frontend use.

**Parameters:**
- `domain`: Company domain
- `size`: Logo size in pixels (default: 128)

**Returns:** `/api/logo/{domain}` or `None`

#### `logo_service.fetch_logo(domain: str) -> Optional[bytes]`

Fetches logo image bytes from Logo.dev.

**Parameters:**
- `domain`: Company domain

**Returns:** PNG image bytes or `None`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial implementation with proxy pattern |
| 1.1 | Jan 2026 | Fixed trailing `\r` issue in secrets |
| 1.2 | Jan 2026 | Added caching headers and fallback UI |

---

## Related Documentation

- [Logo.dev API Documentation](https://logo.dev/docs)
- [GCP Secret Manager Guide](https://cloud.google.com/secret-manager/docs)
- [FastAPI Response Documentation](https://fastapi.tiangolo.com/advanced/custom-response/)
- [Next.js Image Optimization](https://nextjs.org/docs/basic-features/image-optimization)

---

## Support

For issues specific to this implementation:
1. Check backend logs for token loading
2. Test proxy endpoint directly with curl
3. Verify secret has no trailing characters
4. Check service account permissions

For Logo.dev API issues:
- Contact Logo.dev support
- Check API status page
- Verify token is active and has credits
