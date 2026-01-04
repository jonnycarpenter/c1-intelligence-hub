'use client'

import { useState } from 'react'
import { Building2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { API_BASE } from '@/lib/config'

interface CompanyLogoProps {
  /** Domain or logo proxy URL (e.g., "gulfstream.com" or "/api/pipeline/logo/gulfstream.com") */
  domain?: string | null
  /** Logo proxy URL from API response */
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
 * <CompanyLogo logoUrl={prospect.logo_url} size={48} />
 * ```
 */
export default function CompanyLogo({ 
  domain, 
  logoUrl,
  size = 40, 
  className 
}: CompanyLogoProps) {
  const [imgError, setImgError] = useState(false)
  
  // Determine the logo URL to use
  // Priority: logoUrl prop > construct from domain
  const getLogoUrl = (): string | null => {
    if (logoUrl) {
      // If it's already an absolute URL, use as-is
      if (logoUrl.startsWith('http')) {
        return logoUrl
      }
      // If it's a relative path, prepend API_BASE for dev mode
      if (logoUrl.startsWith('/')) {
        return `${API_BASE}${logoUrl}`
      }
    }
    
    if (domain) {
      // Clean the domain and construct proxy URL
      const cleanDomain = domain
        .toLowerCase()
        .replace(/^https?:\/\//, '')
        .replace(/^www\./, '')
        .split('/')[0]
      
      return `${API_BASE}/api/pipeline/logo/${cleanDomain}`
    }
    
    return null
  }
  
  const finalLogoUrl = getLogoUrl()
  
  // Show fallback if no URL or image failed to load
  if (!finalLogoUrl || imgError) {
    return (
      <div 
        className={cn(
          "bg-gradient-to-br from-slate-100 to-slate-200 rounded-lg flex items-center justify-center shrink-0",
          className
        )}
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
      className={cn(
        "rounded-lg object-contain bg-white border border-slate-200 shrink-0",
        className
      )}
      style={{ width: size, height: size }}
      onError={() => setImgError(true)}
      loading="lazy"
    />
  )
}
