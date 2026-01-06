'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  FileText,
  Clock,
  Building2,
  Factory,
  Shield,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  ExternalLink,
  Search,
  Trash2,
  ArrowLeft,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

// ============================================
// Types
// ============================================

interface SavedReport {
  id: string
  query_hash: string
  query: string
  title: string
  executive_summary: string
  data_completeness: string
  overall_confidence: string
  validation_passed: boolean
  citation_count: number
  research_time_seconds: number
  sources_count: number
  companies: string[]
  industries: string[]
  topics: string[]
  user_id?: string
  created_at: string
}

interface SavedReportsPanelProps {
  onOpenReport: (reportId: string) => void
  onContinueResearch: (reportId: string, query: string) => void
  onBack?: () => void
  className?: string
  isExpanded?: boolean
  onToggleExpand?: () => void
}

// ============================================
// Helper functions
// ============================================

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}

function getConfidenceBadge(confidence: string) {
  const lower = confidence?.toLowerCase() || 'unknown'
  if (lower.includes('high')) return { color: 'bg-green-100 text-green-700', label: 'High' }
  if (lower.includes('medium')) return { color: 'bg-amber-100 text-amber-700', label: 'Medium' }
  if (lower.includes('low')) return { color: 'bg-red-100 text-red-700', label: 'Low' }
  return { color: 'bg-slate-100 text-slate-700', label: confidence || 'Unknown' }
}

// ============================================
// Component
// ============================================

export function SavedReportsPanel({
  onOpenReport,
  onContinueResearch,
  onBack,
  className,
  isExpanded = true,
  onToggleExpand,
}: SavedReportsPanelProps) {
  const [reports, setReports] = useState<SavedReport[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedReport, setSelectedReport] = useState<string | null>(null)

  // ============================================
  // Fetch Reports
  // ============================================

  const fetchReports = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getSavedReports({ limit: 20 })
      setReports(data.reports || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchReports()
  }, [fetchReports])

  // ============================================
  // Filter Reports
  // ============================================

  const filteredReports = reports.filter(report => {
    if (!searchQuery.trim()) return true
    const searchLower = searchQuery.toLowerCase()
    return (
      report.query.toLowerCase().includes(searchLower) ||
      report.title?.toLowerCase().includes(searchLower) ||
      report.companies.some(c => c.toLowerCase().includes(searchLower)) ||
      report.industries.some(i => i.toLowerCase().includes(searchLower))
    )
  })

  // ============================================
  // Render
  // ============================================

  // Full page view mode (when onBack is provided)
  const isFullView = !!onBack

  if (isFullView) {
    return (
      <div className={cn('h-full flex flex-col bg-white', className)}>
        {/* Header with back button */}
        <div className="shrink-0 px-6 py-4 border-b border-slate-200 flex items-center gap-4">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-slate-600 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">Back to Research</span>
          </button>
          <div className="flex-1" />
          <h2 className="text-lg font-semibold text-slate-800">Saved Reports</h2>
          <div className="flex-1" />
          <span className="text-sm text-slate-500">{reports.length} reports</span>
        </div>

        {/* Search */}
        <div className="shrink-0 px-6 py-4 border-b border-slate-100">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search reports by query, company, or industry..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Loading State */}
          {loading && (
            <div className="flex items-center justify-center py-12 text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin mr-3" />
              <span className="text-sm">Loading reports...</span>
            </div>
          )}

          {/* Error State */}
          {error && !loading && (
            <div className="flex items-center gap-3 p-4 bg-red-50 text-red-600 rounded-lg">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
              <button onClick={fetchReports} className="ml-auto underline">
                Retry
              </button>
            </div>
          )}

          {/* Empty State */}
          {!loading && !error && filteredReports.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-slate-400">
              <FileText className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-sm">
                {searchQuery ? 'No reports match your search' : 'No saved reports yet'}
              </p>
              <p className="text-xs mt-1">
                {searchQuery ? 'Try a different search term' : 'Run a deep research query to save a report'}
              </p>
            </div>
          )}

          {/* Reports Grid */}
          {!loading && !error && filteredReports.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {filteredReports.map((report) => (
                <ReportCard
                  key={report.id}
                  report={report}
                  isSelected={selectedReport === report.id}
                  onSelect={() => setSelectedReport(selectedReport === report.id ? null : report.id)}
                  onOpen={() => onOpenReport(report.id)}
                  onContinue={() => onContinueResearch(report.id, report.query)}
                  fullView
                />
              ))}
            </div>
          )}
        </div>

        {/* Refresh footer */}
        {!loading && reports.length > 0 && (
          <div className="shrink-0 px-6 py-3 border-t border-slate-100 bg-slate-50">
            <button
              onClick={fetchReports}
              className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh reports
            </button>
          </div>
        )}
      </div>
    )
  }

  // Collapsible sidebar section mode (original)
  return (
    <div className={cn('border-b border-slate-200', className)}>
      {/* Header */}
      <button
        onClick={onToggleExpand}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-slate-500" />
          <span className="font-medium text-slate-700">Saved Reports</span>
          <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
            {reports.length}
          </span>
        </div>
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {/* Content */}
      {isExpanded && (
        <div className="px-3 pb-3">
          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search reports..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-sm bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Loading State */}
          {loading && (
            <div className="flex items-center justify-center py-6 text-slate-400">
              <RefreshCw className="w-4 h-4 animate-spin mr-2" />
              <span className="text-sm">Loading reports...</span>
            </div>
          )}

          {/* Error State */}
          {error && !loading && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
              <button onClick={fetchReports} className="ml-auto underline">
                Retry
              </button>
            </div>
          )}

          {/* Empty State */}
          {!loading && !error && filteredReports.length === 0 && (
            <div className="text-center py-6 text-slate-400">
              <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">
                {searchQuery ? 'No matching reports' : 'No saved reports yet'}
              </p>
              <p className="text-xs">
                {searchQuery ? 'Try a different search' : 'Run a research query to get started'}
              </p>
            </div>
          )}

          {/* Reports List */}
          {!loading && !error && filteredReports.length > 0 && (
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
              {filteredReports.map((report) => (
                <ReportCard
                  key={report.id}
                  report={report}
                  isSelected={selectedReport === report.id}
                  onSelect={() => setSelectedReport(selectedReport === report.id ? null : report.id)}
                  onOpen={() => onOpenReport(report.id)}
                  onContinue={() => onContinueResearch(report.id, report.query)}
                />
              ))}
            </div>
          )}

          {/* Refresh Button */}
          {!loading && reports.length > 0 && (
            <button
              onClick={fetchReports}
              className="mt-3 w-full flex items-center justify-center gap-1.5 py-1.5 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              Refresh
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ============================================
// Report Card Component
// ============================================

interface ReportCardProps {
  report: SavedReport
  isSelected: boolean
  onSelect: () => void
  onOpen: () => void
  onContinue: () => void
  fullView?: boolean
}

function ReportCard({ report, isSelected, onSelect, onOpen, onContinue, fullView = false }: ReportCardProps) {
  const confidenceBadge = getConfidenceBadge(report.overall_confidence)
  
  return (
    <div
      className={cn(
        'rounded-lg border transition-all cursor-pointer',
        isSelected
          ? 'bg-blue-50 border-blue-200'
          : 'bg-white border-slate-200 hover:border-slate-300'
      )}
    >
      {/* Main content - clickable to expand */}
      <div onClick={onSelect} className="p-3">
        {/* Query & Time */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <p className="text-sm font-medium text-slate-800 line-clamp-2">
            {report.query}
          </p>
          <span className="text-xs text-slate-400 whitespace-nowrap flex-shrink-0">
            {formatRelativeTime(report.created_at)}
          </span>
        </div>

        {/* Badges Row */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Confidence */}
          <span className={cn('text-xs px-1.5 py-0.5 rounded', confidenceBadge.color)}>
            {confidenceBadge.label}
          </span>
          
          {/* Validation */}
          {report.validation_passed ? (
            <span className="flex items-center gap-0.5 text-xs text-green-600">
              <CheckCircle className="w-3 h-3" />
              Verified
            </span>
          ) : (
            <span className="flex items-center gap-0.5 text-xs text-amber-600">
              <AlertCircle className="w-3 h-3" />
              Issues
            </span>
          )}
          
          {/* Citations */}
          <span className="text-xs text-slate-500">
            {report.citation_count} citations
          </span>
        </div>

        {/* Companies & Industries Tags */}
        {(report.companies.length > 0 || report.industries.length > 0) && (
          <div className="mt-2 flex items-center gap-1.5 flex-wrap">
            {report.companies.slice(0, 3).map((company) => (
              <span
                key={company}
                className="flex items-center gap-0.5 text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded"
              >
                <Building2 className="w-2.5 h-2.5" />
                {company}
              </span>
            ))}
            {report.companies.length > 3 && (
              <span className="text-xs text-slate-400">+{report.companies.length - 3}</span>
            )}
            {report.industries.slice(0, 2).map((industry) => (
              <span
                key={industry}
                className="flex items-center gap-0.5 text-xs bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded"
              >
                <Factory className="w-2.5 h-2.5" />
                {industry}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Expanded Details */}
      {isSelected && (
        <div className="px-3 pb-3 pt-0 border-t border-slate-100">
          {/* Executive Summary */}
          {report.executive_summary && (
            <p className="text-xs text-slate-600 my-2 line-clamp-3">
              {report.executive_summary}
            </p>
          )}
          
          {/* Stats */}
          <div className="flex items-center gap-4 text-xs text-slate-500 mb-3">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(report.research_time_seconds)}
            </span>
            <span>{report.sources_count} sources</span>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={(e) => { e.stopPropagation(); onOpen(); }}
              className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              View Full Report
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onContinue(); }}
              className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium rounded hover:bg-slate-200 transition-colors"
            >
              Continue Research
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default SavedReportsPanel
