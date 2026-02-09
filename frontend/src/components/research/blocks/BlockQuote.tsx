import React from 'react';
import { ReportBlock } from '../../../types';
import { Quote, TrendingUp, Mic, FileText } from 'lucide-react';
import { BlockCitations } from './BlockCitation';

interface BlockQuoteProps {
    block: ReportBlock;
}

type SourceType = 'earnings_call' | 'podcast' | 'sec_filing' | 'other';

interface SourceConfig {
    icon: React.ElementType;
    label: string;
    borderClass: string;
    bgClass: string;
    iconClass: string;
    quoteMarkClass: string;
    badgeClass: string;
}

const SOURCE_CONFIGS: Record<SourceType, SourceConfig> = {
    earnings_call: {
        icon: TrendingUp,
        label: 'Earnings Call',
        borderClass: 'border-amber-500/30',
        bgClass: 'from-amber-50/50',
        iconClass: 'text-amber-500',
        quoteMarkClass: 'text-amber-200',
        badgeClass: 'bg-amber-100 text-amber-700',
    },
    podcast: {
        icon: Mic,
        label: 'Podcast',
        borderClass: 'border-purple-500/30',
        bgClass: 'from-purple-50/50',
        iconClass: 'text-purple-500',
        quoteMarkClass: 'text-purple-200',
        badgeClass: 'bg-purple-100 text-purple-700',
    },
    sec_filing: {
        icon: FileText,
        label: 'SEC Filing',
        borderClass: 'border-blue-500/30',
        bgClass: 'from-blue-50/50',
        iconClass: 'text-blue-500',
        quoteMarkClass: 'text-blue-200',
        badgeClass: 'bg-blue-100 text-blue-700',
    },
    other: {
        icon: Quote,
        label: '',
        borderClass: 'border-emerald-500/30',
        bgClass: 'from-emerald-50/50',
        iconClass: 'text-emerald-400',
        quoteMarkClass: 'text-emerald-200',
        badgeClass: 'bg-emerald-100 text-emerald-700',
    },
};

export const BlockQuote: React.FC<BlockQuoteProps> = ({ block }) => {
    const { text, speaker, context, sentiment, source_type } = block.data;

    const config = SOURCE_CONFIGS[(source_type as SourceType)] || SOURCE_CONFIGS.other;
    const Icon = config.icon;

    return (
        <div className={`my-6 pl-5 border-l-4 ${config.borderClass} bg-gradient-to-r ${config.bgClass} to-transparent py-4 pr-5 rounded-r-lg relative`}>
            {/* Large decorative opening quote mark */}
            <span className={`absolute top-2 left-6 text-5xl font-serif leading-none select-none pointer-events-none ${config.quoteMarkClass}`}>
                &ldquo;
            </span>

            <div className="relative pt-4 pl-6">
                <blockquote className="text-slate-800 text-sm font-medium italic leading-relaxed">
                    {text}
                    <BlockCitations citations={block.citations} />
                </blockquote>

                {/* Attribution line */}
                <div className="mt-3 flex items-center gap-2 text-xs flex-wrap">
                    {config.label && (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${config.badgeClass}`}>
                            <Icon size={10} />
                            {config.label}
                        </span>
                    )}
                    {speaker && (
                        <span className="font-semibold text-slate-700">{speaker}</span>
                    )}
                    {context && (
                        <>
                            <span className="text-slate-300">&mdash;</span>
                            <span className="text-slate-500">{context}</span>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
