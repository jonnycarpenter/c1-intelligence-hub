'use client'

import { useState } from 'react'
import { 
  X, 
  FileText, 
  Download, 
  Trash2, 
  GripVertical, 
  Headphones, 
  Share2, 
  ChevronDown,
  Plus
} from 'lucide-react'
import { Button, CategoryBadge, PriorityBadge } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { ReportItem } from '@/types'

interface ReportDrawerProps {
  isOpen: boolean
  onClose: () => void
  items: ReportItem[]
  onRemoveItem: (id: string) => void
  onClearAll: () => void
  onExport: (format: 'pdf' | 'docx' | 'pptx') => void
  onGeneratePodcast?: () => void
}

export default function ReportDrawer({
  isOpen,
  onClose,
  items,
  onRemoveItem,
  onClearAll,
  onExport,
  onGeneratePodcast,
}: ReportDrawerProps) {
  const [showExportMenu, setShowExportMenu] = useState(false)

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={cn(
          'fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 transform transition-transform duration-300 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
              <FileText size={20} className="text-emerald-600" />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900">Report Builder</h2>
              <p className="text-xs text-slate-500">{items.length} items added</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-col h-[calc(100%-73px)]">
          {items.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
                <Plus size={32} className="text-slate-400" />
              </div>
              <h3 className="font-medium text-slate-700 mb-2">No items yet</h3>
              <p className="text-sm text-slate-500 max-w-xs">
                Click "Add to Report" on any intelligence item to start building your report.
              </p>
            </div>
          ) : (
            <>
              {/* Items list */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {items.map((item, index) => (
                  <ReportItemCard
                    key={item.id}
                    item={item}
                    index={index}
                    onRemove={() => onRemoveItem(item.id)}
                  />
                ))}
              </div>

              {/* Actions */}
              <div className="border-t border-slate-200 p-4 space-y-3">
                {/* Export button with dropdown */}
                <div className="relative">
                  <Button
                    variant="primary"
                    className="w-full justify-between"
                    onClick={() => setShowExportMenu(!showExportMenu)}
                  >
                    <span className="flex items-center gap-2">
                      <Download size={18} />
                      Export Report
                    </span>
                    <ChevronDown size={16} />
                  </Button>

                  {showExportMenu && (
                    <div className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-lg shadow-lg border border-slate-200 overflow-hidden">
                      <button
                        onClick={() => {
                          onExport('pdf')
                          setShowExportMenu(false)
                        }}
                        className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 transition-colors"
                      >
                        Export as PDF
                      </button>
                      <button
                        onClick={() => {
                          onExport('docx')
                          setShowExportMenu(false)
                        }}
                        className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 transition-colors"
                      >
                        Export as Word (.docx)
                      </button>
                      <button
                        onClick={() => {
                          onExport('pptx')
                          setShowExportMenu(false)
                        }}
                        className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 transition-colors"
                      >
                        Export as PowerPoint
                      </button>
                    </div>
                  )}
                </div>

                {/* Secondary actions */}
                <div className="flex gap-2">
                  {onGeneratePodcast && (
                    <Button
                      variant="secondary"
                      className="flex-1"
                      onClick={onGeneratePodcast}
                    >
                      <Headphones size={16} />
                      Audio Summary
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    className="flex-1"
                    onClick={() => {/* Share functionality */}}
                  >
                    <Share2 size={16} />
                    Share
                  </Button>
                </div>

                {/* Clear all */}
                <Button
                  variant="ghost"
                  className="w-full text-red-600 hover:bg-red-50 hover:text-red-700"
                  onClick={onClearAll}
                >
                  <Trash2 size={16} />
                  Clear All
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}

interface ReportItemCardProps {
  item: ReportItem
  index: number
  onRemove: () => void
}

function ReportItemCard({ item, index, onRemove }: ReportItemCardProps) {
  return (
    <div className="group flex items-start gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200 hover:border-slate-300 transition-colors">
      <button className="p-1 text-slate-400 cursor-grab hover:text-slate-600 transition-colors">
        <GripVertical size={14} />
      </button>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-slate-400 font-medium">#{index + 1}</span>
          <CategoryBadge category={item.category} />
          <PriorityBadge priority={item.priority} />
        </div>
        <h4 className="text-sm font-medium text-slate-800 line-clamp-2">{item.title}</h4>
        {item.addedAt && (
          <p className="text-xs text-slate-400 mt-1">Added {item.addedAt}</p>
        )}
      </div>

      <button
        onClick={onRemove}
        className="p-1.5 rounded text-slate-400 opacity-0 group-hover:opacity-100 hover:bg-red-100 hover:text-red-600 transition-all"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
