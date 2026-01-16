'use client'

import { useState, useCallback, useRef } from 'react'
import { API_BASE } from '@/lib/config'

/**
 * Discovery Chat Hook
 * 
 * Handles streaming chat with the Discovery Assistant.
 * Uses SSE (Server-Sent Events) for real-time responses.
 * 
 * SSE Event Types from backend:
 * - chunk: Partial text response
 * - tool_call: Tool being invoked (for UI indicator)
 * - complete: Final response with sources_used
 * - error: Error message
 */

// =============================================================================
// Types
// =============================================================================

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  sourcesUsed?: string[]  // ['Corpus', 'Web', 'Podcast']
  timestamp: Date
}

interface SSEEvent {
  type: 'chunk' | 'tool_call' | 'complete' | 'error'
  text?: string           // For chunk events
  tool?: string           // For tool_call events
  sources_used?: string[] // For complete events
  message?: string        // For error events
}

interface UseDiscoveryChatReturn {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  activeTools: string[]   // Tools currently being called
  sendMessage: (text: string) => Promise<void>
  clearChat: () => void
}

// =============================================================================
// Helper Functions
// =============================================================================

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

function parseSSELine(line: string): SSEEvent | null {
  if (!line.startsWith('data: ')) return null
  
  const data = line.slice(6) // Remove 'data: ' prefix
  if (data === '[DONE]') return null
  
  try {
    return JSON.parse(data)
  } catch {
    console.warn('[useDiscoveryChat] Failed to parse SSE event:', data)
    return null
  }
}

// =============================================================================
// Hook
// =============================================================================

export function useDiscoveryChat(): UseDiscoveryChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTools, setActiveTools] = useState<string[]>([])
  
  // Ref to track the current assistant message being streamed
  const streamingMessageRef = useRef<string | null>(null)
  // Abort controller for cancelling requests
  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return
    
    // Clear any previous error
    setError(null)
    setActiveTools([])
    
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    
    // Add user message
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    
    // Create placeholder for assistant response
    const assistantId = generateId()
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      timestamp: new Date(),
    }
    
    streamingMessageRef.current = assistantId
    
    setMessages(prev => [...prev, userMessage, assistantMessage])
    setIsLoading(true)
    
    try {
      // Build history from last 10 messages (excluding the new ones)
      const history = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
      }))
      
      const response = await fetch(`${API_BASE}/api/discovery/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: text,
          history,
        }),
        signal: abortControllerRef.current.signal,
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      if (!response.body) {
        throw new Error('No response body')
      }
      
      // Process SSE stream
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accumulatedContent = ''
      const toolsUsed: string[] = []
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        
        // Process complete lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer
        
        for (const line of lines) {
          const event = parseSSELine(line)
          if (!event) continue
          
          switch (event.type) {
            case 'chunk':
              if (event.text) {
                accumulatedContent += event.text
                // Update the streaming message
                setMessages(prev => prev.map(m => 
                  m.id === assistantId 
                    ? { ...m, content: accumulatedContent }
                    : m
                ))
              }
              break
              
            case 'tool_call':
              if (event.tool) {
                // Map backend tool names to friendly labels
                const toolLabel = event.tool === 'corpus_search' ? 'Corpus' 
                                : event.tool === 'exa_search' ? 'Web'
                                : event.tool
                if (!toolsUsed.includes(toolLabel)) {
                  toolsUsed.push(toolLabel)
                }
                setActiveTools(prev => [...prev, toolLabel])
              }
              break
              
            case 'complete':
              // Finalize the message
              setMessages(prev => prev.map(m => 
                m.id === assistantId 
                  ? { 
                      ...m, 
                      content: accumulatedContent,
                      isStreaming: false,
                      sourcesUsed: event.sources_used || toolsUsed,
                    }
                  : m
              ))
              setActiveTools([])
              break
              
            case 'error':
              setError(event.message || 'An error occurred')
              setMessages(prev => prev.map(m => 
                m.id === assistantId 
                  ? { 
                      ...m, 
                      content: event.message || 'An error occurred',
                      isStreaming: false,
                    }
                  : m
              ))
              break
          }
        }
      }
      
      // If we didn't get a complete event, finalize anyway
      setMessages(prev => prev.map(m => 
        m.id === assistantId && m.isStreaming
          ? { ...m, isStreaming: false, sourcesUsed: toolsUsed }
          : m
      ))
      
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was cancelled, don't show error
        return
      }
      
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message'
      setError(errorMessage)
      
      // Update the assistant message to show error
      setMessages(prev => prev.map(m => 
        m.id === assistantId
          ? { ...m, content: `Error: ${errorMessage}`, isStreaming: false }
          : m
      ))
    } finally {
      setIsLoading(false)
      setActiveTools([])
      streamingMessageRef.current = null
      abortControllerRef.current = null
    }
  }, [messages, isLoading])

  const clearChat = useCallback(() => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    
    setMessages([])
    setError(null)
    setActiveTools([])
    setIsLoading(false)
    streamingMessageRef.current = null
  }, [])

  return {
    messages,
    isLoading,
    error,
    activeTools,
    sendMessage,
    clearChat,
  }
}

export default useDiscoveryChat
