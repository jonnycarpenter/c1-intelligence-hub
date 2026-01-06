'use client'

import { useState, useCallback } from 'react'
import { 
  Building2, 
  Beaker, 
  Factory, 
  Settings2, 
  History, 
  Plus, 
  Trash2, 
  Search,
  Filter,
  Download,
  RefreshCw,
  ChevronRight,
  X,
  User,
  Clock,
  AlertCircle,
  CheckCircle2,
  Bookmark
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { MemoryLog, PreferencesPanel } from '@/components/memory'
import {
  useDataSummary,
  useTrackedCompanies,
  useTrackedMaterials,
  useTrackedIndustries,
  useUserPreferences,
  useChangeLog,
  type TrackedCompany,
  type TrackedMaterial,
  type TrackedIndustry,
  type ChangeLogEntry,
} from '@/hooks/useDataPreferences'

type TabId = 'companies' | 'materials' | 'industries' | 'preferences' | 'memory' | 'changelog'
type ViewMode = 'live' | 'changelog'

interface Tab {
  id: TabId
  label: string
  icon: typeof Building2
  color: string
  description: string
}

const tabs: Tab[] = [
  { id: 'companies', label: 'Companies', icon: Building2, color: 'text-emerald-500', description: 'Tracked companies & competitors' },
  { id: 'materials', label: 'Materials', icon: Beaker, color: 'text-blue-500', description: 'Materials & processes' },
  { id: 'industries', label: 'Industries', icon: Factory, color: 'text-purple-500', description: 'Industry verticals' },
  { id: 'preferences', label: 'Preferences', icon: Settings2, color: 'text-amber-500', description: 'User preferences & exclusions' },
  { id: 'memory', label: 'Memory', icon: Bookmark, color: 'text-orange-500', description: 'Saved briefings & research' },
  { id: 'changelog', label: 'Change Log', icon: History, color: 'text-slate-500', description: 'History of all changes' },
]

// ============================================
// Add Item Modal
// ============================================

interface AddItemModalProps {
  isOpen: boolean
  onClose: () => void
  itemType: 'company' | 'material' | 'industry' | 'preference'
  onSubmit: (name: string, userName: string, extra?: Record<string, string>) => Promise<void>
  types?: string[]
}

function AddItemModal({ isOpen, onClose, itemType, onSubmit, types }: AddItemModalProps) {
  const [name, setName] = useState('')
  const [userName, setUserName] = useState('')
  const [selectedType, setSelectedType] = useState('')
  const [ticker, setTicker] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !userName.trim()) {
      setError('Name and your name are required')
      return
    }
    
    try {
      setIsSubmitting(true)
      setError('')
      await onSubmit(name.trim(), userName.trim(), { type: selectedType, ticker })
      setName('')
      setUserName('')
      setSelectedType('')
      setTicker('')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add item')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">
            Add {itemType.charAt(0).toUpperCase() + itemType.slice(1)}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={20} />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 px-3 py-2 rounded-lg">
              <AlertCircle size={16} />
              {error}
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {itemType === 'preference' ? 'Preference/Exclusion' : `${itemType.charAt(0).toUpperCase() + itemType.slice(1)} Name`}
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={itemType === 'preference' ? "e.g., Don't show cultured marble insights" : `Enter ${itemType} name`}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
              autoFocus
            />
          </div>

          {itemType === 'company' && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Stock Ticker (optional)
                </label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="e.g., HXL"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                />
              </div>
              {types && types.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
                  <select
                    value={selectedType}
                    onChange={(e) => setSelectedType(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  >
                    <option value="">Select type...</option>
                    {types.map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}

          {itemType === 'material' && types && types.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
              >
                <option value="">Select type...</option>
                {types.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          )}

          <div className="pt-2 border-t border-slate-200">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Your Name <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-2">
              <User size={16} className="text-slate-400" />
              <input
                type="text"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                placeholder="First name, Last initial (e.g., John D.)"
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
              />
            </div>
            <p className="text-xs text-slate-500 mt-1">Required for accountability</p>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? 'Adding...' : 'Add'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ============================================
// Remove Confirmation Modal
// ============================================

interface RemoveModalProps {
  isOpen: boolean
  onClose: () => void
  itemName: string
  itemType: string
  onConfirm: (userName: string) => Promise<void>
}

function RemoveModal({ isOpen, onClose, itemName, itemType, onConfirm }: RemoveModalProps) {
  const [userName, setUserName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleConfirm = async () => {
    if (!userName.trim()) {
      setError('Your name is required')
      return
    }
    
    try {
      setIsSubmitting(true)
      setError('')
      await onConfirm(userName.trim())
      setUserName('')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove item')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">Confirm Removal</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={20} />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 px-3 py-2 rounded-lg">
              <AlertCircle size={16} />
              {error}
            </div>
          )}
          
          <p className="text-slate-600">
            Are you sure you want to remove <strong>{itemName}</strong> from the {itemType} list?
          </p>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Your Name <span className="text-red-500">*</span>
            </label>
            <div className="flex items-center gap-2">
              <User size={16} className="text-slate-400" />
              <input
                type="text"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                placeholder="First name, Last initial (e.g., John D.)"
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                autoFocus
              />
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? 'Removing...' : 'Remove'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================
// Main Dashboard Component
// ============================================

interface DataPreferencesDashboardProps {
  onAskAgent?: (message: string) => void
}

export default function DataPreferencesDashboard({ onAskAgent }: DataPreferencesDashboardProps) {
  const [activeTab, setActiveTab] = useState<TabId>('companies')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<string>('')
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [removeModal, setRemoveModal] = useState<{ isOpen: boolean; name: string; type: string } | null>(null)

  // Data hooks
  const { summary, refresh: refreshSummary } = useDataSummary()
  const { companies, types: companyTypes, fetchCompanies, addCompany, removeCompany, isLoading: companiesLoading } = useTrackedCompanies()
  const { materials, types: materialTypes, fetchMaterials, addMaterial, removeMaterial, isLoading: materialsLoading } = useTrackedMaterials()
  const { industries, fetchIndustries, addIndustry, removeIndustry, isLoading: industriesLoading } = useTrackedIndustries()
  const { preferences, updatePreference, isLoading: prefsLoading } = useUserPreferences()
  const { changes, fetchChanges, isLoading: changelogLoading } = useChangeLog()

  // Search handler
  const handleSearch = useCallback(() => {
    switch (activeTab) {
      case 'companies':
        fetchCompanies({ search: searchQuery, type: selectedType })
        break
      case 'materials':
        fetchMaterials({ search: searchQuery, type: selectedType })
        break
      case 'industries':
        fetchIndustries({ search: searchQuery })
        break
      case 'changelog':
        fetchChanges({ category: selectedType || undefined })
        break
    }
  }, [activeTab, searchQuery, selectedType, fetchCompanies, fetchMaterials, fetchIndustries, fetchChanges])

  // Refresh all data
  const handleRefresh = useCallback(() => {
    refreshSummary()
    handleSearch()
  }, [refreshSummary, handleSearch])

  // Add handlers
  const handleAddCompany = async (name: string, userName: string, extra?: Record<string, string>) => {
    await addCompany(name, userName, extra?.type, extra?.ticker)
    refreshSummary()
  }

  const handleAddMaterial = async (name: string, userName: string, extra?: Record<string, string>) => {
    await addMaterial(name, userName, extra?.type)
    refreshSummary()
  }

  const handleAddIndustry = async (name: string, userName: string) => {
    await addIndustry(name, userName)
    refreshSummary()
  }

  const handleAddPreference = async (value: string, userName: string) => {
    await updatePreference('add', 'global_exclusions', value, userName)
    refreshSummary()
  }

  // Remove handlers
  const handleRemoveCompany = async (userName: string) => {
    if (removeModal?.name) {
      await removeCompany(removeModal.name, userName)
      refreshSummary()
    }
  }

  const handleRemoveMaterial = async (userName: string) => {
    if (removeModal?.name) {
      await removeMaterial(removeModal.name, userName)
      refreshSummary()
    }
  }

  const handleRemoveIndustry = async (userName: string) => {
    if (removeModal?.name) {
      await removeIndustry(removeModal.name, userName)
      refreshSummary()
    }
  }

  const handleRemovePreference = async (userName: string) => {
    if (removeModal?.name) {
      await updatePreference('remove', 'global_exclusions', removeModal.name, userName)
      refreshSummary()
    }
  }

  // Get current add handler
  const getCurrentAddHandler = () => {
    switch (activeTab) {
      case 'companies': return handleAddCompany
      case 'materials': return handleAddMaterial
      case 'industries': return handleAddIndustry
      case 'preferences': return handleAddPreference
      default: return async () => {}
    }
  }

  // Get current remove handler
  const getCurrentRemoveHandler = () => {
    switch (removeModal?.type) {
      case 'company': return handleRemoveCompany
      case 'material': return handleRemoveMaterial
      case 'industry': return handleRemoveIndustry
      case 'preference': return handleRemovePreference
      default: return async () => {}
    }
  }

  // Get current types for filter
  const getCurrentTypes = () => {
    switch (activeTab) {
      case 'companies': return companyTypes
      case 'materials': return materialTypes
      case 'changelog': return ['company', 'material', 'industry', 'preference', 'system']
      default: return []
    }
  }

  const isLoading = companiesLoading || materialsLoading || industriesLoading || prefsLoading || changelogLoading

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Data & Preferences</h1>
            <p className="text-sm text-slate-500">Manage tracked companies, materials, industries and user preferences</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              className="flex items-center gap-2 px-3 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              onClick={() => window.open('/api/data-preferences/export?data_type=' + activeTab, '_blank')}
              className="flex items-center gap-2 px-3 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <Download size={16} />
              Export
            </button>
          </div>
        </div>

        {/* Summary cards */}
        {summary && (
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="bg-emerald-50 rounded-lg px-4 py-3">
              <div className="text-2xl font-bold text-emerald-600">{summary.companies.total}</div>
              <div className="text-sm text-emerald-700">Companies</div>
            </div>
            <div className="bg-blue-50 rounded-lg px-4 py-3">
              <div className="text-2xl font-bold text-blue-600">{summary.materials.total}</div>
              <div className="text-sm text-blue-700">Materials</div>
            </div>
            <div className="bg-purple-50 rounded-lg px-4 py-3">
              <div className="text-2xl font-bold text-purple-600">{summary.industries.total}</div>
              <div className="text-sm text-purple-700">Industries</div>
            </div>
            <div className="bg-amber-50 rounded-lg px-4 py-3">
              <div className="text-2xl font-bold text-amber-600">{summary.change_log.total_changes}</div>
              <div className="text-sm text-amber-700">Changes Logged</div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200 -mb-4">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id)
                  setSearchQuery('')
                  setSelectedType('')
                }}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px',
                  isActive
                    ? 'border-amber-500 text-amber-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700'
                )}
              >
                <Icon size={16} className={isActive ? tab.color : ''} />
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Search and Filter bar */}
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-4">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder={`Search ${activeTab}...`}
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
        </div>
        
        {getCurrentTypes().length > 0 && (
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-slate-400" />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
            >
              <option value="">All types</option>
              {getCurrentTypes().map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        )}

        <button
          onClick={handleSearch}
          className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
        >
          Search
        </button>

        {activeTab !== 'changelog' && (
          <button
            onClick={() => setAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 transition-colors"
          >
            <Plus size={16} />
            Add {activeTab === 'preferences' ? 'Preference' : activeTab.slice(0, -1)}
          </button>
        )}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-auto p-6">
        {/* Companies Tab */}
        {activeTab === 'companies' && (
          <div className="grid gap-3">
            {companies.map((company) => (
              <CompanyCard
                key={company.company_id}
                company={company}
                onRemove={() => setRemoveModal({ isOpen: true, name: company.company, type: 'company' })}
                onAskAgent={onAskAgent}
              />
            ))}
            {companies.length === 0 && !companiesLoading && (
              <EmptyState message="No companies found" />
            )}
          </div>
        )}

        {/* Materials Tab */}
        {activeTab === 'materials' && (
          <div className="grid gap-3">
            {materials.map((material) => (
              <MaterialCard
                key={material.material_proc_id}
                material={material}
                onRemove={() => setRemoveModal({ isOpen: true, name: material.material_process_name, type: 'material' })}
                onAskAgent={onAskAgent}
              />
            ))}
            {materials.length === 0 && !materialsLoading && (
              <EmptyState message="No materials found" />
            )}
          </div>
        )}

        {/* Industries Tab */}
        {activeTab === 'industries' && (
          <div className="grid gap-3">
            {industries.map((industry) => (
              <IndustryCard
                key={industry.industry_id}
                industry={industry}
                onRemove={() => setRemoveModal({ isOpen: true, name: industry.industry_name, type: 'industry' })}
                onAskAgent={onAskAgent}
              />
            ))}
            {industries.length === 0 && !industriesLoading && (
              <EmptyState message="No industries found" />
            )}
          </div>
        )}

        {/* Preferences Tab */}
        {activeTab === 'preferences' && preferences && (
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-medium text-slate-700 mb-3">Global Exclusions</h3>
              <div className="grid gap-2">
                {preferences.global_exclusions.map((excl) => (
                  <div
                    key={excl.id}
                    className="flex items-center justify-between bg-white rounded-lg px-4 py-3 border border-slate-200"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-amber-500" />
                      <span className="text-slate-700">{excl.value}</span>
                    </div>
                    <button
                      onClick={() => setRemoveModal({ isOpen: true, name: excl.value, type: 'preference' })}
                      className="text-slate-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                {preferences.global_exclusions.length === 0 && (
                  <EmptyState message="No exclusions configured" />
                )}
              </div>
            </div>
          </div>
        )}

        {/* Memory Tab */}
        {activeTab === 'memory' && (
          <MemoryLog />
        )}

        {/* Change Log Tab */}
        {activeTab === 'changelog' && (
          <div className="space-y-3">
            {changes.map((change) => (
              <ChangeLogCard key={change.id} change={change} />
            ))}
            {changes.length === 0 && !changelogLoading && (
              <EmptyState message="No changes recorded yet" />
            )}
          </div>
        )}
      </div>

      {/* Add Modal */}
      <AddItemModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        itemType={activeTab === 'preferences' ? 'preference' : activeTab.slice(0, -1) as 'company' | 'material' | 'industry'}
        onSubmit={getCurrentAddHandler()}
        types={activeTab === 'companies' ? companyTypes : activeTab === 'materials' ? materialTypes : undefined}
      />

      {/* Remove Modal */}
      {removeModal && (
        <RemoveModal
          isOpen={removeModal.isOpen}
          onClose={() => setRemoveModal(null)}
          itemName={removeModal.name}
          itemType={removeModal.type}
          onConfirm={getCurrentRemoveHandler()}
        />
      )}
    </div>
  )
}

// ============================================
// Card Components
// ============================================

function CompanyCard({ company, onRemove, onAskAgent }: { company: TrackedCompany; onRemove: () => void; onAskAgent?: (msg: string) => void }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-slate-900">{company.company}</h3>
            {company.stock_ticker && (
              <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">{company.stock_ticker}</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded">{company.type}</span>
            {company.industries_served && (
              <span className="text-xs text-slate-500">{company.industries_served.split('|').slice(0, 3).join(', ')}</span>
            )}
          </div>
          {company.description && (
            <p className="text-sm text-slate-500 mt-2 line-clamp-2">{company.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {onAskAgent && (
            <button
              onClick={() => onAskAgent(`Tell me about ${company.company}`)}
              className="text-slate-400 hover:text-amber-500 transition-colors"
              title="Ask agent about this company"
            >
              <ChevronRight size={18} />
            </button>
          )}
          <button
            onClick={onRemove}
            className="text-slate-400 hover:text-red-500 transition-colors"
            title="Remove company"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function MaterialCard({ material, onRemove, onAskAgent }: { material: TrackedMaterial; onRemove: () => void; onAskAgent?: (msg: string) => void }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-medium text-slate-900">{material.material_process_name}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">{material.type}</span>
            <span className={cn(
              'px-2 py-0.5 text-xs rounded',
              material.est_manufacturer_margin_tier === 'HIGH' ? 'bg-green-100 text-green-700' :
              material.est_manufacturer_margin_tier === 'MEDIUM' ? 'bg-yellow-100 text-yellow-700' :
              'bg-slate-100 text-slate-600'
            )}>
              {material.est_manufacturer_margin_tier} margin
            </span>
          </div>
          {material.industries_served && (
            <p className="text-xs text-slate-500 mt-2">Industries: {material.industries_served.split('|').join(', ')}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {onAskAgent && (
            <button
              onClick={() => onAskAgent(`Tell me about ${material.material_process_name}`)}
              className="text-slate-400 hover:text-amber-500 transition-colors"
              title="Ask agent about this material"
            >
              <ChevronRight size={18} />
            </button>
          )}
          <button
            onClick={onRemove}
            className="text-slate-400 hover:text-red-500 transition-colors"
            title="Remove material"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function IndustryCard({ industry, onRemove, onAskAgent }: { industry: TrackedIndustry; onRemove: () => void; onAskAgent?: (msg: string) => void }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-medium text-slate-900">{industry.industry_name}</h3>
          {industry.description && (
            <p className="text-sm text-slate-500 mt-1 line-clamp-2">{industry.description}</p>
          )}
          <div className="flex flex-wrap gap-1 mt-2">
            {industry.key_materials && industry.key_materials.split('|').slice(0, 4).map(mat => (
              <span key={mat} className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">{mat}</span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onAskAgent && (
            <button
              onClick={() => onAskAgent(`Tell me about the ${industry.industry_name} industry`)}
              className="text-slate-400 hover:text-amber-500 transition-colors"
              title="Ask agent about this industry"
            >
              <ChevronRight size={18} />
            </button>
          )}
          <button
            onClick={onRemove}
            className="text-slate-400 hover:text-red-500 transition-colors"
            title="Remove industry"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function ChangeLogCard({ change }: { change: ChangeLogEntry }) {
  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'company': return 'bg-emerald-100 text-emerald-700'
      case 'material': return 'bg-blue-100 text-blue-700'
      case 'industry': return 'bg-purple-100 text-purple-700'
      case 'preference': return 'bg-amber-100 text-amber-700'
      default: return 'bg-slate-100 text-slate-700'
    }
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            {change.status === 'success' ? (
              <CheckCircle2 size={16} className="text-green-500" />
            ) : (
              <AlertCircle size={16} className="text-red-500" />
            )}
            <span className="font-medium text-slate-900">{change.description}</span>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className={cn('px-2 py-0.5 text-xs rounded', getCategoryColor(change.category))}>
              {change.category}
            </span>
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <User size={12} />
              {change.user_name}
            </span>
            <span className="text-xs text-slate-400 flex items-center gap-1">
              <Clock size={12} />
              {new Date(change.timestamp).toLocaleString()}
            </span>
          </div>
          {(change.previous_value || change.new_value) && (
            <div className="mt-2 text-xs text-slate-500">
              {change.previous_value && <span className="line-through text-red-500 mr-2">{change.previous_value}</span>}
              {change.new_value && <span className="text-green-600">{change.new_value}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-12 text-slate-500">
      <p>{message}</p>
    </div>
  )
}
