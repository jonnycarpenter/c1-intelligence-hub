'use client'

import React, { useRef, useEffect, useState } from 'react'
import { Sparkles, Send, Loader2, Globe, Database, Podcast } from 'lucide-react'
import { cn } from '@/lib/utils'
import { MarkdownContent } from '@/components/ui'
import { useDiscoveryChat, type DiscoveryChatMessage } from '@/hooks'

/**
 * DiscoveryAssistant - AI chat panel with streaming responses and tool access
 * 
 * Features:
 * - Dark header with sparkles icon
 * - Empty state with quick suggestion chips
 * - Message bubbles (user = teal, assistant = gray)
 * - Source badges showing which tools were used
 * - Auto-scroll to bottom on new messages
 * - Loading indicator while streaming
 */

interface DiscoveryAssistantProps {
  isOpen: boolean
  onClose: () => void
  initialQuery?: string  // Optional query to send immediately when opened
}

// Quick suggestion chips for empty state
const SUGGESTIONS = [
  { label: "What's trending?", query: "What are the top trends in the market right now?" },
  { label: "Competitor moves", query: "Show me recent competitor activity and strategic moves" },
  { label: "Health trends", query: "What's happening with health and wellness in the industry?" },
  { label: "Supply chain", query: "Any notable supply chain or sourcing news?" },
]

// Source badge configuration
const SOURCE_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  'Corpus': { icon: Database, label: 'Corpus', color: 'bg-teal-100 text-teal-700' },
  'Web': { icon: Globe, label: 'Web', color: 'bg-blue-100 text-blue-700' },
  'Podcast': { icon: Podcast, label: 'Podcast', color: 'bg-purple-100 text-purple-700' },
  'corpus_search': { icon: Database, label: 'Corpus', color: 'bg-teal-100 text-teal-700' },
  'exa_search': { icon: Globe, label: 'Web', color: 'bg-blue-100 text-blue-700' },
  'podcast_insights': { icon: Podcast, label: 'Podcast', color: 'bg-purple-100 text-purple-700' },
}

function SourceBadge({ source }: { source: string }) {
  const config = SOURCE_CONFIG[source] || { icon: Database, label: source, color: 'bg-gray-100 text-gray-700' }
  const Icon = config.icon
  
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', config.color)}>
      <Icon size={12} />
      {config.label}
    </span>
  )
}

function MessageBubble({ message }: { message: DiscoveryChatMessage }) {
  const isUser = message.role === 'user'
  
  return (
    <div className={cn('flex gap-3', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn(
        'max-w-[85%] rounded-2xl px-4 py-3',
        isUser 
          ? 'bg-teal-600 text-white rounded-br-sm' 
          : 'bg-slate-100 text-slate-800 rounded-bl-sm'
      )}>
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
            <div className="prose prose-sm max-w-none prose-slate">
              <MarkdownContent content={message.content || ''} />
            </div>
            
            {/* Loading indicator for streaming */}
            {message.isStreaming && (
              <div className="flex items-center gap-2 mt-2 text-slate-400">
                <Loader2 size={14} className="animate-spin" />
                <span className="text-xs">Thinking...</span>
              </div>
            )}
            
            {/* Source badges */}
            {!message.isStreaming && message.sourcesUsed && message.sourcesUsed.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3 pt-2 border-t border-slate-200">
                {message.sourcesUsed.map((source, i) => (
                  <SourceBadge key={i} source={source} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function DiscoveryAssistant({ isOpen, onClose, initialQuery }: DiscoveryAssistantProps) {
  const { messages, isLoading, error, activeTools, sendMessage, clearChat } = useDiscoveryChat()
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const hasProcessedInitialQuery = useRef(false)
  
  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])
  
  // Handle initial query (e.g., from entity pill click)
  useEffect(() => {
    if (isOpen && initialQuery && !hasProcessedInitialQuery.current) {
      hasProcessedInitialQuery.current = true
      sendMessage(initialQuery)
    }
    if (!isOpen) {
      hasProcessedInitialQuery.current = false
    }
  }, [isOpen, initialQuery, sendMessage])
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || isLoading) return
    
    sendMessage(inputValue.trim())
    setInputValue('')
  }
  
  const handleSuggestionClick = (query: string) => {
    sendMessage(query)
  }
  
  if (!isOpen) return null
  
  const isEmpty = messages.length === 0
  
  return (
    <div className="w-[400px] shrink-0 h-full flex flex-col bg-white rounded-2xl overflow-hidden shadow-sm border border-slate-100/60 m-4 mr-0">
      {/* Header - matching Pipeline style */}
      <div className="shrink-0 px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-teal-50 to-white">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal-100 flex items-center justify-center">
            <Sparkles size={20} className="text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-800">Discovery Assistant</h2>
            <p className="text-xs text-slate-500">AI-powered market intelligence</p>
          </div>
        </div>
      </div>
      
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isEmpty ? (
          // Empty state
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <div className="p-3 bg-teal-50 rounded-2xl mb-4">
              <Sparkles size={32} className="text-teal-500" />
            </div>
            <h3 className="text-slate-800 font-semibold mb-1">What would you like to explore?</h3>
            <p className="text-slate-500 text-sm mb-6">
              I can search our intelligence corpus and the live web.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => handleSuggestionClick(suggestion.query)}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm rounded-full transition-colors"
                >
                  {suggestion.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          // Message list
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            
            {/* Active tools indicator */}
            {activeTools.length > 0 && (
              <div className="flex items-center gap-2 text-slate-500 text-xs px-2">
                <Loader2 size={12} className="animate-spin" />
                <span>Searching {activeTools.join(', ')}...</span>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </>
        )}
        
        {/* Error display */}
        {error && (
          <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg">
            {error}
          </div>
        )}
      </div>
      
      {/* Input area */}
      <div className="shrink-0 border-t border-slate-200 p-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask about market trends, competitors..."
            disabled={isLoading}
            className={cn(
              "flex-1 px-4 py-2.5 bg-slate-100 border border-slate-200 rounded-xl text-sm",
              "placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          />
          <button
            type="submit"
            disabled={isLoading || !inputValue.trim()}
            className={cn(
              "p-2.5 rounded-xl transition-all",
              isLoading || !inputValue.trim()
                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                : "bg-teal-600 text-white hover:bg-teal-700"
            )}
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </form>
        
        {/* Clear chat button (when there are messages) */}
        {messages.length > 0 && !isLoading && (
          <button
            onClick={clearChat}
            className="w-full mt-2 py-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
          >
            Clear conversation
          </button>
        )}
      </div>
    </div>
  )
}
