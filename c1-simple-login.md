# C1 Intelligence Hub: Simple Access Gate

## Overview

A lightweight password gate for the pilot phase. This is not real authentication - it's a door to keep out casual visitors while Dave's team evaluates the product.

**What this does:**
- Requires a shared password to access the app
- Captures user's name for activity tracking
- Persists across page refreshes (session-based)

**What this doesn't do:**
- Provide real security (password is shared)
- Track individual logins/sessions
- Protect against determined access

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ACCESS FLOW                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User visits app URL                                        │
│         ↓                                                   │
│  PasswordGate checks sessionStorage                         │
│         ↓                                                   │
│  Not authenticated? → Show login modal                      │
│         ↓                                                   │
│  User enters password + name                                │
│         ↓                                                   │
│  Backend verifies password (env var)                        │
│         ↓                                                   │
│  Success → Store in sessionStorage, show app                │
│         ↓                                                   │
│  Name available for event logging via header                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend Implementation

### Environment Variable

Add to your Cloud Run environment (or `.env` for local):

```bash
SITE_ACCESS_PASSWORD=partnership2025
```

### Verification Endpoint

```javascript
// routes/auth.js

const express = require('express');
const router = express.Router();

// POST /api/verify-access
router.post('/verify-access', (req, res) => {
  const { password } = req.body;
  const validPassword = process.env.SITE_ACCESS_PASSWORD;
  
  if (!validPassword) {
    console.error('SITE_ACCESS_PASSWORD not configured');
    return res.status(500).json({ error: 'Server configuration error' });
  }
  
  if (password === validPassword) {
    res.json({ success: true });
  } else {
    res.status(401).json({ success: false, error: 'Incorrect password' });
  }
});

module.exports = router;
```

### Register Route

```javascript
// server.js or app.js

const authRoutes = require('./routes/auth');

// Public route - no auth middleware
app.use('/api', authRoutes);
```

---

## Frontend Implementation

### PasswordGate Component

```jsx
// components/PasswordGate.jsx

import { useState, useEffect } from 'react';

const AUTH_KEY = 'c1_hub_authenticated';
const USER_NAME_KEY = 'c1_user_name';
const USER_TEAM_KEY = 'c1_user_team';

// Teams based on C1 org structure
const TEAMS = [
  'Sales East',
  'Sales West',
  'Marketing',
  'Product/Supplier',
  'All Others'
];

export function PasswordGate({ children }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [password, setPassword] = useState('');
  const [userName, setUserName] = useState('');
  const [userTeam, setUserTeam] = useState('');  // Required - no default
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    // Check if already authenticated this session
    const isAuth = sessionStorage.getItem(AUTH_KEY) === 'true';
    setAuthenticated(isAuth);
    setLoading(false);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    // Validate team selection
    if (!userTeam) {
      setError('Please select your team.');
      return;
    }
    
    setSubmitting(true);

    try {
      const response = await fetch('/api/verify-access', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });

      if (response.ok) {
        // Store authentication state
        sessionStorage.setItem(AUTH_KEY, 'true');
        
        // Store user name (required field)
        const trimmedName = userName.trim() || 'Anonymous';
        sessionStorage.setItem(USER_NAME_KEY, trimmedName);
        
        // Store user team (required field)
        sessionStorage.setItem(USER_TEAM_KEY, userTeam);
        
        setAuthenticated(true);
      } else {
        setError('Incorrect password. Please try again.');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // Show nothing while checking auth status
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  // Show app if authenticated
  if (authenticated) {
    return children;
  }

  // Show login gate
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 px-4">
      <div className="bg-gray-800 p-8 rounded-xl shadow-2xl max-w-md w-full border border-gray-700">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">🔐</span>
          </div>
          <h1 className="text-2xl font-bold text-white">C1 Intelligence Hub</h1>
          <p className="text-gray-400 mt-2">Partner Access</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name Field */}
          <div>
            <label className="block text-gray-300 text-sm font-medium mb-2">
              Your Name
            </label>
            <input
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              placeholder="Enter your name"
              className="w-full p-3 rounded-lg bg-gray-700 text-white border border-gray-600 
                         focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                         placeholder-gray-400"
              required
            />
          </div>

          {/* Team Selection - Required */}
          <div>
            <label className="block text-gray-300 text-sm font-medium mb-2">
              Your Team
            </label>
            <select
              value={userTeam}
              onChange={(e) => setUserTeam(e.target.value)}
              className="w-full p-3 rounded-lg bg-gray-700 text-white border border-gray-600 
                         focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                         appearance-none cursor-pointer"
              required
            >
              <option value="" disabled>Select your team</option>
              {TEAMS.map(team => (
                <option key={team} value={team}>{team}</option>
              ))}
            </select>
          </div>

          {/* Password Field */}
          <div>
            <label className="block text-gray-300 text-sm font-medium mb-2">
              Access Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              className="w-full p-3 rounded-lg bg-gray-700 text-white border border-gray-600 
                         focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                         placeholder-gray-400"
              required
              autoFocus
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full p-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 
                       disabled:cursor-not-allowed text-white rounded-lg font-medium 
                       transition-colors duration-200"
          >
            {submitting ? 'Verifying...' : 'Enter Hub'}
          </button>
        </form>

        {/* Footer */}
        <p className="text-gray-500 text-xs text-center mt-8">
          Composites One × Ket Zero Intelligence Platform
        </p>
      </div>
    </div>
  );
}
```

### Usage in App Root

```jsx
// App.jsx

import { PasswordGate } from './components/PasswordGate';
import { IntelligenceHub } from './components/IntelligenceHub';

function App() {
  return (
    <PasswordGate>
      <IntelligenceHub />
    </PasswordGate>
  );
}

export default App;
```

---

## User Context Integration

### Getting User Name and Team

```javascript
// utils/user.js

export function getCurrentUserName() {
  return sessionStorage.getItem('c1_user_name') || 'anonymous';
}

export function getCurrentUserTeam() {
  return sessionStorage.getItem('c1_user_team') || 'All Others';
}

export function getCurrentUser() {
  return {
    name: getCurrentUserName(),
    team: getCurrentUserTeam()
  };
}
```

### Adding to API Calls

```javascript
// utils/api.js

import { getCurrentUserName, getCurrentUserTeam } from './user';

export async function apiCall(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-User-Name': getCurrentUserName(),
    'X-User-Team': getCurrentUserTeam(),
    ...options.headers
  };
  
  return fetch(endpoint, {
    ...options,
    headers
  });
}
```

### Using Throughout the App

```javascript
// Example: Saving a briefing
import { apiCall } from '../utils/api';

async function saveBriefing(briefing) {
  const response = await apiCall('/api/memory/log/briefing', {
    method: 'POST',
    body: JSON.stringify({ briefing })
  });
  
  return response.json();
}

// Example: Running deep research
async function runResearch(query) {
  const response = await apiCall('/api/research', {
    method: 'POST',
    body: JSON.stringify({ query })
  });
  
  return response.json();
}
```

### Backend: Extracting User Name

```javascript
// middleware/userName.js

function extractUserName(req, res, next) {
  req.userName = req.headers['x-user-name'] || 'anonymous';
  next();
}

module.exports = { extractUserName };
```

```javascript
// server.js

const { extractUserName } = require('./middleware/userName');

// Apply to all API routes
app.use('/api', extractUserName);

// Then in route handlers:
app.post('/api/memory/log/briefing', async (req, res) => {
  const userName = req.userName; // Available from middleware
  // ... rest of handler
});
```

---

## Activity Logging (Optional Enhancement)

Track who's doing what during the pilot:

### Activity Log Table

```sql
CREATE TABLE `c1_hub.activity_log` (
  activity_id STRING NOT NULL,
  user_name STRING NOT NULL,
  activity_type STRING NOT NULL,    -- 'login', 'research', 'export', 'save_briefing', etc.
  activity_data JSON,               -- flexible payload
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

### Logging Middleware

```javascript
// services/activityLog.js

const { BigQuery } = require('@google-cloud/bigquery');
const bigquery = new BigQuery();

async function logActivity(userName, activityType, activityData = {}) {
  try {
    const query = `
      INSERT INTO \`c1_hub.activity_log\` 
      (activity_id, user_name, activity_type, activity_data)
      VALUES (@activityId, @userName, @activityType, @activityData)
    `;
    
    await bigquery.query({
      query,
      params: {
        activityId: `act_${Date.now()}`,
        userName,
        activityType,
        activityData: JSON.stringify(activityData)
      }
    });
  } catch (error) {
    // Don't fail requests due to logging errors
    console.error('Activity logging failed:', error);
  }
}

module.exports = { logActivity };
```

### Log Key Actions

```javascript
// In your route handlers

const { logActivity } = require('../services/activityLog');

// Log research queries
app.post('/api/research', async (req, res) => {
  const { query } = req.body;
  const userName = req.userName;
  
  // Log the activity
  await logActivity(userName, 'deep_research', { query });
  
  // ... run research
});

// Log exports
app.post('/api/export', async (req, res) => {
  const { reportId, format } = req.body;
  const userName = req.userName;
  
  await logActivity(userName, 'export', { reportId, format });
  
  // ... generate export
});

// Log briefing saves
app.post('/api/memory/log/briefing', async (req, res) => {
  const userName = req.userName;
  
  await logActivity(userName, 'save_briefing', { 
    briefingTitle: req.body.briefing?.title 
  });
  
  // ... save briefing
});
```

---

## Display Current User (Optional)

Show who's logged in somewhere in the UI:

```jsx
// components/UserBadge.jsx

import { getCurrentUserName } from '../utils/user';

export function UserBadge() {
  const userName = getCurrentUserName();
  
  if (userName === 'anonymous') return null;
  
  return (
    <div className="flex items-center gap-2 text-gray-400 text-sm">
      <div className="w-6 h-6 bg-blue-600 rounded-full flex items-center justify-center text-white text-xs">
        {userName.charAt(0).toUpperCase()}
      </div>
      <span>{userName}</span>
    </div>
  );
}
```

Use in your header:

```jsx
// components/Header.jsx

import { UserBadge } from './UserBadge';

export function Header() {
  return (
    <header className="flex justify-between items-center p-4 border-b border-gray-700">
      <h1 className="text-xl font-bold text-white">C1 Intelligence Hub</h1>
      <UserBadge />
    </header>
  );
}
```

---

## Logout Function (Optional)

If you want users to be able to switch names:

```jsx
// components/LogoutButton.jsx

export function LogoutButton() {
  const handleLogout = () => {
    sessionStorage.removeItem('c1_hub_authenticated');
    sessionStorage.removeItem('c1_user_name');
    window.location.reload();
  };
  
  return (
    <button 
      onClick={handleLogout}
      className="text-gray-400 hover:text-white text-sm"
    >
      Switch User
    </button>
  );
}
```

---

## Cloud Run Deployment

### Set Environment Variable

```bash
# Via gcloud CLI
gcloud run services update c1-intelligence-hub \
  --set-env-vars SITE_ACCESS_PASSWORD=partnership2025 \
  --region us-central1

# Or in your cloudbuild.yaml / deployment config
env:
  - name: SITE_ACCESS_PASSWORD
    value: partnership2025
```

### Verify It's Working

```bash
# Test the endpoint
curl -X POST https://your-cloud-run-url/api/verify-access \
  -H "Content-Type: application/json" \
  -d '{"password": "partnership2025"}'

# Should return: {"success": true}
```

---

## Security Notes

| Aspect | Status | Notes |
|--------|--------|-------|
| Password storage | ✅ Server-side | In env var, not in client code |
| Session persistence | ⚠️ sessionStorage | Cleared when browser closes |
| Name verification | ❌ None | User can enter any name |
| Rate limiting | ❌ None | Could add if abuse occurs |
| HTTPS | ✅ Cloud Run | Automatic with Cloud Run |

**For pilot phase**: This is fine. You're keeping casual visitors out, not protecting state secrets.

**When to upgrade**: When you have multiple organizations, need audit trails, or go to production with paying customers.

---

## Checklist

- [ ] Add `SITE_ACCESS_PASSWORD` to Cloud Run environment
- [ ] Create `/api/verify-access` endpoint
- [ ] Create `PasswordGate` component
- [ ] Wrap app root with `PasswordGate`
- [ ] Create `getCurrentUserName()` utility
- [ ] Create `apiCall()` wrapper that adds `X-User-Name` header
- [ ] Add `extractUserName` middleware to backend
- [ ] (Optional) Create `activity_log` table
- [ ] (Optional) Add activity logging to key actions
- [ ] (Optional) Add `UserBadge` component to header
- [ ] (Optional) Add logout/switch user functionality
- [ ] Test locally with different names
- [ ] Deploy and verify password gate works on Cloud Run
