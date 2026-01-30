'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import {
  ChevronDown,
  ChevronRight,
  GripVertical,
  X,
  FileText,
  Plus,
  Loader2,
  ExternalLink,
  Copy,
  Check
} from 'lucide-react'
import { Button } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { ResearchSection as ResearchSectionType, Source, ReportBlock } from '@/types'
import ReactMarkdown from 'react-markdown'
import { ReportBlockRenderer } from './ReportBlockRenderer'

interface ResearchSectionProps {
  section: ResearchSectionType
  isActive?: boolean  // Currently being generated
  onCollapse: (id: string) => void
  onDelete: (id: string) => void
  onAddToReport: (section: ResearchSectionType) => void
  onDragStart?: (e: React.DragEvent, id: string) => void
  onDragOver?: (e: React.DragEvent) => void
  onDrop?: (e: React.DragEvent, targetId: string) => void
  isDragging?: boolean
  dragOverId?: string | null
}

export default function ResearchSection({
  section,
  isActive = false,
  onCollapse,
  onDelete,
  onAddToReport,
  onDragStart,
  onDragOver,
  onDrop,
  isDragging = false,
  dragOverId = null,
}: ResearchSectionProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [copied, setCopied] = useState(false)
  const [mounted, setMounted] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  // Auto-scroll to bottom when content updates (for active sections)
  useEffect(() => {
    if (isActive && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [section.content, isActive])

  // Copy content to clipboard
  const handleCopy = useCallback(async () => {
    if (!section.content) return
    try {
      await navigator.clipboard.writeText(section.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }, [section.content])

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div
      className={cn(
        "bg-white rounded-xl border transition-all duration-200",
        isActive && "border-emerald-300 shadow-lg shadow-emerald-100",
        !isActive && "border-slate-200 hover:border-slate-300",
        isDragging && "opacity-50",
        dragOverId === section.id && "border-emerald-400 border-2"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      draggable
      onDragStart={(e) => onDragStart?.(e, section.id)}
      onDragOver={onDragOver}
      onDrop={(e) => onDrop?.(e, section.id)}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
        {/* Drag Handle */}
        <div
          className={cn(
            "cursor-grab active:cursor-grabbing text-slate-300 hover:text-slate-500 transition-colors",
            isHovered ? "opacity-100" : "opacity-0"
          )}
        >
          <GripVertical size={16} />
        </div>

        {/* Collapse Toggle */}
        <button
          onClick={() => onCollapse(section.id)}
          className="p-1 rounded hover:bg-slate-100 transition-colors"
        >
          {section.isCollapsed ? (
            <ChevronRight size={16} className="text-slate-500" />
          ) : (
            <ChevronDown size={16} className="text-slate-500" />
          )}
        </button>

        {/* Title & Meta */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-800 truncate">
            {section.title}
          </h3>
          <p className="text-xs text-slate-400 truncate">
            {section.query}
          </p>
        </div>

        {/* Status / Actions */}
        <div className="flex items-center gap-2">
          {isActive && (
            <div className="flex items-center gap-1.5 px-2 py-1 bg-emerald-50 rounded-full">
              <Loader2 size={12} className="text-emerald-600 animate-spin" />
              <span className="text-xs text-emerald-700 font-medium">Generating</span>
            </div>
          )}

          <span className="text-xs text-slate-400">
            {mounted ? formatTimestamp(section.timestamp) : ''}
          </span>

          {/* Copy Button */}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className={cn(
              "gap-1.5 transition-opacity",
              isHovered || isActive ? "opacity-100" : "opacity-0"
            )}
            disabled={!section.content}
          >
            {copied ? (
              <>
                <Check size={14} className="text-emerald-500" />
                <span className="text-xs text-emerald-500">Copied!</span>
              </>
            ) : (
              <>
                <Copy size={14} />
                <span className="text-xs">Copy</span>
              </>
            )}
          </Button>

          {/* Add to Report Button */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onAddToReport(section)}
            className={cn(
              "gap-1.5 transition-opacity",
              isHovered || isActive ? "opacity-100" : "opacity-0"
            )}
          >
            <Plus size={14} />
            <span className="text-xs">Add to Report</span>
          </Button>

          {/* Delete Button */}
          <button
            onClick={() => onDelete(section.id)}
            className={cn(
              "p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-500 transition-all",
              isHovered ? "opacity-100" : "opacity-0"
            )}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Content */}
      {!section.isCollapsed && (
        <div
          ref={contentRef}
          className="p-4 max-h-[500px] overflow-y-auto select-text"
        >
          {section.blocks && section.blocks.length > 0 ? (
            <div className="space-y-4">
              {section.blocks.map((block) => (
                <ReportBlockRenderer key={block.block_id} block={block} />
              ))}
            </div>
          ) : section.content ? (
            <div className="prose prose-sm prose-slate max-w-none select-text cursor-text">
              <ReactMarkdown
                components={{
                  h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-lg font-bold text-slate-800 mb-3">{children}</h1>,
                  h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-base font-semibold text-slate-800 mt-4 mb-2">{children}</h2>,
                  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-sm font-semibold text-slate-700 mt-3 mb-1">{children}</h3>,
                  p: ({ children }: { children?: React.ReactNode }) => <p className="text-slate-600 mb-2 leading-relaxed">{children}</p>,
                  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc list-inside space-y-1 mb-3">{children}</ul>,
                  ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal list-inside space-y-1 mb-3">{children}</ol>,
                  li: ({ children }: { children?: React.ReactNode }) => <li className="text-slate-600">{children}</li>,
                  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-semibold text-slate-800">{children}</strong>,
                  blockquote: ({ children }: { children?: React.ReactNode }) => (
                    <blockquote className="border-l-4 border-emerald-300 pl-4 my-3 text-slate-600 italic">
                      {children}
                    </blockquote>
                  ),
                  code: ({ children }: { children?: React.ReactNode }) => (
                    <code className="bg-slate-100 px-1.5 py-0.5 rounded text-sm font-mono text-slate-700">
                      {children}
                    </code>
                  ),
                  table: ({ children }: { children?: React.ReactNode }) => (
                    <div className="overflow-x-auto my-4">
                      <table className="min-w-full divide-y divide-slate-200 text-sm">
                        {children}
                      </table>
                    </div>
                  ),
                  th: ({ children }: { children?: React.ReactNode }) => (
                    <th className="px-3 py-2 text-left font-semibold text-slate-700 bg-slate-50">
                      {children}
                    </th>
                  ),
                  td: ({ children }: { children?: React.ReactNode }) => (
                    <td className="px-3 py-2 text-slate-600 border-t border-slate-100">
                      {children}
                    </td>
                  ),
                }}
              >
                {section.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <Loader2 size={20} className="animate-spin mr-2" />
              <span>Generating analysis...</span>
            </div>
          )}

          {/* Sources */}
          {section.sources && section.sources.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Sources
              </h4>
              <div className="flex flex-wrap gap-2">
                {section.sources.map((source, idx) => (
                  <a
                    key={idx}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-2 py-1 bg-slate-50 hover:bg-slate-100 rounded text-xs text-slate-600 hover:text-emerald-600 transition-colors"
                  >
                    <FileText size={10} />
                    <span className="truncate max-w-[150px]">{source.title || source.name}</span>
                    <ExternalLink size={10} />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
