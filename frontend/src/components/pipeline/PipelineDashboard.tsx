'use client'

import { useState, useRef, useEffect } from 'react'
import {
  Send,
  Building2,
  Users,
  Bookmark,
  Download,
  ExternalLink,
  Loader2,
  AlertCircle,
  X,
  Sparkles,
  MessageSquare,
  Zap,
  ChevronRight,
  Trash2,
  ListChecks,
  Search,
} from 'lucide-react'
import { Button, MarkdownContent } from '@/components/ui'
import { cn } from '@/lib/utils'
import { usePipeline } from '@/hooks'
import { SearchBlockCard } from './SearchBlockCard'
import type {
  PipelineProspect,
  PipelineContact,
  EnhancedProspectSearchResult,
  EnhancedContactSearchResult,
} from '@/types'

// View modes for the right panel
type RightPanelView = 'results' | 'saved'

export default function PipelineDashboard() {
  const [rightPanelView, setRightPanelView] = useState<RightPanelView>('results')
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Pipeline hook with agent support
  const {
    // Pipeline mode
    pipelineMode,
    setPipelineMode,
    // Agent state
    isAgentThinking,
    agentError,
    conversationHistory,
    searchBlocks,
    suggestedFollowups,

    sendAgentMessage,
    clearConversation,
    toggleBlockExpansion,
    removeSearchBlock,
    // Saved data
    savedProspects,
    savedContacts,
    saveProspect,
    removeProspect,
    updateProspect,
    saveContact,
    removeContact,
    enrichProspect,
    enrichCompany,
    exportProspectsToCSV,
    exportContactsToCSV,
  } = usePipeline()

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversationHistory])

  // Handle sending a message
  const handleSend = async () => {
    if (!inputValue.trim() || isAgentThinking) return

    const message = inputValue.trim()
    setInputValue('')

    // Switch to results view when sending a message
    setRightPanelView('results')

    await sendAgentMessage(message)
  }

  // Handle suggested followup click
  const handleFollowupClick = (followup: string) => {
    setInputValue(followup)
    inputRef.current?.focus()
  }

  // Handle saving prospect from search block
  const handleSaveProspect = (prospect: EnhancedProspectSearchResult) => {
    saveProspect(prospect)
  }

  // Handle saving contact from search block
  const handleSaveContact = (contact: EnhancedContactSearchResult) => {
    saveContact(contact)
  }

  const hasSearchBlocks = searchBlocks.length > 0
  const hasConversation = conversationHistory.length > 0

  return (
    <div className="h-full flex flex-col overflow-hidden bg-slate-200 p-4 gap-4">
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Left Panel - Chat Interface */}
        <div className="w-[400px] shrink-0 flex flex-col bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-100/60">
          {/* Header */}
          <div className="shrink-0 px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-emerald-50 to-white">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold text-slate-800">Pipeline Agent</h1>
                  <p className="text-xs text-slate-500">AI-powered prospect discovery</p>
                </div>
              </div>
              {hasConversation && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearConversation}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <Trash2 size={14} />
                  Clear
                </Button>
              )}
            </div>

            {/* Mode Toggle */}
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setPipelineMode('instant')}
                className={cn(
                  'flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5',
                  pipelineMode === 'instant'
                    ? 'bg-white text-emerald-700 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                <Search size={12} />
                Quick Search
              </button>
              <button
                onClick={() => setPipelineMode('full')}
                className={cn(
                  'flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center justify-center gap-1.5',
                  pipelineMode === 'full'
                    ? 'bg-white text-emerald-700 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                <ListChecks size={12} />
                Full List
              </button>
            </div>
            {pipelineMode === 'full' && (
              <p className="text-xs text-emerald-600 mt-2">
                Full List mode can build enriched company lists (1-5 min). Type &quot;CONFIRM&quot; to start.
              </p>
            )}
          </div>

          {/* Chat Messages Area */}
          <div className="flex-1 overflow-auto p-6">
            {!hasConversation ? (
              // Empty state - show suggestions
              <div className="h-full flex flex-col items-center justify-center text-center px-4">
                <div className="w-16 h-16 rounded-2xl bg-emerald-100 flex items-center justify-center mb-4">
                  <MessageSquare className="w-8 h-8 text-emerald-600" />
                </div>
                <h2 className="text-xl font-semibold text-slate-800 mb-2">
                  Ask me anything about prospects
                </h2>
                <p className="text-sm text-slate-500 mb-6 max-w-md">
                  I can find similar companies, search by description, locate decision makers,
                  and discover trigger events like expansions and funding.
                </p>

                {/* Example prompts */}
                <div className="space-y-2 w-full max-w-lg">
                  {[
                    { icon: Building2, text: "Find me all wind energy companies in florida" },
                    { icon: Building2, text: "Find me similar companies to Brunswick boating company" },
                    { icon: Sparkles, text: "Find me supplier sourcing leads in the aerospace industry" },
                  ].map((example, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setInputValue(example.text)
                        // Auto-submit the query
                        setTimeout(() => handleSend(), 100)
                      }}
                      className="w-full flex items-center gap-3 px-4 py-3 bg-slate-50 hover:bg-emerald-50 rounded-xl border border-slate-200 hover:border-emerald-200 transition-all text-left group"
                    >
                      <example.icon className="w-5 h-5 text-slate-400 group-hover:text-emerald-500 transition-colors" />
                      <span className="text-sm text-slate-600 group-hover:text-slate-800">{example.text}</span>
                      <ChevronRight className="w-4 h-4 text-slate-300 ml-auto group-hover:text-emerald-500 transition-colors" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              // Conversation messages
              <div className="space-y-4">
                {conversationHistory.map((msg, idx) => (
                  <div
                    key={idx}
                    className={cn(
                      'flex',
                      msg.role === 'user' ? 'justify-end' : 'justify-start'
                    )}
                  >
                    <div
                      className={cn(
                        'max-w-[85%] rounded-2xl px-4 py-3',
                        msg.role === 'user'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-100 text-slate-800'
                      )}
                    >
                      <MarkdownContent
                        content={msg.content}
                        isUser={msg.role === 'user'}
                      />
                      <p className={cn(
                        'text-xs mt-1',
                        msg.role === 'user' ? 'text-emerald-200' : 'text-slate-400'
                      )}>
                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                ))}

                {/* Agent thinking indicator */}
                {isAgentThinking && (
                  <div className="flex justify-start">
                    <div className="bg-slate-100 rounded-2xl px-4 py-3 flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
                      <span className="text-sm text-slate-600">Searching...</span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Error display */}
          {agentError && (
            <div className="shrink-0 mx-6 mb-4 bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              <p className="text-sm text-red-600">{agentError}</p>
            </div>
          )}

          {/* Suggested followups */}
          {suggestedFollowups.length > 0 && !isAgentThinking && (
            <div className="shrink-0 px-6 pb-2">
              <div className="flex flex-wrap gap-2">
                {suggestedFollowups.map((followup, i) => (
                  <button
                    key={i}
                    onClick={() => handleFollowupClick(followup)}
                    className="px-3 py-1.5 bg-slate-100 hover:bg-emerald-50 text-xs text-slate-600 hover:text-emerald-700 rounded-full border border-slate-200 hover:border-emerald-200 transition-all"
                  >
                    {followup}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input Area */}
          <div className="shrink-0 p-4 border-t border-slate-200 bg-white">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                placeholder="Ask about prospects, contacts, or market signals..."
                className="flex-1 px-4 py-3 rounded-xl border border-slate-200 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none transition-all"
                disabled={isAgentThinking}
              />
              <Button
                onClick={handleSend}
                disabled={!inputValue.trim() || isAgentThinking}
                className="px-4"
              >
                {isAgentThinking ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Right Panel - Results / Saved */}
        <div className="flex-1 flex flex-col bg-slate-50 rounded-2xl overflow-hidden shadow-sm border border-slate-100/60">
          {/* Panel Toggle */}
          <div className="shrink-0 p-4 border-b border-slate-200">
            <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setRightPanelView('results')}
                className={cn(
                  'flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2',
                  rightPanelView === 'results'
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                <Sparkles size={14} />
                Results
                {searchBlocks.length > 0 && (
                  <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded-full">
                    {searchBlocks.length}
                  </span>
                )}
              </button>
              <button
                onClick={() => setRightPanelView('saved')}
                className={cn(
                  'flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2',
                  rightPanelView === 'saved'
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                )}
              >
                <Bookmark size={14} />
                Saved
                {(savedProspects.length + savedContacts.length) > 0 && (
                  <span className="px-1.5 py-0.5 bg-slate-200 text-slate-600 text-xs rounded-full">
                    {savedProspects.length + savedContacts.length}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Panel Content */}
          <div className="flex-1 overflow-auto p-4">
            {rightPanelView === 'results' ? (
              // Search Results (SearchBlocks)
              <div className="space-y-4">
                {!hasSearchBlocks ? (
                  <div className="h-full flex flex-col items-center justify-center text-center py-12">
                    <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-3">
                      <Sparkles className="w-6 h-6 text-slate-400" />
                    </div>
                    <p className="text-sm text-slate-500">Search results will appear here</p>
                    <p className="text-xs text-slate-400 mt-1">Ask the agent to find prospects or contacts</p>
                  </div>
                ) : (
                  searchBlocks.map((block) => (
                    <SearchBlockCard
                      key={block.id}
                      block={block}
                      onToggle={() => toggleBlockExpansion(block.id)}
                      onRemove={() => removeSearchBlock(block.id)}
                      onSaveProspect={handleSaveProspect}
                      onSaveContact={handleSaveContact}
                      onEnrichProspect={async (blockId, domain) => enrichCompany(domain)}
                      isPolling={false}
                    />
                  ))
                )}
              </div>
            ) : (
              // Saved Items
              <div className="space-y-6">
                {/* Saved Prospects */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-slate-700">
                      Prospects ({savedProspects.length})
                    </h3>
                    {savedProspects.length > 0 && (
                      <Button variant="ghost" size="sm" onClick={exportProspectsToCSV}>
                        <Download size={12} />
                        CSV
                      </Button>
                    )}
                  </div>
                  {savedProspects.length === 0 ? (
                    <div className="bg-slate-50 rounded-xl p-6 text-center border border-slate-200">
                      <Building2 className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                      <p className="text-xs text-slate-500">No saved prospects</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {savedProspects.map((prospect) => (
                        <SavedProspectCard
                          key={prospect.id}
                          prospect={prospect}
                          onRemove={() => removeProspect(prospect.id)}
                          onUpdateStatus={(status) => updateProspect(prospect.id, { status })}
                        />
                      ))}
                    </div>
                  )}
                </div>

                {/* Saved Contacts */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-slate-700">
                      Contacts ({savedContacts.length})
                    </h3>
                    {savedContacts.length > 0 && (
                      <Button variant="ghost" size="sm" onClick={exportContactsToCSV}>
                        <Download size={12} />
                        CSV
                      </Button>
                    )}
                  </div>
                  {savedContacts.length === 0 ? (
                    <div className="bg-slate-50 rounded-xl p-6 text-center border border-slate-200">
                      <Users className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                      <p className="text-xs text-slate-500">No saved contacts</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {savedContacts.map((contact) => (
                        <SavedContactCard
                          key={contact.id}
                          contact={contact}
                          onRemove={() => removeContact(contact.id)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================
// Sub-components for Saved Items
// ============================================

interface SavedProspectCardProps {
  prospect: PipelineProspect
  onRemove: () => void
  onUpdateStatus: (status: PipelineProspect['status']) => void
}

function SavedProspectCard({ prospect, onRemove, onUpdateStatus }: SavedProspectCardProps) {
  const statusColors: Record<PipelineProspect['status'], string> = {
    new: 'bg-slate-100 text-slate-600',
    contacted: 'bg-blue-100 text-blue-700',
    qualified: 'bg-emerald-100 text-emerald-700',
    converted: 'bg-emerald-100 text-emerald-700',
  }

  // Safely extract domain
  const getDomain = () => {
    if (prospect.domain) return prospect.domain
    try {
      return new URL(prospect.url).hostname
    } catch {
      return prospect.url
    }
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3 hover:border-slate-300 transition-all group">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-medium text-sm text-slate-800 truncate">{prospect.title}</h4>
          </div>
          <a
            href={prospect.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-emerald-600 hover:text-emerald-700 flex items-center gap-1"
          >
            {getDomain()}
            <ExternalLink size={10} />
          </a>
        </div>
        <div className="flex items-center gap-1">
          <select
            value={prospect.status}
            onChange={(e) => onUpdateStatus(e.target.value as PipelineProspect['status'])}
            className={cn(
              'text-xs px-2 py-1 rounded border-0 cursor-pointer',
              statusColors[prospect.status]
            )}
          >
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="converted">Converted</option>
          </select>
          <button
            onClick={onRemove}
            className="p-1 rounded hover:bg-red-50 text-slate-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

interface SavedContactCardProps {
  contact: PipelineContact
  onRemove: () => void
}

function SavedContactCard({ contact, onRemove }: SavedContactCardProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3 hover:border-slate-300 transition-all group">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-sm text-slate-800">{contact.name}</h4>
          {contact.title && (
            <p className="text-xs text-slate-500">{contact.title}</p>
          )}
          {contact.company && (
            <p className="text-xs text-slate-400">{contact.company}</p>
          )}
          <a
            href={contact.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-emerald-600 hover:text-emerald-700 flex items-center gap-1 mt-1"
          >
            View Profile
            <ExternalLink size={10} />
          </a>
        </div>
        <button
          onClick={onRemove}
          className="p-1 rounded hover:bg-red-50 text-slate-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}
