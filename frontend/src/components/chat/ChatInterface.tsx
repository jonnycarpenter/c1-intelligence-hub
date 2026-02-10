'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Sparkles, Loader2, User, Bot } from 'lucide-react'
import { Button, MarkdownContent } from '@/components/ui'
import AgentThinkingPanel from './AgentThinkingPanel'
import StreamingThinkingPanel from './StreamingThinkingPanel'
import { cn } from '@/lib/utils'
import type { Message, Mode, AgentThinking } from '@/types'

// Suggestions per mode
const modeSuggestions: Record<Mode, string[]> = {
  pulse: [
    "What's driving the aluminum price surge?",
    "Summarize today's critical supply chain alerts",
    "Any disruptions affecting our key suppliers?",
  ],
  discovery: [
    "What's trending in the market this week?",
    "Show me recent competitor activity",
    "Any notable supply chain news?",
  ],
  research: [
    "Compare lithium suppliers in Chile vs Australia",
    "What are the ESG implications of rare earth mining?",
    "Analyze semiconductor supply chain vulnerabilities",
  ],
  products: [
    "Find alternatives to SKU-45231 with better margins",
    "Compare packaging options for beverage cans",
    "Which suppliers offer recycled aluminum?",
  ],
  'field-sales': [
    "Record field intel from customer visit",
    "Log competitor sighting",
    "Voice memo from trade show",
  ],
  pipeline: [
    "Composite buyers at Boeing",
    "Aerospace contacts in my territory",
    "New prospect recommendations",
  ],
  'supply-network': [
    "Show shared suppliers between competitors",
    "Hexcel supplier network",
    "Which suppliers does Toray use?",
  ],
  companies: [
    "Show me all tracked companies",
    "What's the latest on Hexcel's earnings?",
    "Compare Toray vs SGL Carbon market position",
  ],
  industries: [
    "Show Aerospace narrative timeline",
    "What themes are trending in Wind?",
    "Compare Defense Space event types",
  ],
  'data-preferences': [
    "Add a new company to track",
    "Show me recent data changes",
    "Update my notification preferences",
  ],
  'app-architecture': [
    "How does data ingestion work?",
    "Show me the agent workflow",
    "What GCP services are used?",
  ],
}

const welcomeMessages: Record<Mode, string> = {
  pulse: "I'm monitoring your supply chain intelligence in real-time. Ask me about any alerts, trends, or insights.",
  discovery: "I can help you explore market intelligence. Ask me about trends, competitors, or any topic from our corpus.",
  research: "Ready to dive deep. I can analyze markets, compare suppliers, or research any supply chain topic.",
  products: "Let's explore your product intelligence. I can help with SKU analysis, alternatives, and supplier comparisons.",
  'field-sales': "Field Intel is coming soon! You'll be able to record voice memos, log competitor sightings, and share field observations.",
  pipeline: "Pipeline is coming soon! You'll be able to search contacts, find prospects in your territory, and get AI-powered lead recommendations.",
  'supply-network': "Explore supply chain relationships for C1 and competitors. Click nodes on the graph to drill down into supplier or buyer details.",
  companies: "Let's explore company intelligence. I can track competitors, analyze earnings, and monitor market positions.",
  industries: "Explore industry narratives. See how news evolves over 90 days with monthly timelines, top companies, and themes.",
  'data-preferences': "Manage your tracked data and preferences. I can help add or remove companies, materials, and industries.",
  'app-architecture': "Welcome to Architecture. Explore the system design: data ingestion pipelines, frontend architecture, and agentic workflows.",
}

interface ChatInterfaceProps {
  mode: Mode
  messages: Message[]
  onSendMessage: (content: string) => void
  isLoading?: boolean
  isStreaming?: boolean
  streamingContent?: string
  streamingThinking?: AgentThinking[]
  currentAgent?: string | null
  hideStreamingContent?: boolean  // Hide content bubble (e.g., Research mode routes to canvas)
}

export default function ChatInterface({
  mode,
  messages,
  onSendMessage,
  isLoading = false,
  isStreaming = false,
  streamingContent = '',
  streamingThinking = [],
  currentAgent = null,
  hideStreamingContent = false,
}: ChatInterfaceProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const suggestions = modeSuggestions[mode]
  const welcomeMessage = welcomeMessages[mode]

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || isLoading) return
    onSendMessage(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion)
    inputRef.current?.focus()
  }

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Welcome message when empty */}
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-500 flex items-center justify-center mb-4 shadow-lg">
              <Sparkles size={28} className="text-white" />
            </div>
            <h3 className="text-lg font-semibold text-slate-800 mb-2">C1 Intelligence Hub</h3>
            <p className="text-slate-500 mb-6 max-w-md">{welcomeMessage}</p>

            {/* Suggestion chips */}
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSuggestionClick(suggestion)}
                  className="px-3 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:border-emerald-300 hover:bg-emerald-50 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message list */}
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {/* Streaming response with live thinking */}
        {isStreaming && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
              <Bot size={16} className="text-emerald-600" />
            </div>
            <div className="flex flex-col gap-2 max-w-[80%]">
              {/* Live thinking panel */}
              {streamingThinking.length > 0 && (
                <StreamingThinkingPanel
                  thinking={streamingThinking}
                  agentName={currentAgent}
                  isStreaming={true}
                />
              )}

              {/* Streaming content preview - hidden when routing to canvas (Research mode) */}
              {!hideStreamingContent && (
                streamingContent ? (
                  <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-slate-200 text-slate-700">
                    <p className="text-sm whitespace-pre-wrap">{streamingContent}</p>
                    <span className="inline-block w-2 h-4 bg-emerald-500 animate-pulse ml-0.5" />
                  </div>
                ) : (
                  <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-slate-200">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Loader2 size={14} className="animate-spin" />
                      <span className="text-sm">
                        {currentAgent ? `${currentAgent} is thinking...` : 'Processing...'}
                      </span>
                    </div>
                  </div>
                )
              )}

              {/* Research mode indicator - content goes to canvas */}
              {hideStreamingContent && !streamingThinking.length && (
                <div className="bg-emerald-50 rounded-2xl rounded-tl-sm px-4 py-3 border border-emerald-200">
                  <div className="flex items-center gap-2 text-emerald-700">
                    <Loader2 size={14} className="animate-spin" />
                    <span className="text-sm">Researching... response will appear in canvas</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Loading indicator (non-streaming fallback) */}
        {isLoading && !isStreaming && (
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
              <Bot size={16} className="text-emerald-600" />
            </div>
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-slate-200">
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 size={14} className="animate-spin" />
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-slate-200 bg-white p-4">
        {/* Quick suggestions when chat has started */}
        {messages.length > 0 && (
          <div className="flex gap-2 mb-3 overflow-x-auto pb-1">
            {suggestions.slice(0, 2).map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => handleSuggestionClick(suggestion)}
                className="shrink-0 px-2.5 py-1.5 text-xs text-slate-500 bg-slate-100 rounded-full hover:bg-slate-200 transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about supply chain intelligence..."
              rows={1}
              className="w-full resize-none rounded-xl border border-slate-300 px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent placeholder:text-slate-400"
            />
          </div>
          <Button
            type="submit"
            variant="primary"
            disabled={!input.trim() || isLoading}
            className="h-11 w-11 p-0 rounded-xl"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}

interface ChatMessageProps {
  message: Message
}

function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
        isUser ? 'bg-slate-200' : 'bg-emerald-100'
      )}>
        {isUser ? (
          <User size={16} className="text-slate-600" />
        ) : (
          <Bot size={16} className="text-emerald-600" />
        )}
      </div>

      {/* Content */}
      <div className={cn('flex flex-col gap-2 max-w-[80%]', isUser && 'items-end')}>
        {/* Agent thinking panel for assistant messages - shown BEFORE response */}
        {!isUser && message.thinking && message.thinking.length > 0 && (
          <AgentThinkingPanel
            thinking={message.thinking}
            traceUrl={message.traceUrl}
          />
        )}

        <div className={cn(
          'rounded-2xl px-4 py-3',
          isUser
            ? 'bg-emerald-500 text-white rounded-tr-sm'
            : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm'
        )}>
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <MarkdownContent content={message.content} />
          )}
        </div>

        {/* Timestamp */}
        <span className="text-[10px] text-slate-400 px-1">
          {typeof message.timestamp === 'string'
            ? message.timestamp
            : message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  )
}
