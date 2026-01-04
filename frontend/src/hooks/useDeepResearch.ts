'use client'

import { useState, useCallback, useRef } from 'react'

interface DeepResearchReport {
    report_id: string
    generated_at: string
    query: string
    executive_summary: {
        headline: string
        key_points: string[]
        key_metrics: Array<{ label: string, value: string }>
    }
    sections: Array<{
        section_title: string
        content: string
        citations: any[]
    }>
    field_sales: {
        offensive_angles: any[]
        defensive_angles: any[]
        questions_to_explore: string[]
    }
}

interface DeepResearchState {
    isResearching: boolean
    status: string
    clarification: any | null
    report: DeepResearchReport | null
    error: string | null
}

export function useDeepResearch() {
    const [state, setState] = useState<DeepResearchState>({
        isResearching: false,
        status: '',
        clarification: null,
        report: null,
        error: null,
    })

    const startDeepResearch = useCallback(async (query: string, history: any[] = []) => {
        setState({
            isResearching: true,
            status: 'Grooming query...',
            clarification: null,
            report: null,
            error: null,
        })

        try {
            const response = await fetch('/api/research/deep/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, history }),
            })

            if (!response.ok) throw new Error('Failed to start research')

            const reader = response.body?.getReader()
            if (!reader) throw new Error('No reader')

            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim()
                        if (dataStr === '[DONE]') break

                        try {
                            const data = JSON.parse(dataStr)

                            if (data.type === 'status') {
                                setState(prev => ({ ...prev, status: data.content }))
                            } else if (data.type === 'clarification') {
                                setState(prev => ({
                                    ...prev,
                                    isResearching: false,
                                    clarification: data.content
                                }))
                            } else if (data.type === 'report') {
                                setState(prev => ({
                                    ...prev,
                                    isResearching: false,
                                    report: data.content,
                                    status: 'Research complete'
                                }))
                            } else if (data.type === 'error') {
                                setState(prev => ({ ...prev, isResearching: false, error: data.content }))
                            }
                        } catch (e) {
                            console.error('Error parsing stream data:', e)
                        }
                    }
                }
            }
        } catch (error: any) {
            setState(prev => ({ ...prev, isResearching: false, error: error.message }))
        }
    }, [])

    return {
        ...state,
        startDeepResearch,
        resetResearch: () => setState({
            isResearching: false,
            status: '',
            clarification: null,
            report: null,
            error: null,
        })
    }
}
