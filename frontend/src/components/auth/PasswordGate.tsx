'use client'

import { useState, useEffect } from 'react'
import { Sparkles, User, Loader2 } from 'lucide-react'

const AUTH_KEY = 'c1_hub_authenticated'
const USER_NAME_KEY = 'userName'  // Must match api.ts expectations
const USER_TEAM_KEY = 'userTeam'  // Must match api.ts expectations
// No password required - simplified login (name only)

interface PasswordGateProps {
  children: React.ReactNode
}

export function PasswordGate({ children }: PasswordGateProps) {
  const [authenticated, setAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [userName, setUserName] = useState('')
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

    // Validate name
    if (!userName.trim()) {
      setError('Please enter your name.')
      return
    }

    // Default team for simplified login
    const defaultTeam = 'All Others'

    setSubmitting(true)

    try {
      const trimmedName = userName.trim()
      const isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

      if (isLocalDev) {
        // Local dev: skip backend call
        sessionStorage.setItem(AUTH_KEY, 'true')
        localStorage.setItem(USER_NAME_KEY, trimmedName)
        localStorage.setItem(USER_TEAM_KEY, defaultTeam)
        setAuthenticated(true)
        setSubmitting(false)
        return
      }

      // Production: verify with backend (name-only login)
      const response = await fetch('/api/verify-access', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_name: trimmedName,
          user_team: defaultTeam
        })
      })

      if (response.ok) {
        sessionStorage.setItem(AUTH_KEY, 'true')
        localStorage.setItem(USER_NAME_KEY, trimmedName)
        localStorage.setItem(USER_TEAM_KEY, defaultTeam)
        setAuthenticated(true)
      } else {
        setError('Something went wrong. Please try again.')
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
          <div className="w-16 h-16 bg-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">C1 Intelligence Hub</h1>
          <p className="text-slate-400 mt-2">Jump in and explore</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name Field */}
          <div>
            <label className="block text-slate-300 text-sm font-medium mb-2">
              <User className="w-4 h-4 inline mr-2" />
              What should we call you?
            </label>
            <input
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              placeholder="Your name or Roger Rabbit"
              className="w-full p-3 rounded-lg bg-slate-700 text-white border border-slate-600
                         focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none
                         placeholder-slate-400"
              required
              autoComplete="name"
            />
            <p className="text-xs text-slate-500 mt-2">
              No email, no spam. Just a name so we know who&apos;s poking around.
            </p>
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
            className="w-full p-3 rounded-lg bg-emerald-600 text-white font-medium
                       hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2
                       focus:ring-offset-slate-800 disabled:opacity-50 disabled:cursor-not-allowed
                       transition-colors flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading...
              </>
            ) : (
              'Enter Hub'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

export default PasswordGate
