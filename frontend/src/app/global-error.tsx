'use client'

import { useEffect } from 'react'

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    useEffect(() => {
        console.error('Global error:', error)
    }, [error])

    return (
        <html>
            <body>
                <div style={{
                    minHeight: '100vh',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: '#f8fafc',
                    fontFamily: 'system-ui, -apple-system, sans-serif',
                    padding: '24px'
                }}>
                    <div style={{
                        maxWidth: '400px',
                        width: '100%',
                        backgroundColor: 'white',
                        borderRadius: '12px',
                        boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                        border: '1px solid #e2e8f0',
                        padding: '32px',
                        textAlign: 'center'
                    }}>
                        <div style={{
                            width: '64px',
                            height: '64px',
                            margin: '0 auto 24px',
                            borderRadius: '50%',
                            backgroundColor: '#fef2f2',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '32px'
                        }}>
                            ⚠️
                        </div>
                        
                        <h2 style={{
                            fontSize: '20px',
                            fontWeight: 'bold',
                            color: '#0f172a',
                            marginBottom: '8px'
                        }}>
                            Application Error
                        </h2>
                        
                        <p style={{
                            color: '#64748b',
                            marginBottom: '24px',
                            lineHeight: '1.5'
                        }}>
                            Something went wrong loading the application.
                            Please try refreshing the page.
                        </p>
                        
                        <button
                            onClick={reset}
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '12px 24px',
                                backgroundColor: '#4f46e5',
                                color: 'white',
                                fontWeight: '500',
                                borderRadius: '8px',
                                border: 'none',
                                cursor: 'pointer',
                                fontSize: '14px'
                            }}
                        >
                            🔄 Try again
                        </button>
                    </div>
                </div>
            </body>
        </html>
    )
}
