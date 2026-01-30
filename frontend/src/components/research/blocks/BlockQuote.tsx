import React from 'react';
import { ReportBlock } from '../../../types';
import { Quote } from 'lucide-react';
import { BlockCitations } from './BlockCitation';

interface BlockQuoteProps {
    block: ReportBlock;
}

export const BlockQuote: React.FC<BlockQuoteProps> = ({ block }) => {
    const { text, speaker, context, sentiment } = block.data;

    return (
        <div className="my-6 pl-4 border-l-4 border-emerald-500/30 bg-gradient-to-r from-emerald-50/50 to-transparent py-2 pr-4 rounded-r-lg">
            <div className="flex gap-2">
                <Quote className="text-emerald-400 shrink-0 mt-1" size={16} fill="currentColor" fillOpacity={0.2} />
                <div>
                    <blockquote className="text-slate-800 text-sm font-medium italic leading-relaxed">
                        "{text}"
                        <BlockCitations citations={block.citations} />
                    </blockquote>
                    <div className="mt-2 flex items-center gap-2 text-xs">
                        <span className="font-semibold text-slate-700">{speaker}</span>
                        {context && (
                            <>
                                <span className="text-slate-300">•</span>
                                <span className="text-slate-500">{context}</span>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};
