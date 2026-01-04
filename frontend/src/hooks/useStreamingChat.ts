'use client'

import { useState, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import type { Message, AgentThinking, ToolCall, Mode } from '@/types'
import type { Product } from './useProducts'
import type { Company } from './useCompanies'
import type { Industry } from './useIndustries'

// Stream event types from backend
interface StreamEvent {
  type: 'start' | 'status' | 'routing' | 'thinking' | 'tool_start' | 'tool_end' | 
        'tool_call' | 'tool_result' | 'tool_error' | 'agent_action' | 'agent_finish' |
        'content' | 'final' | 'complete' | 'done' | 'error'
  content?: string
  message_id?: string
  conversation_id?: string
  agent?: string
  tool_name?: string
  inputs?: Record<string, unknown>
  output_summary?: string
  output?: string  // Full tool output JSON for product extraction
  result?: string
  reasoning?: string
  event?: string
  metadata?: Record<string, unknown>
}

interface StreamingState {
  isStreaming: boolean
  currentAgent: string | null
  thinkingSteps: AgentThinking[]
  content: string
  error: string | null
  products: Product[] // Products extracted from tool results
  companies: Company[] // Companies extracted from tool results
  industries: Industry[] // Industries extracted from tool results
}

interface UseStreamingChatOptions {
  onMessageComplete?: (message: Message) => void
  onResearchContentUpdate?: (content: string) => void  // For updating research section during streaming
}

// Helper to extract products from tool results
function extractProductsFromToolResult(toolName: string, resultStr: string): Product[] {
  // Only process product-related tools
  const productTools = [
    'search_competitor_products',
    'get_c1_catalog',
    'get_product_specs',
    'compare_product_specs',
    'find_product_gaps',
    'suggest_alternatives',
  ]
  
  if (!productTools.some(t => toolName.toLowerCase().includes(t.replace(/_/g, '')))) {
    // Also check for partial matches
    const toolLower = toolName.toLowerCase()
    if (!toolLower.includes('product') && !toolLower.includes('catalog') && 
        !toolLower.includes('competitor') && !toolLower.includes('spec')) {
      return []
    }
  }
  
  try {
    const parsed = JSON.parse(resultStr)
    const products: Product[] = []
    
    // Handle products_by_supplier format (from search_competitor_products)
    if (parsed.products_by_supplier) {
      Object.entries(parsed.products_by_supplier).forEach(([supplier, prods]) => {
        (prods as Array<{ id: string; name: string; category: string; industries?: string[]; in_c1_catalog?: boolean }>).forEach((p) => {
          products.push({
            id: p.id,
            name: p.name,
            supplier,
            category: p.category,
            industries: p.industries || [],
            specs: {},
            in_c1_catalog: p.in_c1_catalog || false,
          })
        })
      })
    }
    
    // Handle products_by_category format (from get_c1_catalog)
    if (parsed.products_by_category) {
      Object.entries(parsed.products_by_category).forEach(([category, prods]) => {
        (prods as Array<{ name: string; supplier: string; industries?: string[] }>).forEach((p) => {
          // Generate a simple ID from name
          const id = p.name.toLowerCase().replace(/\s+/g, '-').substring(0, 20)
          products.push({
            id,
            name: p.name,
            supplier: p.supplier,
            category,
            industries: p.industries || [],
            specs: {},
            in_c1_catalog: true,
          })
        })
      })
    }
    
    // Handle single product format (from get_product_specs)
    if (parsed.product && typeof parsed.product === 'object') {
      const p = parsed.product
      products.push({
        id: p.id || p.name?.toLowerCase().replace(/\s+/g, '-'),
        name: p.name,
        supplier: p.supplier,
        category: p.category || 'unknown',
        subcategory: p.subcategory,
        industries: p.industries || [],
        specs: p.specs || {},
        in_c1_catalog: p.in_c1_catalog || false,
      })
    }
    
    // Handle comparison format (from compare_product_specs)
    if (parsed.products && Array.isArray(parsed.products)) {
      parsed.products.forEach((p: { id?: string; name: string; supplier: string; category?: string; subcategory?: string; industries?: string[]; specs?: Record<string, string>; in_c1_catalog?: boolean }) => {
        products.push({
          id: p.id || p.name?.toLowerCase().replace(/\s+/g, '-'),
          name: p.name,
          supplier: p.supplier,
          category: p.category || 'unknown',
          subcategory: p.subcategory,
          industries: p.industries || [],
          specs: p.specs || {},
          in_c1_catalog: p.in_c1_catalog || false,
        })
      })
    }
    
    // Handle gaps format (from find_product_gaps)
    if (parsed.gaps_by_supplier) {
      Object.entries(parsed.gaps_by_supplier).forEach(([supplier, prods]) => {
        (prods as Array<{ id: string; name: string; industries?: string[] }>).forEach((p) => {
          products.push({
            id: p.id,
            name: p.name,
            supplier,
            category: parsed.category || 'unknown',
            industries: p.industries || [],
            specs: {},
            in_c1_catalog: false, // Gaps are things we don't carry
          })
        })
      })
    }
    
    // Deduplicate by ID
    const seen = new Set<string>()
    return products.filter(p => {
      if (seen.has(p.id)) return false
      seen.add(p.id)
      return true
    })
  } catch {
    // Not valid JSON or couldn't parse
    return []
  }
}

// Helper to clean content for research canvas (remove JSON/tool artifacts)
function cleanContentForResearch(content: string): string {
  if (!content) return content
  
  let cleaned = content
  
  // Remove any JSON objects (anything that looks like {...} with quotes inside)
  // This catches tool results, API responses, etc.
  cleaned = cleaned.replace(/\{[^{}]*"[^"]*"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g, '')
  
  // Remove nested/complex JSON objects more aggressively
  // Match opening brace, then any content with quotes, then closing brace
  cleaned = cleaned.replace(/\{\s*"[\s\S]*?\}\s*(?=\n|$)/g, '')
  
  // Remove JSON arrays
  cleaned = cleaned.replace(/\[\s*\{[\s\S]*?\}\s*\]/g, '')
  
  // Remove standalone JSON-like key-value lines
  cleaned = cleaned.replace(/^\s*"[^"]+"\s*:\s*[^\n]+$/gm, '')
  
  // Remove thinking/metadata blocks
  cleaned = cleaned.replace(/<thinking>[\s\S]*?<\/thinking>/gi, '')
  cleaned = cleaned.replace(/\[Tool: [^\]]+\]/g, '')
  cleaned = cleaned.replace(/\[Agent: [^\]]+\]/g, '')
  cleaned = cleaned.replace(/\[Result: [^\]]+\]/g, '')
  
  // Remove "Tool result:" prefixed blocks
  cleaned = cleaned.replace(/Tool result:[\s\S]*?(?=\n\n|\n[A-Z]|$)/gi, '')
  
  // Remove lines that are just JSON structure characters
  cleaned = cleaned.replace(/^\s*[\{\}\[\],]+\s*$/gm, '')
  
  // Remove lines starting with common JSON keys
  cleaned = cleaned.replace(/^\s*"(?:id|name|type|status|success|error|data|result|items|total|count)".*$/gm, '')
  
  // Remove excessive newlines (3+ becomes 2)
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n')
  
  // Trim whitespace
  cleaned = cleaned.trim()
  
  return cleaned
}

// Helper to extract companies from tool results
function extractCompaniesFromToolResult(toolName: string, resultStr: string): Company[] {
  // Only process company-related tools
  const companyTools = [
    'get_companies_list',
    'add_company_to_tracker',
    'corpus_query',
  ]
  
  const toolLower = toolName.toLowerCase()
  if (!companyTools.some(t => toolLower.includes(t.replace(/_/g, ''))) &&
      !toolLower.includes('compan') && !toolLower.includes('competitor')) {
    return []
  }
  
  try {
    const parsed = JSON.parse(resultStr)
    const companies: Company[] = []
    
    // Handle companies array format (from get_companies_list)
    if (parsed.companies && Array.isArray(parsed.companies)) {
      parsed.companies.forEach((c: { 
        company_id?: string
        company?: string
        name?: string
        type?: string
        stock_ticker?: string
        ticker?: string
        industries_served?: string
        description?: string
      }) => {
        const name = c.company || c.name || ''
        if (!name) return
        
        companies.push({
          id: c.company_id || name.toLowerCase().replace(/\s+/g, '-'),
          name,
          type: c.type || 'Unknown',
          ticker: c.stock_ticker || c.ticker,
          industries: c.industries_served ? c.industries_served.split(',').map(s => s.trim()) : [],
          description: c.description,
          is_tracked: true,
        })
      })
    }
    
    // Handle single company format (from add_company_to_tracker)
    if (parsed.company && typeof parsed.company === 'object') {
      const c = parsed.company
      const name = c.company || c.name || ''
      if (name) {
        companies.push({
          id: c.company_id || name.toLowerCase().replace(/\s+/g, '-'),
          name,
          type: c.type || 'Unknown',
          ticker: c.stock_ticker || c.ticker,
          industries: c.industries_served ? c.industries_served.split(',').map((s: string) => s.trim()) : [],
          description: c.description,
          is_tracked: true,
        })
      }
    }
    
    // Deduplicate by ID
    const seen = new Set<string>()
    return companies.filter(c => {
      if (seen.has(c.id)) return false
      seen.add(c.id)
      return true
    })
  } catch {
    return []
  }
}

// Helper to extract industries from tool results
function extractIndustriesFromToolResult(toolName: string, resultStr: string): Industry[] {
  // Only process industry-related tools
  const industryTools = [
    'corpus_query',
    'get_industry_trends',
  ]
  
  const toolLower = toolName.toLowerCase()
  if (!industryTools.some(t => toolLower.includes(t.replace(/_/g, ''))) &&
      !toolLower.includes('industr') && !toolLower.includes('sector')) {
    return []
  }
  
  try {
    const parsed = JSON.parse(resultStr)
    const industries: Industry[] = []
    
    // Handle industries array format
    if (parsed.industries && Array.isArray(parsed.industries)) {
      parsed.industries.forEach((ind: {
        id?: string
        industry_id?: string
        name?: string
        industry_name?: string
        market_size?: string
        growth_rate?: number | string
        trend?: string
        description?: string
        key_applications?: string[]
        key_materials?: string[]
        key_companies?: string[]
      }) => {
        const name = ind.name || ind.industry_name || ''
        if (!name) return
        
        industries.push({
          id: ind.id || ind.industry_id || name.toLowerCase().replace(/\s+/g, '_'),
          name,
          market_size: ind.market_size,
          growth_rate: typeof ind.growth_rate === 'number' ? ind.growth_rate : (parseFloat(String(ind.growth_rate)) || undefined),
          trend: ind.trend as Industry['trend'],
          description: ind.description,
          key_applications: ind.key_applications,
          key_materials: ind.key_materials,
          key_companies: ind.key_companies,
        })
      })
    }
    
    // Deduplicate by ID
    const seen = new Set<string>()
    return industries.filter(i => {
      if (seen.has(i.id)) return false
      seen.add(i.id)
      return true
    })
  } catch {
    return []
  }
}

export function useStreamingChat(options: UseStreamingChatOptions = {}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [streamingState, setStreamingState] = useState<StreamingState>({
    isStreaming: false,
    currentAgent: null,
    thinkingSteps: [],
    content: '',
    error: null,
    products: [],
    companies: [],
    industries: [],
  })
  
  const conversationIdRef = useRef<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  
  // Ref for dynamic research content callback - allows updating callback without re-creating sendMessage
  const researchContentCallbackRef = useRef<((content: string) => void) | null>(null)
  
  // Setter for research content callback (can be called from parent component)
  const setResearchContentCallback = useCallback((callback: ((content: string) => void) | null) => {
    researchContentCallbackRef.current = callback
  }, [])

  // Helper to format timestamp
  const formatTime = () => new Date().toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit' 
  })

  // Send a message with streaming
  const sendMessage = useCallback(async (content: string, mode: Mode) => {
    // Add user message immediately
    const userMessage: Message = {
      id: `user_${Date.now()}`,
      role: 'user',
      content,
      timestamp: formatTime(),
    }
    setMessages(prev => [...prev, userMessage])

    // Reset streaming state
    setStreamingState({
      isStreaming: true,
      currentAgent: null,
      thinkingSteps: [],
      content: '',
      error: null,
      products: [],
      companies: [],
      industries: [],
    })

    // Create placeholder for assistant message
    const assistantId = `assistant_${Date.now()}`
    const thinkingSteps: AgentThinking[] = []
    const toolCallsMap = new Map<string, ToolCall>()
    let finalContent = ''
    let currentStepIndex = -1
    let extractedProducts: Product[] = []
    let extractedCompanies: Company[] = []
    let extractedIndustries: Industry[] = []

    try {
      // Stream from API
      for await (const event of api.streamQuery({
        message: content,
        mode,
        conversation_id: conversationIdRef.current || undefined,
      })) {
        const streamEvent = event as StreamEvent

        switch (streamEvent.type) {
          case 'start':
            // Store conversation ID
            if (streamEvent.conversation_id) {
              conversationIdRef.current = streamEvent.conversation_id
            }
            setStreamingState(prev => ({
              ...prev,
              currentAgent: streamEvent.agent || null,
            }))
            break

          case 'status':
            // Add a new thinking step for status
            const statusStep: AgentThinking = {
              step: streamEvent.content || 'Processing...',
              status: 'in-progress',
              timestamp: formatTime(),
            }
            thinkingSteps.push(statusStep)
            currentStepIndex = thinkingSteps.length - 1
            setStreamingState(prev => ({
              ...prev,
              thinkingSteps: [...thinkingSteps],
            }))
            break

          case 'routing':
            // Mark routing decision
            const routingStep: AgentThinking = {
              step: `Routing to ${streamEvent.agent}`,
              reasoning: streamEvent.reasoning,
              status: 'completed',
              timestamp: formatTime(),
            }
            thinkingSteps.push(routingStep)
            setStreamingState(prev => ({
              ...prev,
              currentAgent: streamEvent.agent || null,
              thinkingSteps: [...thinkingSteps],
            }))
            break

          case 'thinking':
            // Handle thinking start/end
            if (streamEvent.event === 'thinking_start') {
              const thinkStep: AgentThinking = {
                step: streamEvent.content || 'Agent reasoning...',
                status: 'in-progress',
                timestamp: formatTime(),
              }
              thinkingSteps.push(thinkStep)
              currentStepIndex = thinkingSteps.length - 1
            } else if (streamEvent.event === 'thinking_end' && currentStepIndex >= 0) {
              thinkingSteps[currentStepIndex].status = 'completed'
            }
            setStreamingState(prev => ({
              ...prev,
              thinkingSteps: [...thinkingSteps],
            }))
            break

          case 'tool_start':
          case 'tool_call':
            // Add tool call to current step or create new step
            const toolCall: ToolCall = {
              id: `tool_${Date.now()}`,
              name: streamEvent.tool_name || streamEvent.content || 'Unknown tool',
              input: streamEvent.inputs || streamEvent.metadata?.tool_args,
              status: 'running',
              startTime: new Date(),
            }
            toolCallsMap.set(toolCall.name, toolCall)

            // Find or create a step for tools
            let toolStep = thinkingSteps.find(s => s.step === 'Using tools')
            if (!toolStep) {
              toolStep = {
                step: 'Using tools',
                status: 'in-progress',
                timestamp: formatTime(),
                toolCalls: [],
              }
              thinkingSteps.push(toolStep)
            }
            toolStep.toolCalls = [...toolCallsMap.values()]
            setStreamingState(prev => ({
              ...prev,
              thinkingSteps: [...thinkingSteps],
            }))
            break

          case 'tool_end':
          case 'tool_result':
            // Update tool with result
            const toolName = streamEvent.tool_name || streamEvent.content || ''
            const existingTool = toolCallsMap.get(toolName)
            if (existingTool) {
              existingTool.status = 'completed'
              existingTool.output = streamEvent.output_summary || streamEvent.result
              existingTool.endTime = new Date()
              if (existingTool.startTime) {
                existingTool.duration = existingTool.endTime.getTime() - existingTool.startTime.getTime()
              }
            }
            
            // Extract products, companies, and industries from tool results
            // Priority: output (full JSON) > result > output_summary
            const toolResultStr = streamEvent.output || streamEvent.result || streamEvent.output_summary || ''
            
            // Extract products
            const parsedProducts = extractProductsFromToolResult(toolName, toolResultStr)
            if (parsedProducts.length > 0) {
              extractedProducts = [...extractedProducts, ...parsedProducts]
            }
            
            // Extract companies
            const parsedCompanies = extractCompaniesFromToolResult(toolName, toolResultStr)
            if (parsedCompanies.length > 0) {
              extractedCompanies = [...extractedCompanies, ...parsedCompanies]
            }
            
            // Extract industries
            const parsedIndustries = extractIndustriesFromToolResult(toolName, toolResultStr)
            if (parsedIndustries.length > 0) {
              extractedIndustries = [...extractedIndustries, ...parsedIndustries]
            }
            
            // Update streaming state with any extracted entities
            if (parsedProducts.length > 0 || parsedCompanies.length > 0 || parsedIndustries.length > 0) {
              setStreamingState(prev => ({
                ...prev,
                products: extractedProducts,
                companies: extractedCompanies,
                industries: extractedIndustries,
              }))
            }
            
            // Update the tools step
            const toolsStep = thinkingSteps.find(s => s.step === 'Using tools')
            if (toolsStep) {
              toolsStep.toolCalls = [...toolCallsMap.values()]
            }
            setStreamingState(prev => ({
              ...prev,
              thinkingSteps: [...thinkingSteps],
            }))
            break

          case 'tool_error':
            // Mark tool as errored
            const errorToolStep = thinkingSteps.find(s => s.step === 'Using tools')
            if (errorToolStep) {
              const errorTool: ToolCall = {
                name: 'Tool Error',
                status: 'error',
                output: streamEvent.content,
              }
              errorToolStep.toolCalls = [...(errorToolStep.toolCalls || []), errorTool]
            }
            setStreamingState(prev => ({
              ...prev,
              thinkingSteps: [...thinkingSteps],
            }))
            break

          case 'content':
            // Accumulate content (might come in chunks)
            finalContent += streamEvent.content || ''
            setStreamingState(prev => ({
              ...prev,
              content: finalContent,
            }))
            // Also update research section if callback provided (via ref for dynamic updates)
            // Clean content for research canvas (remove JSON/tool artifacts)
            if (researchContentCallbackRef.current) {
              const cleanedContent = cleanContentForResearch(finalContent)
              researchContentCallbackRef.current(cleanedContent)
            }
            break

          case 'final':
            // Final response - use this as the complete content
            finalContent = streamEvent.content || finalContent
            // Mark all steps as completed
            thinkingSteps.forEach(step => {
              if (step.status === 'in-progress') {
                step.status = 'completed'
              }
            })
            setStreamingState(prev => ({
              ...prev,
              content: finalContent,
              thinkingSteps: [...thinkingSteps],
            }))
            // Final update to research section (via ref for dynamic updates)
            // Clean content for research canvas (remove JSON/tool artifacts)
            if (researchContentCallbackRef.current) {
              const cleanedContent = cleanContentForResearch(finalContent)
              researchContentCallbackRef.current(cleanedContent)
            }
            break

          case 'complete':
            // Processing complete
            break

          case 'done':
            // Stream ended
            break

          case 'error':
            setStreamingState(prev => ({
              ...prev,
              error: streamEvent.content || 'An error occurred',
            }))
            break
        }
      }

      // Create final assistant message
      // For research mode, show a brief note since content goes to canvas
      const isResearchMode = mode === 'research'
      const assistantMessage: Message = {
        id: assistantId,
        role: 'assistant',
        content: isResearchMode 
          ? '✅ Research complete — see the canvas for full analysis.'
          : finalContent,
        timestamp: formatTime(),
        thinking: thinkingSteps.length > 0 ? thinkingSteps : undefined,
        agentName: streamingState.currentAgent || undefined,
      }

      setMessages(prev => [...prev, assistantMessage])
      options.onMessageComplete?.(assistantMessage)

    } catch (error) {
      console.error('Streaming error:', error)
      const errorMessage: Message = {
        id: assistantId,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: formatTime(),
        isError: true,
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setStreamingState(prev => ({
        ...prev,
        isStreaming: false,
      }))
    }
  }, [options])

  // Clear messages
  const clearMessages = useCallback(() => {
    setMessages([])
    conversationIdRef.current = null
    setStreamingState({
      isStreaming: false,
      currentAgent: null,
      thinkingSteps: [],
      content: '',
      error: null,
      products: [],
      companies: [],
      industries: [],
    })
  }, [])

  // Cancel streaming
  const cancelStream = useCallback(() => {
    abortControllerRef.current?.abort()
    setStreamingState(prev => ({
      ...prev,
      isStreaming: false,
    }))
  }, [])

  // Clear products from streaming state (go back to showing all products)
  const clearProducts = useCallback(() => {
    setStreamingState(prev => ({
      ...prev,
      products: [],
    }))
  }, [])

  // Clear companies from streaming state (go back to showing all companies)
  const clearCompanies = useCallback(() => {
    setStreamingState(prev => ({
      ...prev,
      companies: [],
    }))
  }, [])

  // Clear industries from streaming state (go back to showing all industries)
  const clearIndustries = useCallback(() => {
    setStreamingState(prev => ({
      ...prev,
      industries: [],
    }))
  }, [])

  return {
    messages,
    setMessages,
    sendMessage,
    clearMessages,
    cancelStream,
    clearProducts,
    clearCompanies,
    clearIndustries,
    setResearchContentCallback,  // For research page to register content updates
    isStreaming: streamingState.isStreaming,
    streamingState,
    conversationId: conversationIdRef.current,
  }
}
