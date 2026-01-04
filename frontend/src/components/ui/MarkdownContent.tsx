'use client'

import ReactMarkdown from 'react-markdown'
import { cn } from '@/lib/utils'

interface MarkdownContentProps {
    content: string
    className?: string
    isUser?: boolean
}

/**
 * A reusable component for rendering markdown content from AI agents
 * with a premium, user-friendly aesthetic.
 */
export function MarkdownContent({ content, className, isUser }: MarkdownContentProps) {
    return (
        <div className={cn(
            "text-sm leading-relaxed max-w-none",
            isUser ? "text-white" : "text-slate-700",
            className
        )}>
            <ReactMarkdown
                components={{
                    // Paragraphs with slightly more whitespace for readability
                    p: ({ children }) => (
                        <p className={cn(
                            "mb-3 last:mb-0 leading-relaxed",
                            !isUser && "font-[450]" // Medium weight for better readability on light backgrounds
                        )}>
                            {children}
                        </p>
                    ),

                    // Headings with bold, high-contrast colors
                    h1: ({ children }) => <h1 className="text-xl font-bold text-slate-900 mt-6 mb-3 first:mt-0">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-lg font-bold text-slate-900 mt-5 mb-2 first:mt-0">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-base font-bold text-slate-800 mt-4 mb-2 first:mt-0">{children}</h3>,

                    // Strong tags with high contrast
                    strong: ({ children }) => (
                        <strong className={cn(
                            "font-bold",
                            isUser ? "text-white" : "text-slate-900"
                        )}>
                            {children}
                        </strong>
                    ),

                    // Lists with custom bullets and spacing
                    ul: ({ children }) => <ul className="list-disc list-outside ml-5 space-y-2 my-4">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal list-outside ml-5 space-y-2 my-4">{children}</ol>,
                    li: ({ children }) => (
                        <li className={cn(
                            "pl-1",
                            isUser ? "text-emerald-50" : "text-slate-700 font-[450]"
                        )}>
                            {children}
                        </li>
                    ),

                    // Blockquotes for emphasized "call outs"
                    blockquote: ({ children }) => (
                        <blockquote className={cn(
                            "border-l-4 border-emerald-500 pl-4 py-2 my-5 bg-emerald-50/50 rounded-r-xl italic",
                            isUser ? "text-emerald-100 bg-white/10 border-white" : "text-slate-600"
                        )}>
                            {children}
                        </blockquote>
                    ),

                    // Code blocks for technical terms
                    code: ({ children }) => (
                        <code className={cn(
                            "px-1.5 py-0.5 rounded font-mono text-[13px] border transition-colors",
                            isUser
                                ? "bg-white/20 border-white/30 text-white"
                                : "bg-slate-100 border-slate-200 text-emerald-700"
                        )}>
                            {children}
                        </code>
                    ),

                    // Links with brand-aligned styling
                    a: ({ href, children }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={cn(
                                "font-semibold underline underline-offset-2 decoration-2 transition-all",
                                isUser
                                    ? "text-white decoration-white/40 hover:decoration-white"
                                    : "text-emerald-600 decoration-emerald-300 hover:text-emerald-700 hover:decoration-emerald-500"
                            )}
                        >
                            {children}
                        </a>
                    ),

                    // Image rendering with graceful fallback
                    img: ({ src, alt }) => (
                        <div className="my-4 overflow-hidden rounded-xl border border-slate-200 bg-slate-50 shadow-sm">
                            <img
                                src={src}
                                alt={alt || 'Visual content'}
                                className="max-w-full h-auto block mx-auto"
                                onError={(e) => {
                                    (e.target as HTMLImageElement).parentElement!.style.display = 'none'
                                }}
                            />
                            {alt && (
                                <div className="px-4 py-2 bg-white border-t border-slate-100 italic text-xs text-slate-500">
                                    {alt}
                                </div>
                            )}
                        </div>
                    ),

                    // Dividers
                    hr: () => <hr className={cn("my-6", isUser ? "border-white/20" : "border-slate-100")} />,
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    )
}
