'use client'

import { useEffect, useState } from 'react'

const AUTH_KEY = 'c1_hub_authenticated'
const USER_NAME_KEY = 'userName'
const USER_TEAM_KEY = 'userTeam'

interface PasswordGateProps {
  children: React.ReactNode
}

export function PasswordGate({ children }: PasswordGateProps) {
  // We need a mounted state to avoid hydration mismatches with localStorage usage
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    // Ensure default user exists for components that might read this
    if (!localStorage.getItem(USER_NAME_KEY)) {
      localStorage.setItem(USER_NAME_KEY, 'Guest User')
    }
    if (!localStorage.getItem(USER_TEAM_KEY)) {
      localStorage.setItem(USER_TEAM_KEY, 'Guest Team')
    }

    // Set auth key just in case legacy code checks it
    sessionStorage.setItem(AUTH_KEY, 'true')
    setMounted(true)
  }, [])

  // During SSR and first render, return null to ensure localStorage is populated 
  // before children mount (avoiding race conditions in AppHeader)
  if (!mounted) return null

  return <>{children}</>
}

export default PasswordGate
