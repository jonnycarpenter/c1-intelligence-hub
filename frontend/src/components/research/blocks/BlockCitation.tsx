import React from 'react';
import { ExternalLink } from 'lucide-react';
import { Citation } from '../../../types';

interface BlockCitationProps {
    citation: Citation;
    index: number;
}

export const BlockCitation: React.FC<BlockCitationProps> = ({ citation, index }) => {
    if (!citation.source_url) return null;

    return (
        <a
            href={citation.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-1.5 py-0.5 ml-1 text-[10px] font-medium text-emerald-600 bg-emerald-50 hover:bg-emerald-100 border border-emerald-100 rounded-md transition-colors align-super no-underline"
            title={`${citation.source_title} (${citation.source_date || 'No date'})`}
        >
            <span className="max-w-[100px] truncate">{citation.source_title}</span>
            <ExternalLink size={8} />
        </a>
    );
};

export const BlockCitations: React.FC<{ citations?: Citation[] }> = ({ citations }) => {
    if (!citations || citations.length === 0) return null;

    return (
        <span className="inline-flex flex-wrap items-center gap-1 ml-1">
            {citations.map((c, i) => (
                <BlockCitation key={i} citation={c} index={i} />
            ))}
        </span>
    );
};
