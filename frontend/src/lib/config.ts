/**
 * Configuration utilities for the frontend
 */

/**
 * Get the API base URL.
 * In production (static export), use relative URLs since frontend and backend are on same origin.
 * In development, use localhost:8000.
 * 
 * This is evaluated safely on both server and client.
 */
export function getApiBaseUrl(): string {
  // If environment variable is set, use it
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL
  }
  
  // During SSR or static generation, return empty string (relative URLs)
  if (typeof window === 'undefined') {
    return ''
  }
  
  // In production (non-localhost), use relative URLs
  if (window.location.hostname !== 'localhost') {
    return ''
  }
  
  // Default to localhost for development
  return 'http://localhost:8000'
}

// Export the function result - evaluated at import time but safely handles SSR
export const API_BASE = getApiBaseUrl()
