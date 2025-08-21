import React, { useEffect } from 'react';

// --- MODAL COMPONENTS ---
export const ExpandModal = ({ data, onClose, isLoading }) => {
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = 'unset'; };
    }, []);
    
    const Paragraph = ({ para, isCurrent }) => {
        if (!para) {
            return (
                <div className="p-3 rounded-md bg-slate-50 border border-dashed border-slate-300 text-center text-sm text-slate-400">
                    Context not available.
                </div>
            );
        }
        return (
            <div className={`p-3 rounded-md ${
                isCurrent 
                    ? "bg-sky-100 border border-sky-300 ring-2 ring-sky-200" 
                    : "bg-slate-50 border border-slate-200"
            }`}>
                <p className="text-slate-800 leading-relaxed text-base font-sans whitespace-pre-wrap">
                    {para.content_snippet}
                </p>
            </div>
        );
    };
    
    return (
        <div className="fixed inset-0 bg-black bg-opacity-60 z-50 flex justify-center items-center p-4" onClick={onClose}>
            <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="p-3 border-b border-slate-200 flex justify-between items-center">
                    <h2 className="text-lg font-bold text-slate-800 font-display">Expanded Context</h2>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-2xl font-bold">
                        &times;
                    </button>
                </div>
                <div className="p-3 md:p-4 overflow-y-auto">
                    {isLoading ? (
                        <div className="text-center py-10">
                            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500"></div>
                            <p className="mt-3 text-base text-slate-500">Loading Context...</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Paragraph para={data?.previous} />
                            <Paragraph para={data?.current} isCurrent={true} />
                            <Paragraph para={data?.next} />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};