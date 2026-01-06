'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Target,
  Ban,
  Plus,
  Trash2,
  AlertCircle,
  RefreshCw,
  Globe,
  Users,
  Sparkles,
  CheckCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

// ============================================
// Types
// ============================================

interface Preference {
  id: string
  target: string
  description?: string
  team?: string | null  // null = org-wide
}

interface Preferences {
  priorities: Preference[]
  blocks: Preference[]
}

interface PreferencesPanelProps {
  className?: string
}

// ============================================
// Constants
// ============================================

const TEAMS = ['Sales East', 'Sales West', 'Marketing', 'Product/Supplier', 'All Others']

// ============================================
// Component
// ============================================

export function PreferencesPanel({ className }: PreferencesPanelProps) {
  const [preferences, setPreferences] = useState<Preferences>({ priorities: [], blocks: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Add form state
  const [isAdding, setIsAdding] = useState<'priority' | 'block' | null>(null)
  const [newTarget, setNewTarget] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newScope, setNewScope] = useState<'org' | 'team'>('org')
  const [submitting, setSubmitting] = useState(false)
  const [addSuccess, setAddSuccess] = useState(false)

  const userTeam = typeof window !== 'undefined' 
    ? localStorage.getItem('userTeam') || 'All Others' 
    : 'All Others'

  // ============================================
  // Data Fetching
  // ============================================

  const fetchPreferences = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getPreferences()
      setPreferences(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preferences')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPreferences()
  }, [fetchPreferences])

  // ============================================
  // Add Preference
  // ============================================

  const handleAdd = async () => {
    if (!newTarget.trim() || !isAdding) return
    
    setSubmitting(true)
    setError(null)
    
    try {
      await api.addPreference({
        type: isAdding === 'priority' ? 'prioritize' : 'block',
        target: newTarget.trim(),
        description: newDescription.trim() || undefined,
        team: newScope === 'team' ? userTeam : undefined,
      })
      
      // Show success briefly
      setAddSuccess(true)
      setTimeout(() => setAddSuccess(false), 2000)
      
      // Reset form
      setNewTarget('')
      setNewDescription('')
      setIsAdding(null)
      
      // Refresh list
      fetchPreferences()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add preference')
    } finally {
      setSubmitting(false)
    }
  }

  // ============================================
  // Remove Preference
  // ============================================

  const handleRemove = async (preferenceId: string) => {
    try {
      await api.removePreference(preferenceId)
      fetchPreferences()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove preference')
    }
  }

  // ============================================
  // Render
  // ============================================

  if (loading) {
    return (
      <div className={cn('flex items-center justify-center py-12', className)}>
        <RefreshCw className="w-5 h-5 text-slate-400 animate-spin" />
        <span className="ml-2 text-slate-500">Loading preferences...</span>
      </div>
    )
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Intelligence Preferences</h2>
          <p className="text-sm text-slate-500">
            Configure what topics the AI should prioritize or de-emphasize
          </p>
        </div>
        <button
          onClick={fetchPreferences}
          className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* Success Banner */}
      {addSuccess && (
        <div className="flex items-center gap-2 p-3 bg-green-50 text-green-700 rounded-lg">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm">Preference added successfully!</span>
        </div>
      )}

      {/* Priority Topics Section */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 bg-emerald-50 border-b border-emerald-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-emerald-600" />
            <h3 className="font-medium text-emerald-900">Priority Topics</h3>
          </div>
          <span className="text-xs text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded-full">
            {preferences.priorities.length} active
          </span>
        </div>
        
        <div className="p-4">
          <p className="text-sm text-slate-500 mb-4">
            The AI will highlight and pay special attention to insights about these topics.
          </p>
          
          {/* Priority List */}
          <div className="space-y-2 mb-4">
            {preferences.priorities.map((pref) => (
              <PreferenceItem
                key={pref.id}
                preference={pref}
                type="priority"
                onRemove={() => handleRemove(pref.id)}
              />
            ))}
            
            {preferences.priorities.length === 0 && !isAdding && (
              <div className="text-center py-6 text-slate-400">
                <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No priority topics set</p>
                <p className="text-xs">Add topics you want the AI to focus on</p>
              </div>
            )}
          </div>
          
          {/* Add Priority Form */}
          {isAdding === 'priority' ? (
            <AddPreferenceForm
              target={newTarget}
              description={newDescription}
              scope={newScope}
              userTeam={userTeam}
              onTargetChange={setNewTarget}
              onDescriptionChange={setNewDescription}
              onScopeChange={setNewScope}
              onSubmit={handleAdd}
              onCancel={() => { setIsAdding(null); setNewTarget(''); setNewDescription(''); }}
              submitting={submitting}
              type="priority"
            />
          ) : (
            <button
              onClick={() => setIsAdding('priority')}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 border-2 border-dashed border-emerald-200 text-emerald-600 rounded-lg hover:bg-emerald-50 hover:border-emerald-300 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Priority Topic
            </button>
          )}
        </div>
      </div>

      {/* Blocked Topics Section */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 bg-amber-50 border-b border-amber-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ban className="w-5 h-5 text-amber-600" />
            <h3 className="font-medium text-amber-900">De-prioritized Topics</h3>
          </div>
          <span className="text-xs text-amber-600 bg-amber-100 px-2 py-0.5 rounded-full">
            {preferences.blocks.length} active
          </span>
        </div>
        
        <div className="p-4">
          <p className="text-sm text-slate-500 mb-4">
            The AI will soft-filter these topics — they&apos;ll appear less prominently but won&apos;t be completely hidden.
          </p>
          
          {/* Block List */}
          <div className="space-y-2 mb-4">
            {preferences.blocks.map((pref) => (
              <PreferenceItem
                key={pref.id}
                preference={pref}
                type="block"
                onRemove={() => handleRemove(pref.id)}
              />
            ))}
            
            {preferences.blocks.length === 0 && isAdding !== 'block' && (
              <div className="text-center py-6 text-slate-400">
                <Ban className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No de-prioritized topics</p>
                <p className="text-xs">Add topics you want to see less of</p>
              </div>
            )}
          </div>
          
          {/* Add Block Form */}
          {isAdding === 'block' ? (
            <AddPreferenceForm
              target={newTarget}
              description={newDescription}
              scope={newScope}
              userTeam={userTeam}
              onTargetChange={setNewTarget}
              onDescriptionChange={setNewDescription}
              onScopeChange={setNewScope}
              onSubmit={handleAdd}
              onCancel={() => { setIsAdding(null); setNewTarget(''); setNewDescription(''); }}
              submitting={submitting}
              type="block"
            />
          ) : (
            <button
              onClick={() => setIsAdding('block')}
              className="w-full flex items-center justify-center gap-2 py-2 px-4 border-2 border-dashed border-amber-200 text-amber-600 rounded-lg hover:bg-amber-50 hover:border-amber-300 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add De-prioritized Topic
            </button>
          )}
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 rounded-lg p-4">
        <h4 className="text-sm font-medium text-blue-900 mb-1">How preferences work</h4>
        <ul className="text-sm text-blue-700 space-y-1">
          <li>• <strong>Priority topics</strong> get boosted in briefings and research</li>
          <li>• <strong>De-prioritized topics</strong> are soft-filtered (0.3× relevance penalty)</li>
          <li>• Org-wide settings apply to all users; team settings only affect your team</li>
          <li>• Changes take effect immediately on new queries</li>
        </ul>
      </div>
    </div>
  )
}

// ============================================
// Sub-components
// ============================================

interface PreferenceItemProps {
  preference: Preference
  type: 'priority' | 'block'
  onRemove: () => void
}

function PreferenceItem({ preference, type, onRemove }: PreferenceItemProps) {
  const isOrgWide = !preference.team
  
  return (
    <div className={cn(
      'flex items-center justify-between px-4 py-3 rounded-lg',
      type === 'priority' ? 'bg-emerald-50' : 'bg-amber-50'
    )}>
      <div className="flex items-center gap-3 flex-1">
        <div className={cn(
          'w-2 h-2 rounded-full flex-shrink-0',
          type === 'priority' ? 'bg-emerald-500' : 'bg-amber-500'
        )} />
        
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-800">{preference.target}</span>
            {isOrgWide ? (
              <span className="flex items-center gap-1 text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                <Globe className="w-3 h-3" />
                Org-wide
              </span>
            ) : (
              <span className="flex items-center gap-1 text-xs text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded">
                <Users className="w-3 h-3" />
                {preference.team}
              </span>
            )}
          </div>
          {preference.description && (
            <p className="text-sm text-slate-500 truncate">{preference.description}</p>
          )}
        </div>
      </div>
      
      <button
        onClick={onRemove}
        className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
        title="Remove"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  )
}

interface AddPreferenceFormProps {
  target: string
  description: string
  scope: 'org' | 'team'
  userTeam: string
  onTargetChange: (v: string) => void
  onDescriptionChange: (v: string) => void
  onScopeChange: (v: 'org' | 'team') => void
  onSubmit: () => void
  onCancel: () => void
  submitting: boolean
  type: 'priority' | 'block'
}

function AddPreferenceForm({
  target,
  description,
  scope,
  userTeam,
  onTargetChange,
  onDescriptionChange,
  onScopeChange,
  onSubmit,
  onCancel,
  submitting,
  type,
}: AddPreferenceFormProps) {
  return (
    <div className={cn(
      'p-4 rounded-lg border-2',
      type === 'priority' ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'
    )}>
      <div className="space-y-3">
        {/* Topic Input */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Topic or Entity
          </label>
          <input
            type="text"
            value={target}
            onChange={(e) => onTargetChange(e.target.value)}
            placeholder={type === 'priority' ? 'e.g., "resin pricing", "AOC", "aerospace"' : 'e.g., "Acme Corp", "plastics"'}
            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            autoFocus
          />
        </div>
        
        {/* Description Input */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Description <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            placeholder="Why is this important?"
            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        
        {/* Scope Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Apply to
          </label>
          <div className="flex gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="scope"
                checked={scope === 'org'}
                onChange={() => onScopeChange('org')}
                className="text-blue-600 focus:ring-blue-500"
              />
              <span className="flex items-center gap-1 text-sm text-slate-700">
                <Globe className="w-4 h-4" />
                Entire organization
              </span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="scope"
                checked={scope === 'team'}
                onChange={() => onScopeChange('team')}
                className="text-blue-600 focus:ring-blue-500"
              />
              <span className="flex items-center gap-1 text-sm text-slate-700">
                <Users className="w-4 h-4" />
                {userTeam} only
              </span>
            </label>
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            disabled={!target.trim() || submitting}
            className={cn(
              'px-4 py-2 text-white rounded-lg transition-colors flex items-center gap-2',
              type === 'priority' 
                ? 'bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300' 
                : 'bg-amber-600 hover:bg-amber-700 disabled:bg-amber-300'
            )}
          >
            {submitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Adding...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" />
                Add {type === 'priority' ? 'Priority' : 'De-priority'}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default PreferencesPanel
