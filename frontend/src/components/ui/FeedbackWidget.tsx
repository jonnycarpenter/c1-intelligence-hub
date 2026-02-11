'use client'

import { useState } from 'react'
import { ThumbsUp, ThumbsDown, CheckCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface FeedbackWidgetProps {
    reportId: string
    reportType: 'deep_research' | 'weekly_briefing'
}

export function FeedbackWidget({ reportId, reportType }: FeedbackWidgetProps) {
    const [rating, setRating] = useState<'positive' | 'negative' | null>(null)
    const [comment, setComment] = useState('')
    const [submitted, setSubmitted] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [showComment, setShowComment] = useState(false)

    const handleRate = async (value: 'positive' | 'negative') => {
        setRating(value)
        setShowComment(true)
    }

    const handleSubmit = async () => {
        if (!rating) return
        setSubmitting(true)
        try {
            await api.submitFeedback({
                report_id: reportId,
                report_type: reportType,
                rating,
                comment: comment.trim() || undefined,
            })
            setSubmitted(true)
        } catch (err) {
            console.error('Failed to submit feedback:', err)
        } finally {
            setSubmitting(false)
        }
    }

    if (submitted) {
        return (
            <div className="flex items-center gap-2 py-3 px-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-700">
                <CheckCircle size={16} />
                Thanks for your feedback!
            </div>
        )
    }

    return (
        <div className="border border-slate-200 rounded-xl bg-slate-50/50 p-4 space-y-3">
            <div className="flex items-center gap-3">
                <span className="text-sm text-slate-500">Was this report helpful?</span>
                <div className="flex gap-1.5">
                    <button
                        onClick={() => handleRate('positive')}
                        className={cn(
                            'p-1.5 rounded-lg border transition-all',
                            rating === 'positive'
                                ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                                : 'bg-white border-slate-200 text-slate-400 hover:text-emerald-600 hover:border-emerald-200'
                        )}
                    >
                        <ThumbsUp size={16} />
                    </button>
                    <button
                        onClick={() => handleRate('negative')}
                        className={cn(
                            'p-1.5 rounded-lg border transition-all',
                            rating === 'negative'
                                ? 'bg-red-100 border-red-300 text-red-700'
                                : 'bg-white border-slate-200 text-slate-400 hover:text-red-600 hover:border-red-200'
                        )}
                    >
                        <ThumbsDown size={16} />
                    </button>
                </div>
            </div>

            {showComment && (
                <div className="space-y-2">
                    <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="Optional: tell us more..."
                        rows={2}
                        className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-300 resize-none"
                    />
                    <button
                        onClick={handleSubmit}
                        disabled={submitting}
                        className="text-sm px-3 py-1.5 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 transition-colors"
                    >
                        {submitting ? 'Sending...' : 'Submit'}
                    </button>
                </div>
            )}
        </div>
    )
}
