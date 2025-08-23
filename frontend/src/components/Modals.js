import React, { useEffect } from 'react';

// --- MODAL COMPONENTS ---
export const ExpandModal = ({ data, onClose, isLoading }) => {
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = 'unset'; };
    }, []);

    useEffect(() => {
        const handleEsc = (event) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };
        window.addEventListener('keydown', handleEsc);

        return () => {
            window.removeEventListener('keydown', handleEsc);
        };
    }, [onClose]);
    
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

export const WelcomeModal = ({ onClose, onGoToUsageGuide }) => {
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = 'unset'; };
    }, []);

    useEffect(() => {
        const handleEsc = (event) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };
        window.addEventListener('keydown', handleEsc);

        return () => {
            window.removeEventListener('keydown', handleEsc);
        };
    }, [onClose]);
    
    return (
        <div className="fixed inset-0 bg-black bg-opacity-60 z-50 flex justify-center items-center p-4" onClick={onClose}>
            <div className="bg-white rounded-lg shadow-xl w-full max-w-md flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="p-6 text-center">
                    <div className="mb-4">
                        <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-sky-100 mb-4">
                            <span className="text-2xl">🙏😊</span>
                        </div>
                        <h2 className="text-2xl font-bold text-slate-800 mb-2">Welcome to Aagam Khoj!</h2>
                        <p className="text-slate-600 text-base leading-relaxed">
                            Please go through the "Usage Guide" to use this platform effectively.
                        </p>
                    </div>
                    <div className="flex flex-col space-y-3">
                        <button
                            onClick={onGoToUsageGuide}
                            className="w-full bg-sky-600 text-white font-semibold py-3 px-4 rounded-md hover:bg-sky-700 transition duration-300"
                        >
                            Go to Usage Guide
                        </button>
                        <button
                            onClick={onClose}
                            className="w-full bg-slate-200 text-slate-700 font-semibold py-3 px-4 rounded-md hover:bg-slate-300 transition duration-300"
                        >
                            Skip
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};