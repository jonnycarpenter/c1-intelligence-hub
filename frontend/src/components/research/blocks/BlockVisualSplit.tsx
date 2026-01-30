import React, { useState } from 'react';
import { ReportBlock } from '../../../types';
import { Maximize2, X } from 'lucide-react';
import { BlockCitations } from './BlockCitation';

interface BlockVisualSplitProps {
    block: ReportBlock;
}

export const BlockVisualSplit: React.FC<BlockVisualSplitProps> = ({ block }) => {
    const { text, visual_id, image_url, caption, layout = 'text_left', data_summary } = block.data;
    const [isExpanded, setIsExpanded] = useState(false);

    // If no image, fallback to just text
    if (!image_url) {
        return (
            <div className="mb-6">
                <p className="text-slate-700 text-sm leading-relaxed">
                    {text}
                    <BlockCitations citations={block.citations} />
                </p>
            </div>
        );
    }

    return (
        <div className={`flex flex-col md:flex-row gap-6 mb-8 items-start ${layout === 'text_right' ? 'md:flex-row-reverse' : ''}`}>

            {/* Text Content */}
            <div className="flex-1 min-w-0">
                <p className="text-slate-700 text-sm leading-relaxed">
                    {text}
                    <BlockCitations citations={block.citations} />
                </p>
                {data_summary && (
                    <div className="mt-3 text-xs text-slate-500 italic border-l-2 border-slate-200 pl-3">
                        {data_summary}
                    </div>
                )}
            </div>

            {/* Visual Content */}
            <div className="w-full md:w-5/12 shrink-0">
                <div
                    className="group relative bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-all cursor-pointer"
                    onClick={() => setIsExpanded(true)}
                >
                    <div className="aspect-[4/3] bg-slate-100 relative">
                        <img
                            src={image_url}
                            alt={caption || "Research Visual"}
                            className="w-full h-full object-contain p-2"
                            loading="lazy"
                        />
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                            <span className="bg-white/90 text-slate-700 px-2 py-1 rounded text-xs font-medium flex items-center gap-1 shadow-sm">
                                <Maximize2 size={12} />
                                Expand
                            </span>
                        </div>
                    </div>
                    {caption && (
                        <div className="p-2 bg-slate-50 border-t border-slate-100">
                            <p className="text-[10px] text-slate-500 leading-tight text-center">
                                {caption}
                            </p>
                        </div>
                    )}
                </div>
            </div>

            {/* Lightbox Modal */}
            {isExpanded && (
                <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setIsExpanded(false)}>
                    <div className="relative max-w-5xl w-full bg-white rounded-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200" onClick={e => e.stopPropagation()}>
                        <div className="flex justify-between items-center p-3 border-b border-slate-100 bg-slate-50/50">
                            <h3 className="text-sm font-medium text-slate-700 truncate pr-4">
                                {caption || "Visual Detail"}
                            </h3>
                            <button
                                onClick={() => setIsExpanded(false)}
                                className="p-1 hover:bg-slate-200 rounded-full text-slate-500 transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="p-1 bg-slate-50 md:p-8 flex items-center justify-center min-h-[400px]">
                            <img
                                src={image_url}
                                alt={caption}
                                className="max-h-[80vh] w-auto max-w-full object-contain shadow-lg rounded"
                            />
                        </div>

                        {data_summary && (
                            <div className="p-4 bg-slate-50 border-t border-slate-100 text-xs text-slate-600">
                                <span className="font-semibold text-slate-800">Data Summary:</span> {data_summary}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
