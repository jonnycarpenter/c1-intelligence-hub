'use client'

import { useEffect } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    useEffect(() => {
        // Log the error to console for debugging
        console.error('Application error:', error)
    }, [error])

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
            <div className="max-w-md w-full bg-white rounded-xl shadow-lg border border-slate-200 p-8 text-center">
                <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-red-50 flex items-center justify-center">
                    <AlertCircle className="w-8 h-8 text-red-500" />
                </div>
                
                <h2 className="text-xl font-bold text-slate-900 mb-2">
                    Something went wrong
                </h2>
                
                <p className="text-slate-600 mb-6">
                    An unexpected error occurred. This might be a temporary issue.
                </p>
                
                {process.env.NODE_ENV === 'development' && error.message && (
                    <div className="mb-6 p-4 bg-slate-50 rounded-lg text-left">
                        <p className="text-xs font-mono text-slate-600 break-all">
                            {error.message}
                        </p>
                    </div>
                )}
                
                <button
                    onClick={reset}
                    className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors"
                >
                    <RefreshCw className="w-4 h-4" />
                    Try again
                </button>
            </div>
        </div>
    )
}
