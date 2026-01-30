'use client'

/**
 * GuidePanel Component
 * 
 * Slide-out panel from the right side of the screen that provides
 * an AI-powered Guide to help prospective users understand the platform.
 */

import { useState, useRef, useEffect } from 'react'
import { X, Send, Loader2, Compass, User, Bot, Sparkles } from 'lucide-react'
import { Button, MarkdownContent } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useGuideChat, type GuideMessage } from '@/hooks/useGuideChat'

interface GuidePanelProps {
    isOpen: boolean
    onClose: () => void
}

const SUGGESTED_QUESTIONS = [
    "What makes this platform unique?",
    "What data sources do you monitor?",
    "Tell me about the Strategic Briefing",
    "What materials are you tracking?",
    "How does Deep Research work?",
]

export default function GuidePanel({ isOpen, onClose }: GuidePanelProps) {
    const [input, setInput] = useState('')
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)

    const {
        messages,
        isLoading,
        sendMessage,
        resetChat,
        welcomeMessage,
        loadWelcome,
    } = useGuideChat()

    // Load welcome message when panel opens
    useEffect(() => {
        if (isOpen && !welcomeMessage && messages.length === 0) {
            loadWelcome()
        }
    }, [isOpen, welcomeMessage, messages.length, loadWelcome])

    // Reset chat when panel closes
    useEffect(() => {
        if (!isOpen) {
            resetChat()
        }
    }, [isOpen, resetChat])

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, welcomeMessage])

    // Focus input when panel opens
    useEffect(() => {
        if (isOpen) {
            setTimeout(() => inputRef.current?.focus(), 300)
        }
    }, [isOpen])

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault()
        if (!input.trim() || isLoading) return

        const message = input.trim()
        setInput('')
        await sendMessage(message)
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
        <>
            {/* Backdrop */}
            <div
                className={cn(
                    "fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity duration-300",
                    isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={onClose}
            />

            {/* Panel */}
            <div
                className={cn(
                    "fixed right-0 top-0 h-full w-[420px] max-w-full bg-white shadow-2xl z-50",
                    "flex flex-col",
                    "transform transition-transform duration-300 ease-out",
                    isOpen ? "translate-x-0" : "translate-x-full"
                )}
            >
                {/* Header */}
                <div className="shrink-0 px-5 py-4 border-b border-slate-200 bg-gradient-to-r from-teal-500 to-emerald-500">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
                                <Compass size={22} className="text-white" />
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-white">Intelligence Hub Guide</h2>
                                <p className="text-xs text-white/80">Ask me anything about the platform</p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 rounded-lg text-white/80 hover:text-white hover:bg-white/10 transition-colors"
                        >
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
                    {/* Welcome message */}
                    {welcomeMessage && messages.length === 0 && (
                        <div className="flex items-start gap-3">
                            <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center shrink-0">
                                <Sparkles size={16} className="text-teal-600" />
                            </div>
                            <div className="flex flex-col gap-3 max-w-[85%]">
                                <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 border border-slate-200 shadow-sm">
                                    <MarkdownContent content={welcomeMessage} />
                                </div>

                                {/* Suggested questions */}
                                <div className="flex flex-wrap gap-2">
                                    {SUGGESTED_QUESTIONS.slice(0, 3).map((question, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => handleSuggestionClick(question)}
                                            className="px-3 py-1.5 text-xs text-teal-700 bg-teal-50 border border-teal-200 rounded-full hover:bg-teal-100 transition-colors"
                                        >
                                            {question}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Message list */}
                    {messages.map((message) => (
                        <ChatMessage key={message.id} message={message} />
                    ))}

                    {/* Loading indicator */}
                    {isLoading && (
                        <div className="flex items-start gap-3">
                            <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center shrink-0">
                                <Bot size={16} className="text-teal-600" />
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

                {/* Input Area */}
                <div className="shrink-0 border-t border-slate-200 bg-white p-4">
                    {/* More suggestions when conversation has started */}
                    {messages.length > 0 && messages.length < 4 && (
                        <div className="flex gap-2 mb-3 overflow-x-auto pb-1">
                            {SUGGESTED_QUESTIONS.slice(3, 5).map((question, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => handleSuggestionClick(question)}
                                    className="shrink-0 px-2.5 py-1.5 text-xs text-slate-500 bg-slate-100 rounded-full hover:bg-slate-200 transition-colors"
                                >
                                    {question}
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
                                placeholder="Ask about the platform..."
                                rows={1}
                                className="w-full resize-none rounded-xl border border-slate-300 px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent placeholder:text-slate-400"
                            />
                        </div>
                        <Button
                            type="submit"
                            variant="primary"
                            disabled={!input.trim() || isLoading}
                            className="h-11 w-11 p-0 rounded-xl bg-teal-500 hover:bg-teal-600"
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
        </>
    )
}

interface ChatMessageProps {
    message: GuideMessage
}

function ChatMessage({ message }: ChatMessageProps) {
    const isUser = message.role === 'user'

    return (
        <div className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}>
            {/* Avatar */}
            <div className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                isUser ? 'bg-slate-200' : 'bg-teal-100'
            )}>
                {isUser ? (
                    <User size={16} className="text-slate-600" />
                ) : (
                    <Bot size={16} className="text-teal-600" />
                )}
            </div>

            {/* Content */}
            <div className={cn('flex flex-col gap-1 max-w-[85%]', isUser && 'items-end')}>
                <div className={cn(
                    'rounded-2xl px-4 py-3',
                    isUser
                        ? 'bg-teal-500 text-white rounded-tr-sm'
                        : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                )}>
                    {isUser ? (
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    ) : (
                        <MarkdownContent content={message.content} />
                    )}
                </div>

                {/* Timestamp */}
                <span className="text-[10px] text-slate-400 px-1">
                    {message.timestamp}
                </span>
            </div>
        </div>
    )
}
