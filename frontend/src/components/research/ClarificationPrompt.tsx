'use client'

import { useState } from 'react'
import { HelpCircle, ArrowRight, MessageSquare } from 'lucide-react'
import { Button } from '@/components/ui'

interface ClarificationPromptProps {
    question: any
    onResponse: (response: string) => void
}

export default function ClarificationPrompt({ question, onResponse }: ClarificationPromptProps) {
    const [response, setResponse] = useState('')

    return (
        <div className="bg-white rounded-2xl border-2 border-emerald-100 shadow-xl p-6 max-w-2xl mx-auto">
            <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                    <HelpCircle size={24} />
                </div>
                <div>
                    <h3 className="font-bold text-slate-900 text-lg">Query Needs Clarification</h3>
                    <p className="text-sm text-slate-500">I need a bit more detail to provide the best research results.</p>
                </div>
            </div>

            <div className="bg-slate-50 rounded-xl p-4 mb-6 border border-slate-100">
                <p className="text-slate-800 font-medium leading-relaxed">
                    {question.question}
                </p>
            </div>

            <div className="space-y-4">
                {question.options && question.options.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                        {question.options.map((opt: string, idx: number) => (
                            <button
                                key={idx}
                                onClick={() => {
                                    setResponse(opt)
                                    onResponse(opt)
                                }}
                                className="px-4 py-2 bg-white border border-slate-200 rounded-full text-sm text-slate-700 hover:border-emerald-500 hover:bg-emerald-50 transition-all font-medium"
                            >
                                {opt}
                            </button>
                        ))}
                    </div>
                )}

                <div className="relative">
                    <textarea
                        value={response}
                        onChange={(e) => setResponse(e.target.value)}
                        placeholder="Provide more context or choose an option..."
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl p-4 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all min-h-[100px] resize-none"
                    />
                </div>

                <div className="flex justify-end pt-2">
                    <Button
                        onClick={() => onResponse(response)}
                        disabled={!response.trim()}
                        className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-6"
                    >
                        Submit Response
                        <ArrowRight size={16} />
                    </Button>
                </div>
            </div>
        </div>
    )
}
