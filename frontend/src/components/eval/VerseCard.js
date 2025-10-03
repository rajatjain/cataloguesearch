import React from 'react';

const VerseCard = ({ verse, index, isActive, onClick, pdfDoc, navigateToPDFPage }) => {
    const handleClick = () => {
        onClick(index);
        if (verse.page_num && pdfDoc) {
            navigateToPDFPage(verse.page_num);
        }
    };

    return (
        <div
            className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                isActive
                    ? 'border-sky-500 bg-sky-50'
                    : 'border-slate-200 hover:border-slate-300'
            }`}
            onClick={handleClick}
        >
            <div className="flex items-center justify-between mb-2">
                <div className="flex flex-col">
                    <span className="text-sm font-medium text-sky-600">
                        {verse.type} {verse.type_start_num}{verse.type_end_num !== verse.type_start_num && `-${verse.type_end_num}`}
                    </span>
                    {verse.adhikar && (
                        <span className="text-xs text-purple-600 font-medium">
                            {verse.adhikar}
                        </span>
                    )}
                </div>
                <div className="flex items-center space-x-2">
                    <span className="text-xs bg-sky-100 text-sky-700 px-2 py-0.5 rounded">#{verse.seq_num}</span>
                    {verse.page_num && (
                        <span className="text-xs text-slate-500">
                            Page {verse.page_num}
                        </span>
                    )}
                </div>
            </div>
            <div className="text-sm text-slate-700 line-clamp-3">
                {verse.verse}
            </div>
            {verse.translation && (
                <div className="text-xs text-slate-600 mt-2 line-clamp-2">
                    {verse.translation}
                </div>
            )}
        </div>
    );
};

export default VerseCard;