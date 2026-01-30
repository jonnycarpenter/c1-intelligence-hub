import React from 'react';
import { ReportBlock } from '../../../types';
import { BlockCitations } from './BlockCitation';

interface BlockParagraphProps {
    block: ReportBlock;
}

export const BlockParagraph: React.FC<BlockParagraphProps> = ({ block }) => {
    const { text } = block.data;

    return (
        <div className="mb-4 text-slate-700 leading-relaxed text-sm">
            {text}
            <BlockCitations citations={block.citations} />
        </div>
    );
};
