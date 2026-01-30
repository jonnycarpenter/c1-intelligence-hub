/**
 * useGuideChat Hook
 * 
 * Manages state for the Intelligence Hub Guide chat panel.
 * The Guide is an AI assistant that helps prospective users understand the platform.
 */

import { useState, useCallback } from 'react'
import { API_BASE } from '@/lib/config'

export interface GuideMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: string
}

interface UseGuideChatReturn {
    messages: GuideMessage[]
    isLoading: boolean
    sendMessage: (content: string) => Promise<void>
    resetChat: () => void
    welcomeMessage: string | null
    loadWelcome: () => Promise<void>
}

export function useGuideChat(): UseGuideChatReturn {
    const [messages, setMessages] = useState<GuideMessage[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [welcomeMessage, setWelcomeMessage] = useState<string | null>(null)

    const loadWelcome = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/guide/welcome`)
            if (response.ok) {
                const data = await response.json()
                setWelcomeMessage(data.message)
            }
        } catch (error) {
            console.error('Failed to load welcome message:', error)
            // Fallback welcome message
            setWelcomeMessage(`👋 Welcome to the Intelligence Hub!

I'm your Guide, here to help you understand what this platform can do for your business.

What would you like to know about?`)
        }
    }, [])

    const sendMessage = useCallback(async (content: string) => {
        if (!content.trim() || isLoading) return

        // Add user message
        const userMessage: GuideMessage = {
            id: `user_${Date.now()}`,
            role: 'user',
            content: content.trim(),
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }

        setMessages(prev => [...prev, userMessage])
        setIsLoading(true)

        try {
            // Build history for context (exclude the message we just added)
            const history = messages.map(msg => ({
                role: msg.role,
                content: msg.content,
            }))

            const response = await fetch(`${API_BASE}/api/guide/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: content.trim(),
                    history,
                }),
            })

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`)
            }

            const data = await response.json()

            // Add assistant response
            const assistantMessage: GuideMessage = {
                id: `assistant_${Date.now()}`,
                role: 'assistant',
                content: data.response,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            }

            setMessages(prev => [...prev, assistantMessage])

        } catch (error) {
            console.error('Guide chat error:', error)

            // Add error message
            const errorMessage: GuideMessage = {
                id: `error_${Date.now()}`,
                role: 'assistant',
                content: "I apologize, but I'm having trouble responding right now. Please try again in a moment!",
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            }

            setMessages(prev => [...prev, errorMessage])
        } finally {
            setIsLoading(false)
        }
    }, [messages, isLoading])

    const resetChat = useCallback(() => {
        setMessages([])
        setWelcomeMessage(null)
    }, [])

    return {
        messages,
        isLoading,
        sendMessage,
        resetChat,
        welcomeMessage,
        loadWelcome,
    }
}
