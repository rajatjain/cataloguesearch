import React from 'react';

const ProseCard = ({ prose, index, isActive, onClick, pdfDoc, navigateToPDFPage }) => {
    const subsectionCount = prose.subsections ? prose.subsections.length : 0;
    const totalParas = prose.content.length + (prose.subsections || []).reduce((sum, sub) => sum + sub.content.length, 0);

    const handleClick = () => {
        onClick(index);
        if (prose.page_num && pdfDoc) {
            navigateToPDFPage(prose.page_num);
        }
    };

    return (
        <div
            className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                isActive
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-slate-200 hover:border-slate-300'
            }`}
            onClick={handleClick}
        >
            <div className="flex items-center justify-between mb-2">
                <div className="flex flex-col flex-1">
                    <div className="flex items-center">
                        <svg className="w-4 h-4 text-emerald-600 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                        </svg>
                        <span className="text-sm font-medium text-emerald-600 line-clamp-1">
                            {prose.heading}
                        </span>
                    </div>
                    {prose.adhikar && (
                        <span className="text-xs text-purple-600 font-medium mt-1">
                            {prose.adhikar}
                        </span>
                    )}
                </div>
                <div className="flex items-center space-x-2 ml-2">
                    <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded">#{prose.seq_num}</span>
                    {prose.page_num && (
                        <span className="text-xs text-slate-500 whitespace-nowrap">
                            Page {prose.page_num}
                        </span>
                    )}
                </div>
            </div>
            {prose.content.length > 0 && (
                <div className="text-xs text-slate-600 line-clamp-2">
                    {prose.content[0]}
                </div>
            )}
            {subsectionCount > 0 && (
                <div className="text-xs text-slate-500 mt-2">
                    {subsectionCount} subsection{subsectionCount > 1 && 's'} • {totalParas} paragraph{totalParas > 1 && 's'}
                </div>
            )}
        </div>
    );
};

export default ProseCard;