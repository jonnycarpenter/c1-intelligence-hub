'use client'

import { useState, useEffect } from 'react'
import {
  ChevronDown,
  ChevronUp,
  X,
  ExternalLink,
  Building2,
  Users,
  Zap,
  Save,
  Sparkles,
  MapPin,
  Calendar,
  Loader2,
  ListChecks,
  CheckCircle2,
  XCircle,
  Mail,
  Phone,
  Linkedin,
  DollarSign,
  Briefcase,
  Shield,
  CreditCard,
  Globe,
  Hash,
} from 'lucide-react'
import CompanyLogo from './CompanyLogo'
import type {
  SearchBlock,
  EnhancedProspectSearchResult,
  EnhancedContactSearchResult,
  EnhancedTriggerEventResult,
  ApolloEnrichmentResult,
  ApolloContactTeaserResult,
  ApolloContactRevealedResult,
  ApolloCreditStatus,
} from '@/types'

interface SearchBlockCardProps {
  block: SearchBlock
  onToggle: () => void
  onRemove: () => void
  onSaveProspect?: (prospect: EnhancedProspectSearchResult) => void
  onSaveContact?: (contact: EnhancedContactSearchResult) => void
  onRevealContact?: (personId: string) => Promise<void>
  onEnrichProspect?: (blockId: string, domain: string) => Promise<ApolloEnrichmentResult | null>
  isPolling?: boolean
  isRevealing?: boolean
}

// Block type icons and colors
const BLOCK_TYPE_CONFIG: Record<string, {
  icon: typeof Sparkles
  color: string
  bg: string
  border: string
  label: string
}> = {
  similar_companies: {
    icon: Sparkles,
    color: 'text-purple-500',
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    label: 'Similar Companies',
  },
  search_companies: {
    icon: Building2,
    color: 'text-blue-500',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    label: 'Company Search',
  },
  contacts: {
    icon: Users,
    color: 'text-emerald-500',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    label: 'Contacts',
  },
  trigger_events: {
    icon: Zap,
    color: 'text-emerald-500',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    label: 'Trigger Events',
  },
  webset_building: {
    icon: ListChecks,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-300',
    label: 'Full List Building',
  },
  // Apollo.io block types
  apollo_enrichment: {
    icon: Building2,
    color: 'text-indigo-500',
    bg: 'bg-indigo-50',
    border: 'border-indigo-200',
    label: 'Company Enrichment',
  },
  apollo_contacts: {
    icon: Users,
    color: 'text-cyan-500',
    bg: 'bg-cyan-50',
    border: 'border-cyan-200',
    label: 'Apollo Contacts',
  },
  apollo_contact_revealed: {
    icon: Mail,
    color: 'text-rose-500',
    bg: 'bg-rose-50',
    border: 'border-rose-200',
    label: 'Contact Revealed',
  },
  apollo_credits: {
    icon: CreditCard,
    color: 'text-slate-500',
    bg: 'bg-slate-50',
    border: 'border-slate-200',
    label: 'Credit Status',
  },
}

// Event type badges
const EVENT_TYPE_COLORS: Record<string, string> = {
  expansion: 'bg-emerald-100 text-emerald-700',
  funding: 'bg-purple-100 text-purple-700',
  acquisition: 'bg-blue-100 text-blue-700',
  contract: 'bg-emerald-100 text-emerald-700',
  leadership: 'bg-rose-100 text-rose-700',
  partnership: 'bg-cyan-100 text-cyan-700',
  other: 'bg-gray-100 text-gray-700',
}

export function SearchBlockCard({
  block,
  onToggle,
  onRemove,
  onSaveProspect,
  onSaveContact,
  onRevealContact,
  onEnrichProspect,
  isPolling,
  isRevealing,
}: SearchBlockCardProps) {
  const config = BLOCK_TYPE_CONFIG[block.block_type] || BLOCK_TYPE_CONFIG.search_companies
  const Icon = config.icon

  // Handle webset building blocks specially
  const isWebsetBuilding = block.block_type === 'webset_building'
  const websetStatus = block.webset_status || 'running'

  // Apollo block types
  const isApolloEnrichment = block.block_type === 'apollo_enrichment'
  const isApolloContacts = block.block_type === 'apollo_contacts'
  const isApolloRevealed = block.block_type === 'apollo_contact_revealed'
  const isApolloCredits = block.block_type === 'apollo_credits'

  return (
    <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden transition-all duration-200`}>
      {/* Header */}
      <div className="px-4 py-3 bg-white/50 backdrop-blur-sm flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${config.bg}`}>
            {isWebsetBuilding && websetStatus === 'running' ? (
              <Loader2 className={`w-4 h-4 ${config.color} animate-spin`} />
            ) : isWebsetBuilding && websetStatus === 'completed' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            ) : isWebsetBuilding && websetStatus === 'failed' ? (
              <XCircle className="w-4 h-4 text-red-500" />
            ) : (
              <Icon className={`w-4 h-4 ${config.color}`} />
            )}
          </div>
          <div>
            <h3 className="font-medium text-gray-900">{block.title}</h3>
            <p className="text-xs text-gray-500">
              {isWebsetBuilding ? (
                websetStatus === 'running' ? (
                  <span className="text-emerald-600">Building enriched list... (1-5 min)</span>
                ) : websetStatus === 'completed' ? (
                  <span className="text-emerald-600">{block.result_count} companies ready</span>
                ) : (
                  <span className="text-red-600">Build failed</span>
                )
              ) : (
                <>{block.result_count} results • {config.label}</>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onToggle}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label={block.is_expanded ? 'Collapse' : 'Expand'}
          >
            {block.is_expanded ? (
              <ChevronUp className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-gray-500" />
            )}
          </button>
          <button
            onClick={onRemove}
            className="p-1.5 hover:bg-red-50 rounded-lg transition-colors"
            aria-label="Remove block"
          >
            <X className="w-4 h-4 text-gray-400 hover:text-red-500" />
          </button>
        </div>
      </div>

      {/* Content */}
      {block.is_expanded && (
        <div className="px-4 py-3 bg-white space-y-2 max-h-[500px] overflow-y-auto">
          {/* Webset Building Status */}
          {isWebsetBuilding && (
            <div className="py-6 text-center">
              {websetStatus === 'running' ? (
                <div className="space-y-3">
                  <div className="flex justify-center">
                    <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center">
                      <Loader2 className="w-6 h-6 text-emerald-600 animate-spin" />
                    </div>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Building Your List</p>
                    <p className="text-sm text-gray-500 mt-1">
                      We&apos;re gathering and enriching company data. This typically takes 1-5 minutes.
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      Includes: employee count, funding, location, LinkedIn profiles
                    </p>
                  </div>
                </div>
              ) : websetStatus === 'completed' ? (
                <div className="space-y-3">
                  <div className="flex justify-center">
                    <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center">
                      <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                    </div>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">List Ready!</p>
                    <p className="text-sm text-gray-500 mt-1">
                      {block.result_count} companies with enriched data
                    </p>
                    <p className="text-xs text-emerald-600 mt-2">
                      Click to view full results (coming soon)
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex justify-center">
                    <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                      <XCircle className="w-6 h-6 text-red-600" />
                    </div>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">Build Failed</p>
                    <p className="text-sm text-gray-500 mt-1">
                      There was an error building your list. Please try again.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Prospects (similar_companies or search_companies) */}
          {!isWebsetBuilding && block.prospects && block.prospects.map((prospect, idx) => (
            <ProspectItem
              key={`${prospect.url}-${idx}`}
              prospect={prospect}
              index={idx}
              onSave={onSaveProspect}
              onEnrich={(domain) => onEnrichProspect ? onEnrichProspect(block.id, domain) : Promise.resolve(null)}
            />
          ))}

          {/* Contacts */}
          {!isWebsetBuilding && block.contacts && block.contacts.map((contact, idx) => (
            <ContactItem
              key={`${contact.url}-${idx}`}
              contact={contact}
              index={idx}
              onSave={onSaveContact}
            />
          ))}

          {/* Trigger Events */}
          {!isWebsetBuilding && block.trigger_events && block.trigger_events.map((event, idx) => (
            <TriggerEventItem
              key={`${event.url}-${idx}`}
              event={event}
              index={idx}
            />
          ))}

          {/* Apollo.io Enrichment */}
          {isApolloEnrichment && block.apollo_enrichment && (
            <ApolloEnrichmentItem enrichment={block.apollo_enrichment} />
          )}

          {/* Apollo.io Contact Teasers */}
          {isApolloContacts && block.apollo_contacts && (
            <>
              {/* Company Context Header (if enrichment available) */}
              {block.company_enrichment && (
                <div className="mb-4 p-4 rounded-xl border border-cyan-100 bg-gradient-to-br from-cyan-50/50 to-white">
                  <div className="flex items-center gap-4">
                    <CompanyLogo
                      domain={block.company_enrichment.domain}
                      logoUrl={block.company_enrichment.logo_url}
                      size={56}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-lg font-semibold text-slate-900">
                          {block.company_enrichment.name}
                        </h4>
                        {block.company_enrichment.industry && (
                          <span className="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded-full">
                            {block.company_enrichment.industry}
                          </span>
                        )}
                      </div>
                      {block.company_enrichment.description && (
                        <p className="text-sm text-slate-500 line-clamp-1 mt-0.5">
                          {block.company_enrichment.description}
                        </p>
                      )}
                      {/* Key Metrics Row */}
                      <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                        {block.company_enrichment.employee_count && (
                          <span className="flex items-center gap-1">
                            <Users className="w-3.5 h-3.5 text-cyan-600" />
                            <span className="font-medium text-slate-700">
                              {block.company_enrichment.employee_count.toLocaleString()}
                            </span> employees
                          </span>
                        )}
                        {block.company_enrichment.revenue_printed && (
                          <span className="flex items-center gap-1">
                            <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
                            <span className="font-medium text-slate-700">
                              {block.company_enrichment.revenue_printed}
                            </span> revenue
                          </span>
                        )}
                        {(block.company_enrichment.city || block.company_enrichment.state) && (
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3.5 h-3.5 text-slate-400" />
                            {[block.company_enrichment.city, block.company_enrichment.state]
                              .filter(Boolean).join(', ')}
                          </span>
                        )}
                      </div>
                    </div>
                    {block.company_enrichment.linkedin_url && (
                      <a
                        href={block.company_enrichment.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-blue-600 transition-colors"
                        title="View company LinkedIn"
                      >
                        <Linkedin className="w-5 h-5" />
                      </a>
                    )}
                  </div>
                </div>
              )}
              {/* Contact Cards */}
              {block.apollo_contacts.map((contact, idx) => (
                <ApolloContactTeaserItem
                  key={`${contact.id}-${idx}`}
                  contact={contact}
                />
              ))}
            </>
          )}

          {/* Apollo.io Revealed Contact */}
          {isApolloRevealed && block.apollo_contact_revealed && (
            <ApolloContactRevealedItem contact={block.apollo_contact_revealed} />
          )}

          {/* Apollo.io Credits */}
          {isApolloCredits && block.apollo_credits && (
            <ApolloCreditStatusItem credits={block.apollo_credits} />
          )}
        </div>
      )}
    </div>
  )
}

// Individual result items
function ProspectItem({
  prospect,
  index,
  onSave,
  onEnrich
}: {
  prospect: EnhancedProspectSearchResult
  index?: number
  onSave?: (p: EnhancedProspectSearchResult) => void
  onEnrich?: (domain: string) => Promise<ApolloEnrichmentResult | null>
}) {
  const [saved, setSaved] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const [enrichment, setEnrichment] = useState<ApolloEnrichmentResult | null>(prospect.apollo_enrichment || null)
  const [isEnriching, setIsEnriching] = useState(false)

  useEffect(() => {
    if (prospect.apollo_enrichment) {
      setEnrichment(prospect.apollo_enrichment)
    }
  }, [prospect.apollo_enrichment])

  const handleSave = () => {
    if (onSave) {
      onSave(prospect)
      setSaved(true)
    }
  }

  const handleEnrich = async () => {
    if (!onEnrich || !prospect.domain || enrichment) return
    setIsEnriching(true)
    try {
      const result = await onEnrich(prospect.domain)
      if (result) setEnrichment(result)
    } catch (err) {
      console.error('Enrichment failed:', err)
    } finally {
      setIsEnriching(false)
    }
  }

  const hq = enrichment ?
    [enrichment.city, enrichment.state, enrichment.country].filter(Boolean).join(', ') :
    null;

  return (
    <div className={`flex flex-col gap-3 p-4 border border-slate-200 rounded-xl hover:border-emerald-200 hover:shadow-md transition-all group ${index !== undefined && index % 2 === 0 ? 'bg-white' : 'bg-emerald-50/20'}`}>
      {/* 1. Header & Identity */}
      <div className="flex items-start gap-4">
        <CompanyLogo domain={prospect.domain} size={48} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-semibold text-slate-900 text-base">
              {prospect.company_name || prospect.title}
            </h4>
            {prospect.score && prospect.score > 0.8 && (
              <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-700 rounded-full">
                High Match
              </span>
            )}
            {prospect.domain && (
              <span className="text-xs text-slate-400 font-medium">{prospect.domain}</span>
            )}
          </div>

          {/* Supply Chain Tags */}
          {enrichment?.supply_chain_matches && enrichment.supply_chain_matches.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {enrichment.supply_chain_matches.map((match, i) => (
                <span key={i} className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-100 rounded text-[10px] font-semibold">
                  {match}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleSave}
            disabled={saved}
            className={`p-2 rounded-lg transition-all ${saved
              ? 'bg-emerald-100 text-emerald-600'
              : 'hover:bg-slate-100 text-slate-400 hover:text-emerald-600'
              }`}
            title={saved ? 'Saved' : 'Save to pipeline'}
          >
            <Save className="w-4 h-4" />
          </button>
          <a
            href={prospect.url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 hover:bg-slate-100 rounded-lg text-slate-400 hover:text-blue-600 transition-all"
            title="Open website"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* 2. Metadata Grid (The "Glance") */}
      {enrichment && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 py-3 border-y border-slate-50">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-50 flex items-center justify-center">
              <Users className="w-3.5 h-3.5 text-blue-600" />
            </div>
            <div>
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tight">Size</p>
              <p className="text-xs font-semibold text-slate-700">
                {enrichment.employee_count ? enrichment.employee_count.toLocaleString() : 'N/A'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center">
              <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div>
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tight">Revenue</p>
              <p className="text-xs font-semibold text-slate-700">{enrichment.revenue_printed || 'N/A'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center">
              <Briefcase className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <div>
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tight">Industry</p>
              <p className="text-xs font-semibold text-slate-700 truncate max-w-[80px]">
                {enrichment.industry || 'Unknown'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-slate-100 flex items-center justify-center">
              <MapPin className="w-3.5 h-3.5 text-slate-600" />
            </div>
            <div>
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tight">Location</p>
              <p className="text-xs font-semibold text-slate-700 truncate max-w-[100px]">
                {[enrichment.city, enrichment.state].filter(Boolean).join(', ') || 'N/A'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-amber-50 flex items-center justify-center">
              <Calendar className="w-3.5 h-3.5 text-amber-600" />
            </div>
            <div>
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-tight">Founded</p>
              <p className="text-xs font-semibold text-slate-700">
                {enrichment.founded_year || 'N/A'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Description & Expandable Profile */}
      <div className="flex flex-col gap-2">
        <p className="text-sm text-slate-600 leading-relaxed">
          {prospect.description}
        </p>

        {enrichment && (
          <>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 hover:text-emerald-700 w-fit transition-colors mt-1"
            >
              {isExpanded ? (
                <>
                  <ChevronUp className="w-4 h-4" />
                  Hide Profile
                </>
              ) : (
                <>
                  <ChevronDown className="w-4 h-4" />
                  Show Full Profile
                </>
              )}
            </button>

            {isExpanded && (
              <div className="mt-2 p-3 bg-slate-50 rounded-xl border border-slate-100 animate-in fade-in slide-in-from-top-2 duration-300">
                {enrichment.description && enrichment.description !== prospect.description && (
                  <div className="mb-4">
                    <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5" />
                      About
                    </h5>
                    <p className="text-sm text-slate-600 italic">"{enrichment.description}"</p>
                  </div>
                )}

                {enrichment.technologies && enrichment.technologies.length > 0 && (
                  <div className="mb-4">
                    <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5" />
                      Technologies & Stack
                    </h5>
                    <div className="flex flex-wrap gap-1.5">
                      {enrichment.technologies.slice(0, 15).map((tech, i) => (
                        <span key={i} className="px-2 py-0.5 bg-white border border-slate-200 rounded text-[10px] text-slate-600">
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sub-organizations & Locations */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  {enrichment.suborganizations && enrichment.suborganizations.length > 0 && (
                    <div>
                      <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <Building2 className="w-3.5 h-3.5" />
                        Subsidiaries
                      </h5>
                      <div className="flex flex-col gap-1">
                        {enrichment.suborganizations.slice(0, 5).map((sub, i) => (
                          <span key={i} className="text-xs text-slate-600 truncate">
                            • {sub}
                          </span>
                        ))}
                        {enrichment.suborganizations.length > 5 && (
                          <span className="text-xs text-slate-400 pl-2">
                            +{enrichment.suborganizations.length - 5} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {enrichment.retail_location_count !== undefined && enrichment.retail_location_count > 0 && (
                    <div>
                      <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5" />
                        Retail Presence
                      </h5>
                      <span className="px-2 py-1 bg-amber-50 text-amber-700 rounded text-xs font-semibold border border-amber-100">
                        {enrichment.retail_location_count.toLocaleString()} Locations
                      </span>
                    </div>
                  )}
                </div>

                {/* Classification Codes */}
                {(enrichment.sic_codes?.length || enrichment.naics_codes?.length) && (
                  <div className="mb-4 pt-3 border-t border-slate-100">
                    <div className="flex flex-col gap-2">
                      {enrichment.sic_codes && enrichment.sic_codes.length > 0 && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="font-semibold text-slate-500 w-12">SIC:</span>
                          <div className="flex flex-wrap gap-1">
                            {enrichment.sic_codes.map((code, i) => {
                              // Handle both string and object formats from Apollo API
                              const displayCode = typeof code === 'string'
                                ? code
                                : (code as any)?.code || (code as any)?.name || String(code)
                              return (
                                <span key={i} className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">
                                  {displayCode}
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      )}
                      {enrichment.naics_codes && enrichment.naics_codes.length > 0 && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="font-semibold text-slate-500 w-12">NAICS:</span>
                          <div className="flex flex-wrap gap-1">
                            {enrichment.naics_codes.map((code, i) => {
                              // Handle both string and object formats from Apollo API
                              const displayCode = typeof code === 'string'
                                ? code
                                : (code as any)?.code || (code as any)?.name || String(code)
                              return (
                                <span key={i} className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">
                                  {displayCode}
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}



                {enrichment.linkedin_url && (
                  <div className="mt-4 pt-3 border-t border-slate-200 flex justify-end">
                    <a
                      href={enrichment.linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-xs font-medium text-slate-500 hover:text-blue-600 transition-colors"
                    >
                      <Linkedin className="w-4 h-4" />
                      Company LinkedIn
                    </a>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {!enrichment && !isEnriching && onEnrich && (
          <button
            onClick={handleEnrich}
            className="flex items-center gap-2 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-semibold hover:bg-indigo-100 transition-colors w-fit mt-1"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Enrich with Apollo
          </button>
        )}

        {isEnriching && (
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium mt-1">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Fetching Apollo intelligence...
          </div>
        )}
      </div>
    </div>
  )
}

function ContactItem({
  contact,
  index,
  onSave
}: {
  contact: EnhancedContactSearchResult
  index?: number
  onSave?: (c: EnhancedContactSearchResult) => void
}) {
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    if (onSave) {
      onSave(contact)
      setSaved(true)
    }
  }

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg hover:bg-gray-100 transition-colors group ${index !== undefined && index % 2 === 0 ? 'bg-white' : 'bg-emerald-50/20'}`}>
      <CompanyLogo domain={contact.company_domain} size={40} />
      <div className="flex-1 min-w-0">
        <h4 className="font-medium text-gray-900">{contact.name}</h4>
        {contact.title && (
          <p className="text-sm text-gray-600">{contact.title}</p>
        )}
        {contact.company && (
          <p className="text-sm text-gray-500">{contact.company}</p>
        )}
        <p className="text-xs text-gray-400 line-clamp-2 mt-1">
          {contact.snippet}
        </p>
        {contact.location && (
          <div className="flex items-center gap-1 mt-1">
            <MapPin className="w-3 h-3 text-gray-400" />
            <span className="text-xs text-gray-400">{contact.location}</span>
          </div>
        )}
      </div>
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={handleSave}
          disabled={saved}
          className={`p-1.5 rounded-lg transition-colors ${saved
            ? 'bg-emerald-100 text-emerald-600'
            : 'hover:bg-emerald-50 text-gray-400 hover:text-emerald-600'
            }`}
          title={saved ? 'Saved' : 'Save contact'}
        >
          <Save className="w-4 h-4" />
        </button>
        <a
          href={contact.url}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 hover:bg-blue-50 rounded-lg text-gray-400 hover:text-blue-600 transition-colors"
          title="View profile"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
  )
}

function TriggerEventItem({ event, index }: { event: EnhancedTriggerEventResult, index?: number }) {
  const eventTypeColor = EVENT_TYPE_COLORS[event.event_type || 'other'] || EVENT_TYPE_COLORS.other

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg hover:bg-gray-100 transition-colors group ${index !== undefined && index % 2 === 0 ? 'bg-white' : 'bg-emerald-50/20'}`}>
      {event.logo_url || event.mentioned_company_domain ? (
        <CompanyLogo
          domain={event.mentioned_company_domain}
          logoUrl={event.logo_url}
          size={40}
        />
      ) : (
        <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center flex-shrink-0">
          <Zap className="w-5 h-5 text-emerald-600" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h4 className="font-medium text-gray-900 line-clamp-1">{event.title}</h4>
          {event.event_type && (
            <span className={`px-1.5 py-0.5 text-xs rounded ${eventTypeColor}`}>
              {event.event_type}
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 line-clamp-2 mt-0.5">
          {event.summary}
        </p>
        <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
          {event.mentioned_company && (
            <span className="flex items-center gap-1">
              <Building2 className="w-3 h-3" />
              {event.mentioned_company}
            </span>
          )}
          {event.published_date && (
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {new Date(event.published_date).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
      <a
        href={event.url}
        target="_blank"
        rel="noopener noreferrer"
        className="p-1.5 hover:bg-blue-50 rounded-lg text-gray-400 hover:text-blue-600 transition-colors opacity-0 group-hover:opacity-100"
        title="Read article"
      >
        <ExternalLink className="w-4 h-4" />
      </a>
    </div>
  )
}

// ============================================
// Apollo.io Components
// ============================================

function ApolloEnrichmentItem({ enrichment }: { enrichment: ApolloEnrichmentResult }) {
  return (
    <div className="p-4 bg-gradient-to-br from-indigo-50 to-white rounded-lg border border-indigo-100">
      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        <CompanyLogo domain={enrichment.domain} logoUrl={enrichment.logo_url} size={56} />
        <div className="flex-1">
          <h4 className="text-lg font-semibold text-gray-900">{enrichment.name}</h4>
          <p className="text-sm text-gray-500">{enrichment.domain}</p>
          {enrichment.description && (
            <p className="text-sm text-gray-600 mt-1 line-clamp-2">{enrichment.description}</p>
          )}
        </div>
      </div>

      {/* Key Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {enrichment.employee_count && (
          <div className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center gap-1.5 text-gray-500 text-xs">
              <Users className="w-3 h-3" />
              Employees
            </div>
            <div className="font-semibold text-gray-900 mt-0.5">
              {enrichment.employee_count.toLocaleString()}
            </div>
          </div>
        )}
        {enrichment.revenue_printed && (
          <div className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center gap-1.5 text-gray-500 text-xs">
              <DollarSign className="w-3 h-3" />
              Revenue
            </div>
            <div className="font-semibold text-gray-900 mt-0.5">
              {enrichment.revenue_printed}
            </div>
          </div>
        )}
        {enrichment.founded_year && (
          <div className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center gap-1.5 text-gray-500 text-xs">
              <Calendar className="w-3 h-3" />
              Founded
            </div>
            <div className="font-semibold text-gray-900 mt-0.5">
              {enrichment.founded_year}
            </div>
          </div>
        )}
        <div className="bg-white rounded-lg p-2 border border-gray-100">
          <div className="flex items-center gap-1.5 text-gray-500 text-xs">
            <Briefcase className="w-3 h-3" />
            Industry
          </div>
          <div className="font-semibold text-gray-900 mt-0.5 truncate">
            {enrichment.industry}
          </div>
        </div>
        {enrichment.retail_location_count !== undefined && enrichment.retail_location_count > 0 && (
          <div className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center gap-1.5 text-gray-500 text-xs">
              <MapPin className="w-3 h-3" />
              Retail Locations
            </div>
            <div className="font-semibold text-gray-900 mt-0.5">
              {enrichment.retail_location_count.toLocaleString()}
            </div>
          </div>
        )}
      </div>

      {/* SIC/NAICS Codes - Small strip */}
      {(enrichment.sic_codes?.length || enrichment.naics_codes?.length) && (
        <div className="flex flex-wrap gap-3 mb-4 text-xs">
          {enrichment.sic_codes && enrichment.sic_codes.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-gray-400 font-medium">SIC:</span>
              <div className="flex gap-1">
                {enrichment.sic_codes.slice(0, 3).map((code, i) => (
                  <span key={i} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{code}</span>
                ))}
              </div>
            </div>
          )}
          {enrichment.naics_codes && enrichment.naics_codes.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="text-gray-400 font-medium">NAICS:</span>
              <div className="flex gap-1">
                {enrichment.naics_codes.slice(0, 3).map((code, i) => (
                  <span key={i} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{code}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}


      {/* Location & Links */}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {enrichment.headquarters && (
          <span className="flex items-center gap-1 text-gray-600">
            <MapPin className="w-3.5 h-3.5 text-gray-400" />
            {enrichment.headquarters}
          </span>
        )}
        {enrichment.linkedin_url && (
          <a
            href={enrichment.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-blue-600 hover:text-blue-700"
          >
            <Linkedin className="w-3.5 h-3.5" />
            LinkedIn
          </a>
        )}
        {enrichment.ticker && (
          <span className="flex items-center gap-1 text-gray-600">
            <Hash className="w-3.5 h-3.5 text-gray-400" />
            {enrichment.ticker}
          </span>
        )}
      </div>

      {/* Technologies */}
      {enrichment.technologies && enrichment.technologies.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="text-xs text-gray-500 mb-1.5">Technologies</div>
          <div className="flex flex-wrap gap-1.5">
            {enrichment.technologies.slice(0, 8).map((tech, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
              >
                {tech}
              </span>
            ))}
            {enrichment.technologies.length > 8 && (
              <span className="px-2 py-0.5 text-gray-500 text-xs">
                +{enrichment.technologies.length - 8} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Sub-organizations */}
      {enrichment.suborganizations && enrichment.suborganizations.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="text-xs text-gray-500 mb-1.5 flex items-center gap-1">
            <Building2 className="w-3 h-3" />
            Subsidiaries & Brands
          </div>
          <div className="flex flex-wrap gap-1.5">
            {enrichment.suborganizations.slice(0, 5).map((sub, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-xs rounded border border-indigo-100"
              >
                {sub}
              </span>
            ))}
            {enrichment.suborganizations.length > 5 && (
              <span className="px-2 py-0.5 text-gray-500 text-xs">
                +{enrichment.suborganizations.length - 5} more
              </span>
            )}
          </div>
        </div>
      )}




    </div>
  )
}

function ApolloContactTeaserItem({
  contact,
}: {
  contact: ApolloContactTeaserResult
}) {
  // Build full location string
  const locationParts = [contact.city, contact.state, contact.country].filter(Boolean)
  const fullLocation = contact.location || locationParts.join(', ')

  // Format data freshness
  const formatFreshness = (dateStr?: string) => {
    if (!dateStr) return null
    try {
      const date = new Date(dateStr)
      const now = new Date()
      const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
      if (diffDays < 7) return 'Updated this week'
      if (diffDays < 30) return `Updated ${Math.floor(diffDays / 7)} weeks ago`
      if (diffDays < 90) return `Updated ${Math.floor(diffDays / 30)} months ago`
      return 'Updated 3+ months ago'
    } catch {
      return null
    }
  }

  const freshness = formatFreshness(contact.last_updated)
  const isStale = contact.last_updated && new Date(contact.last_updated) < new Date(Date.now() - 90 * 24 * 60 * 60 * 1000)

  // Department color mapping
  const getDeptColor = (dept: string) => {
    const d = dept.toLowerCase()
    if (d.includes('purchas') || d.includes('procur') || d.includes('supply')) return 'bg-emerald-100 text-emerald-700 border-emerald-200'
    if (d.includes('engineer') || d.includes('technical') || d.includes('r&d')) return 'bg-blue-100 text-blue-700 border-blue-200'
    if (d.includes('exec') || d.includes('c_suite') || d.includes('leadership')) return 'bg-purple-100 text-purple-700 border-purple-200'
    if (d.includes('sales') || d.includes('business')) return 'bg-amber-100 text-amber-700 border-amber-200'
    if (d.includes('operations') || d.includes('manufacturing')) return 'bg-slate-100 text-slate-700 border-slate-200'
    return 'bg-gray-100 text-gray-700 border-gray-200'
  }

  // Determine the display name - prefer revealed full name
  const displayName = contact.name || contact.name_display ||
    `${contact.first_name} ${contact.last_name || contact.last_name_preview || ''}`.trim()

  // Check if we have actual contact info (revealed)
  const hasActualEmail = !!contact.email
  const hasActualPhone = !!contact.phone
  const isRevealed = contact.is_revealed || hasActualEmail || hasActualPhone

  return (
    <div className={`flex items-start gap-3 p-4 bg-white rounded-xl border ${isRevealed ? 'border-emerald-200 bg-gradient-to-r from-emerald-50/30 to-white' : 'border-slate-200'} hover:border-cyan-300 hover:shadow-md transition-all group`}>
      <CompanyLogo domain={contact.company_domain} logoUrl={contact.photo_url || contact.logo_url} size={48} />
      <div className="flex-1 min-w-0">
        {/* Name + Seniority + Verified Badge Row */}
        <div className="flex items-center gap-2 flex-wrap">
          <h4 className="font-semibold text-slate-900">
            {displayName}
          </h4>
          {isRevealed && (
            <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide bg-emerald-100 text-emerald-700 rounded">
              ✓ Verified
            </span>
          )}
          {contact.seniority && (
            <span className="px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-cyan-100 text-cyan-700 rounded-full">
              {contact.seniority}
            </span>
          )}
        </div>

        {/* Title */}
        {contact.title && (
          <p className="text-sm text-slate-600 mt-0.5">{contact.title}</p>
        )}

        {/* Department Badges */}
        {contact.departments && contact.departments.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {contact.departments.slice(0, 3).map((dept, i) => (
              <span
                key={i}
                className={`px-2 py-0.5 text-[10px] font-medium rounded border ${getDeptColor(dept)}`}
              >
                {dept.charAt(0).toUpperCase() + dept.slice(1).replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}

        {/* Company */}
        {contact.company_name && (
          <p className="text-sm text-slate-500 mt-1">{contact.company_name}</p>
        )}

        {/* Revealed Contact Info - Email & Phone */}
        {(hasActualEmail || hasActualPhone) && (
          <div className="flex items-center gap-4 mt-2 text-sm">
            {hasActualEmail && (
              <a
                href={`mailto:${contact.email}`}
                className="flex items-center gap-1.5 text-emerald-700 hover:text-emerald-800 font-medium"
              >
                <Mail className="w-3.5 h-3.5" />
                {contact.email}
                {contact.email_status === 'verified' && (
                  <span className="text-[9px] text-emerald-600">✓</span>
                )}
              </a>
            )}
            {hasActualPhone && (
              <a
                href={`tel:${contact.phone}`}
                className="flex items-center gap-1.5 text-emerald-700 hover:text-emerald-800 font-medium"
              >
                <Phone className="w-3.5 h-3.5" />
                {contact.phone}
              </a>
            )}
          </div>
        )}

        {/* Meta Row: Location, Contact Availability (legacy), Freshness */}
        <div className="flex items-center gap-3 mt-2 text-xs text-slate-400 flex-wrap">
          {fullLocation && (
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              {fullLocation}
            </span>
          )}
          {/* Legacy indicators - only show if no actual data */}
          {!hasActualEmail && contact.has_email && (
            <span className="flex items-center gap-1 text-slate-400">
              <Mail className="w-3 h-3" />
              Email available
            </span>
          )}
          {!hasActualPhone && contact.has_phone && (
            <span className="flex items-center gap-1 text-slate-400">
              <Phone className="w-3 h-3" />
              Phone available
            </span>
          )}
          {freshness && (
            <span className={`flex items-center gap-1 ${isStale ? 'text-amber-500' : 'text-slate-400'}`}>
              <Calendar className="w-3 h-3" />
              {freshness}
            </span>
          )}
        </div>
      </div>

      {/* LinkedIn - always visible now */}
      <div className="flex items-center gap-1 shrink-0">
        {contact.linkedin_url && (
          <a
            href={contact.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 hover:bg-blue-50 rounded-lg text-slate-400 hover:text-blue-600 transition-colors"
            title="View LinkedIn"
          >
            <Linkedin className="w-5 h-5" />
          </a>
        )}
      </div>
    </div>
  )
}

function ApolloContactRevealedItem({ contact }: { contact: ApolloContactRevealedResult }) {
  return (
    <div className="p-4 bg-gradient-to-br from-rose-50 to-white rounded-lg border border-rose-100">
      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        {contact.photo_url ? (
          <img
            src={contact.photo_url}
            alt={contact.name}
            className="w-14 h-14 rounded-full object-cover border-2 border-rose-100"
          />
        ) : (
          <CompanyLogo domain={contact.company_domain} logoUrl={contact.logo_url} size={56} />
        )}
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h4 className="text-lg font-semibold text-gray-900">{contact.name}</h4>
            <span className="px-2 py-0.5 text-xs bg-rose-100 text-rose-700 rounded-full flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              Revealed
            </span>
          </div>
          {contact.title && (
            <p className="text-sm text-gray-600">{contact.title}</p>
          )}
          {contact.company_name && (
            <p className="text-sm text-gray-500">{contact.company_name}</p>
          )}
        </div>
      </div>

      {/* Contact Info - The Good Stuff! */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        {contact.email && (
          <a
            href={`mailto:${contact.email}`}
            className="flex items-center gap-2 p-2.5 bg-white rounded-lg border border-gray-100 hover:border-blue-300 transition-colors group"
          >
            <div className="p-1.5 bg-blue-50 rounded-lg">
              <Mail className="w-4 h-4 text-blue-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-gray-500">Email</div>
              <div className="font-medium text-gray-900 truncate group-hover:text-blue-600">
                {contact.email}
              </div>
              {contact.email_status && (
                <div className="text-xs text-emerald-600">{contact.email_status}</div>
              )}
            </div>
          </a>
        )}
        {contact.phone && (
          <a
            href={`tel:${contact.phone}`}
            className="flex items-center gap-2 p-2.5 bg-white rounded-lg border border-gray-100 hover:border-emerald-300 transition-colors group"
          >
            <div className="p-1.5 bg-emerald-50 rounded-lg">
              <Phone className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-gray-500">Phone</div>
              <div className="font-medium text-gray-900 truncate group-hover:text-emerald-600">
                {contact.phone}
              </div>
            </div>
          </a>
        )}
      </div>

      {/* Links & Location */}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {contact.location && (
          <span className="flex items-center gap-1 text-gray-600">
            <MapPin className="w-3.5 h-3.5 text-gray-400" />
            {contact.location}
          </span>
        )}
        {contact.linkedin_url && (
          <a
            href={contact.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-blue-600 hover:text-blue-700"
          >
            <Linkedin className="w-3.5 h-3.5" />
            LinkedIn
          </a>
        )}
      </div>
    </div>
  )
}

function ApolloCreditStatusItem({ credits }: { credits: ApolloCreditStatus }) {
  const utilizationPct = (credits.used / credits.limit) * 100
  const isLow = credits.remaining < 100
  const isVeryLow = credits.remaining < 25

  return (
    <div className="p-4 bg-gradient-to-br from-slate-50 to-white rounded-lg border border-slate-100">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <CreditCard className="w-5 h-5 text-slate-600" />
          <h4 className="font-semibold text-gray-900">Apollo Credits</h4>
        </div>
        <span className={`px-2 py-0.5 text-xs rounded-full ${isVeryLow ? 'bg-red-100 text-red-700' :
          isLow ? 'bg-emerald-100 text-emerald-700' :
            'bg-emerald-100 text-emerald-700'
          }`}>
          {credits.remaining} remaining
        </span>
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{credits.used} used</span>
          <span>{credits.limit} limit</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${isVeryLow ? 'bg-red-500' :
              isLow ? 'bg-emerald-500' :
                'bg-emerald-500'
              }`}
            style={{ width: `${Math.min(utilizationPct, 100)}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">
          Resets: {credits.reset_date}
        </span>
        <span className={`font-medium ${credits.can_reveal ? 'text-emerald-600' : 'text-red-600'
          }`}>
          {credits.can_reveal ? '✓ Can reveal contacts' : '✕ Credit limit reached'}
        </span>
      </div>
    </div>
  )
}
