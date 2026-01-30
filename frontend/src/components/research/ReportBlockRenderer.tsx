import React from 'react';
import { ReportBlock, BlockType } from '../../types';
import { BlockParagraph } from './blocks/BlockParagraph';
import { BlockMetricGrid } from './blocks/BlockMetricGrid';
import { BlockVisualSplit } from './blocks/BlockVisualSplit';
import { BlockQuote } from './blocks/BlockQuote';

interface ReportBlockRendererProps {
    block: ReportBlock;
}

export const ReportBlockRenderer: React.FC<ReportBlockRendererProps> = ({ block }) => {
    switch (block.block_type) {
        case 'paragraph':
            return <BlockParagraph block={block} />;

        case 'metric_grid':
            return <BlockMetricGrid block={block} />;

        case 'visual_split':
            return <BlockVisualSplit block={block} />;

        case 'visual_hero':
            // Reuse visual split but Force fuller layout, or implement specialized Hero later
            // For now fallback to VisualSplit
            return <BlockVisualSplit block={{ ...block, data: { ...block.data, layout: 'hero' } }} />;

        case 'quote':
            return <BlockQuote block={block} />;

        default:
            console.warn(`Unknown block type: ${block.block_type}`, block);
            return null;
    }
};
