import React from 'react';
import { ReportBlock } from '../../../types';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface BlockMetricGridProps {
    block: ReportBlock;
}

export const BlockMetricGrid: React.FC<BlockMetricGridProps> = ({ block }) => {
    const metrics = block.data.metrics || [];
    if (!metrics.length) return null;

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {metrics.map((metric: any, idx: number) => (
                <div key={idx} className="bg-slate-50 border border-slate-100 rounded-lg p-3">
                    <div className="text-xs text-slate-500 font-medium mb-1 truncate">
                        {metric.label || metric.metric_name}
                    </div>
                    <div className="text-lg font-bold text-slate-900 mb-1">
                        {metric.value}
                    </div>
                    {metric.context && (
                        <div className="text-[10px] text-slate-500 flex items-center gap-1">
                            {metric.context.includes('+') ? (
                                <TrendingUp size={10} className="text-emerald-500" />
                            ) : metric.context.includes('-') && !metric.context.includes('stable') ? (
                                <TrendingDown size={10} className="text-rose-500" />
                            ) : (
                                <Minus size={10} className="text-slate-400" />
                            )}
                            {metric.context}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};
