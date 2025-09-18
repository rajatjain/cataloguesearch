import React, { useState, useEffect } from 'react';
import { CloseIcon } from './SharedComponents';
import {
    generateShareURL,
    formatShareContent,
    copyToClipboard,
    trackShareEvent
} from '../utils/shareUtils';

const ShareModal = ({ result, query, currentFilters, language, searchType, onClose }) => {
    const [shareData, setShareData] = useState({});
    const [copiedFeedback, setCopiedFeedback] = useState('');

    useEffect(() => {
        const url = generateShareURL();
        const data = formatShareContent(query, result, url, language);
        
        setShareData(data);
        
    }, [result, query, language]);

    useEffect(() => {
        const handleEsc = (event) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [onClose]);

    const handleCopyText = async () => {
        const success = await copyToClipboard(shareData.text);
        if (success) {
            setCopiedFeedback('Text copied to clipboard!');
            trackShareEvent('copy_text', query, result.document_id);
            setTimeout(() => setCopiedFeedback(''), 3000);
        } else {
            setCopiedFeedback('Failed to copy text');
            setTimeout(() => setCopiedFeedback(''), 3000);
        }
    };

    return (
        <div 
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
            onClick={onClose}
        >
            <div 
                className="bg-white rounded-lg shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-6 border-b border-slate-200">
                    <div className="flex justify-between items-center">
                        <h2 className="text-xl font-bold text-slate-800">Share Result</h2>
                        <button onClick={onClose} className="text-slate-500 hover:text-slate-700 transition-colors">
                            <CloseIcon />
                        </button>
                    </div>
                </div>

                {/* Content Preview */}
                <div className="p-6 border-b border-slate-200">
                    <div className="bg-slate-50 p-4 rounded-lg mb-4">
                        <div className="text-sm text-slate-600 mb-2">
                            <strong>Query:</strong> "{query}"
                        </div>
                        <div className="text-sm text-slate-700 mb-2 italic whitespace-pre-line">
                            <strong>Extract:</strong> "{result?.content_snippet ? result.content_snippet.replace(/<[^>]*>/g, '').trim() : 'Loading...'}"
                        </div>
                        <div className="text-sm text-slate-700 mb-2">
                            <strong>Granth:</strong> {result?.metadata?.Granth || 'Unknown Source'}
                        </div>
                        <div className="text-sm text-slate-700 mb-2">
                            <strong>{language === 'gujarati' ? 'પ્રવચનકાર:' : 'प्रवचनकार:'}</strong> {result?.Pravachankar || 'Unknown'}
                        </div>
                        <div className="text-sm text-slate-700">
                            <strong>Pravachan Details:</strong> {result?.metadata?.Series && `${result.metadata.Series}, `}{result?.original_filename ? result.original_filename.split('/').pop() : result?.filename || ''}, Page {result?.page_number || 'Unknown'}
                        </div>
                    </div>
                    
                    {copiedFeedback && (
                        <div className="bg-green-100 border border-green-300 text-green-800 px-3 py-2 rounded-md text-sm mb-4">
                            {copiedFeedback}
                        </div>
                    )}
                </div>

                {/* Share Options */}
                <div className="p-6">
                    <div className="space-y-3">
                        {/* Copy Text */}
                        <button
                            onClick={handleCopyText}
                            className="w-full flex items-center justify-center gap-3 bg-sky-600 text-white py-3 px-4 rounded-lg hover:bg-sky-700 transition-colors"
                        >
                            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            Copy Text
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ShareModal;