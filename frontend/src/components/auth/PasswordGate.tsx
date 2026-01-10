'use client'

import { useState, useEffect } from 'react'
import { Lock, User, Users, Loader2 } from 'lucide-react'

const AUTH_KEY = 'c1_hub_authenticated'
const USER_NAME_KEY = 'userName'  // Must match api.ts expectations
const USER_TEAM_KEY = 'userTeam'  // Must match api.ts expectations

// Teams based on C1 org structure
const TEAMS = [
  'Sales East',
  'Sales West',
  'Marketing',
  'Product/Supplier',
  'All Others'
] as const

interface PasswordGateProps {
  children: React.ReactNode
}

export function PasswordGate({ children }: PasswordGateProps) {
  const [authenticated, setAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [password, setPassword] = useState('')
  const [userName, setUserName] = useState('')
  const [userTeam, setUserTeam] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    // Check if already authenticated this session
    const isAuth = sessionStorage.getItem(AUTH_KEY) === 'true'

    // If authenticated, make sure localStorage has the user info
    if (isAuth) {
      const storedName = localStorage.getItem(USER_NAME_KEY)
      const storedTeam = localStorage.getItem(USER_TEAM_KEY)

      // If somehow missing team, require re-auth
      if (!storedTeam) {
        sessionStorage.removeItem(AUTH_KEY)
        setAuthenticated(false)
      } else {
        setAuthenticated(true)
      }
    }

    setLoading(false)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validate team selection
    if (!userTeam) {
      setError('Please select your team.')
      return
    }

    // Validate name
    if (!userName.trim()) {
      setError('Please enter your name.')
      return
    }

    setSubmitting(true)

    try {
      // LOCAL DEVELOPMENT BYPASS: Check if running on localhost
      const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

      if (isLocalDev && password === 'partnership2026') {
        // Store authentication state in sessionStorage
        sessionStorage.setItem(AUTH_KEY, 'true')

        // Store user info in localStorage (for API headers)
        const trimmedName = userName.trim()
        localStorage.setItem(USER_NAME_KEY, trimmedName)
        localStorage.setItem(USER_TEAM_KEY, userTeam)

        setAuthenticated(true)
        setSubmitting(false)
        return
      }

      // Production: verify with backend
      const response = await fetch('/api/verify-access', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          password,
          user_name: userName.trim(),
          user_team: userTeam
        })
      })

      if (response.ok) {
        // Store authentication state in sessionStorage
        sessionStorage.setItem(AUTH_KEY, 'true')

        // Store user info in localStorage (for API headers)
        const trimmedName = userName.trim()
        localStorage.setItem(USER_NAME_KEY, trimmedName)
        localStorage.setItem(USER_TEAM_KEY, userTeam)

        setAuthenticated(true)
      } else {
        setError('Incorrect password. Please try again.')
      }
    } catch (err) {
      setError('Connection error. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  // Show loading spinner while checking auth status
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading...</span>
        </div>
      </div>
    )
  }

  // Show app if authenticated
  if (authenticated) {
    return <>{children}</>
  }

  // Show login gate
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
      <div className="bg-slate-800 p-8 rounded-xl shadow-2xl max-w-md w-full border border-slate-700">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">C1 Intelligence Hub</h1>
          <p className="text-slate-400 mt-2">Partner Access</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name Field */}
          <div>
            <label className="block text-slate-300 text-sm font-medium mb-2">
              <User className="w-4 h-4 inline mr-2" />
              Your Name
            </label>
            <input
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              placeholder="Enter your name"
              className="w-full p-3 rounded-lg bg-slate-700 text-white border border-slate-600 
                         focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                         placeholder-slate-400"
              required
              autoComplete="name"
            />
          </div>

          {/* Team Selection */}
          <div>
            <label className="block text-slate-300 text-sm font-medium mb-2">
              <Users className="w-4 h-4 inline mr-2" />
              Your Team
            </label>
            <select
              value={userTeam}
              onChange={(e) => setUserTeam(e.target.value)}
              className="w-full p-3 rounded-lg bg-slate-700 text-white border border-slate-600 
                         focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                         appearance-none cursor-pointer"
              required
            >
              <option value="" disabled className="text-slate-400">Select your team</option>
              {TEAMS.map(team => (
                <option key={team} value={team}>{team}</option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              This helps personalize your intelligence feed
            </p>
          </div>

          {/* Password Field */}
          <div>
            <label className="block text-slate-300 text-sm font-medium mb-2">
              <Lock className="w-4 h-4 inline mr-2" />
              Access Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              className="w-full p-3 rounded-lg bg-slate-700 text-white border border-slate-600 
                         focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                         placeholder-slate-400"
              required
              autoComplete="current-password"
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full p-3 rounded-lg bg-blue-600 text-white font-medium
                       hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                       focus:ring-offset-slate-800 disabled:opacity-50 disabled:cursor-not-allowed
                       transition-colors flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Verifying...
              </>
            ) : (
              'Enter Hub'
            )}
          </button>
        </form>

        {/* Footer */}
        <p className="text-center text-slate-500 text-xs mt-6">
          Contact your C1 representative if you need access credentials.
        </p>
      </div>
    </div>
  )
}

export default PasswordGate
