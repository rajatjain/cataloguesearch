import React, { useState, useEffect, useRef } from 'react';

// --- SEARCH INTERFACE COMPONENTS ---
export const SearchBar = ({ query, setQuery, onSearch }) => {
    const inputRef = useRef(null);

    useEffect(() => {
        // Auto-focus search box when component mounts
        if (inputRef.current) {
            inputRef.current.focus();
        }
    }, []);

    useEffect(() => {
        const handleKeyPress = (event) => {
            // Only focus if "/" is pressed and we're not already in an input field
            if (event.key === '/' && 
                !['INPUT', 'TEXTAREA'].includes(event.target.tagName) &&
                inputRef?.current) {
                event.preventDefault();
                inputRef.current.focus();
            }
        };

        document.addEventListener('keydown', handleKeyPress);

        return () => {
            document.removeEventListener('keydown', handleKeyPress);
        };
    }, [inputRef]);

    return (
        <div className="relative">
            <input 
                ref={inputRef}
                type="text" 
                value={query} 
                onChange={(e) => setQuery(e.target.value)} 
                onKeyDown={(e) => e.key === 'Enter' && onSearch()} 
                placeholder="Enter your search query..." 
                className="w-full p-3 pl-4 text-lg bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 text-slate-900 font-sans" 
            />
        </div>
    );
};

export const MetadataFilters = ({ metadata, activeFilters, onAddFilter, onRemoveFilter, contentTypes, setContentTypes }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [granthMode, setGranthMode] = useState('all'); // 'all' or 'specific'
    const [selectedGranths, setSelectedGranths] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');

    const availableGranths = metadata['Granth'] || [];
    const filteredGranths = availableGranths.filter(granth =>
        granth.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Sync selectedGranths with activeFilters on mount and when filters change
    useEffect(() => {
        const granthFilters = activeFilters.filter(f => f.key === 'Granth');
        if (granthFilters.length > 0) {
            setGranthMode('specific');
            setSelectedGranths(granthFilters.map(f => f.value));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Handle Escape key to close modal
    useEffect(() => {
        const handleEsc = (event) => {
            if (event.key === 'Escape') {
                setIsOpen(false);
            }
        };
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, []);

    const handleGranthToggle = (granth) => {
        setSelectedGranths(prev => {
            if (prev.includes(granth)) {
                return prev.filter(g => g !== granth);
            } else {
                return [...prev, granth];
            }
        });
    };

    const handleApply = () => {
        // Remove all existing Granth filters first
        const granthFilterIndices = [];
        activeFilters.forEach((filter, index) => {
            if (filter.key === 'Granth') {
                granthFilterIndices.push(index);
            }
        });
        // Remove in reverse order to maintain correct indices
        granthFilterIndices.reverse().forEach(index => {
            onRemoveFilter(index);
        });

        // Add back the Granth filters based on mode
        if (granthMode === 'specific' && selectedGranths.length > 0) {
            selectedGranths.forEach(granth => {
                onAddFilter({ key: 'Granth', value: granth });
            });
        }

        setIsOpen(false);
    };

    const handleClearAll = () => {
        setGranthMode('all');
        setSelectedGranths([]);
        setContentTypes({ pravachans: true, granths: true });
        setSearchTerm('');
        // Remove all Granth filters
        const granthFilterIndices = [];
        activeFilters.forEach((filter, index) => {
            if (filter.key === 'Granth') {
                granthFilterIndices.push(index);
            }
        });
        // Remove in reverse order to maintain correct indices
        granthFilterIndices.reverse().forEach(index => {
            onRemoveFilter(index);
        });
    };

    const granthFilterCount = activeFilters.filter(f => f.key === 'Granth').length;

    const getContentTypeText = () => {
        if (contentTypes.pravachans && contentTypes.granths) {
            return 'Both';
        } else if (contentTypes.pravachans) {
            return 'Pravachans only';
        } else if (contentTypes.granths) {
            return 'Granths only';
        }
        return 'None selected';
    };

    const getSummaryText = () => {
        const hasContentTypeFilter = !contentTypes.pravachans || !contentTypes.granths;
        const totalActiveFilters = granthFilterCount + (hasContentTypeFilter ? 1 : 0);

        if (totalActiveFilters === 0) {
            return 'All Content';
        }

        return `Filters (${totalActiveFilters})`;
    };

    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">Refine Search</h3>

            {/* Filter Button */}
            <button
                onClick={() => setIsOpen(true)}
                className="w-full p-3 bg-slate-50 border border-slate-300 rounded-md text-left text-slate-800 text-base hover:bg-slate-100 transition-colors focus:ring-2 focus:ring-sky-500 flex items-center justify-between"
            >
                <span>{getSummaryText()}</span>
                <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {/* Active Filters */}
            {(granthFilterCount > 0 || (!contentTypes.pravachans || !contentTypes.granths)) && (
                <div className="flex flex-wrap gap-1.5 items-center">
                    <span className="font-semibold text-slate-500 text-sm">Active:</span>

                    {/* Content Type Chip (only if not "Both") */}
                    {(!contentTypes.pravachans || !contentTypes.granths) && (
                        <div className="bg-purple-100 text-purple-800 px-2 py-1 rounded-full flex items-center gap-2 text-sm font-medium">
                            <span>{getContentTypeText()}</span>
                            <button
                                onClick={() => setContentTypes({ pravachans: true, granths: true })}
                                className="text-purple-600 hover:text-purple-800 font-bold"
                            >
                                &times;
                            </button>
                        </div>
                    )}

                    {/* Granth Filters - Show summary if more than 3, otherwise show individual chips */}
                    {granthFilterCount > 3 ? (
                        <div className="bg-sky-100 text-sky-800 px-2 py-1 rounded-full flex items-center gap-2 text-sm font-medium">
                            <span>{granthFilterCount} Granths selected</span>
                            <button
                                onClick={() => setIsOpen(true)}
                                className="text-sky-600 hover:text-sky-800 font-bold text-xs"
                                title="Click to view/edit selections"
                            >
                                View
                            </button>
                        </div>
                    ) : (
                        activeFilters.filter(f => f.key === 'Granth').map((filter, index) => (
                            <div key={index} className="bg-sky-100 text-sky-800 px-2 py-1 rounded-full flex items-center gap-2 text-sm font-medium">
                                <span>{filter.value}</span>
                                <button
                                    onClick={() => {
                                        const actualIndex = activeFilters.findIndex(f => f.key === 'Granth' && f.value === filter.value);
                                        onRemoveFilter(actualIndex);
                                        setSelectedGranths(prev => prev.filter(g => g !== filter.value));
                                        if (activeFilters.filter(f => f.key === 'Granth').length === 1) {
                                            setGranthMode('all');
                                        }
                                    }}
                                    className="text-sky-600 hover:text-sky-800 font-bold"
                                >
                                    &times;
                                </button>
                            </div>
                        ))
                    )}
                </div>
            )}

            {/* Modal/Bottom Sheet */}
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 bg-black bg-opacity-50 z-40"
                        onClick={() => setIsOpen(false)}
                    />

                    {/* Modal Content */}
                    <div className="fixed inset-x-0 bottom-0 md:inset-0 md:flex md:items-center md:justify-center z-50">
                        <div className="bg-white rounded-t-xl md:rounded-xl shadow-2xl w-full md:max-w-lg md:max-h-[80vh] flex flex-col max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
                            {/* Header */}
                            <div className="p-4 border-b border-slate-200 flex items-center justify-between sticky top-0 bg-white rounded-t-xl md:rounded-t-xl">
                                <h3 className="text-lg font-bold text-slate-800">Filters</h3>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="text-slate-400 hover:text-slate-600 p-1"
                                >
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>

                            {/* Content */}
                            <div className="p-4 overflow-y-auto flex-1">
                                {/* Content Type Section */}
                                <div className="mb-6">
                                    <h4 className="text-sm font-semibold text-slate-600 mb-3">Content Type</h4>
                                    <div className="grid grid-cols-2 gap-2">
                                        <button
                                            onClick={() => setContentTypes(prev => ({ ...prev, pravachans: !prev.pravachans }))}
                                            className={`p-2.5 rounded-md border-2 font-medium transition-all text-sm flex items-center justify-center gap-1.5 ${
                                                contentTypes.pravachans
                                                    ? 'border-sky-500 bg-sky-50 text-sky-700'
                                                    : 'border-slate-300 bg-white text-slate-600'
                                            }`}
                                        >
                                            {contentTypes.pravachans && (
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                                </svg>
                                            )}
                                            🎙️ Pravachan on Granths
                                        </button>
                                        <button
                                            onClick={() => setContentTypes(prev => ({ ...prev, granths: !prev.granths }))}
                                            className={`p-2.5 rounded-md border-2 font-medium transition-all text-sm flex items-center justify-center gap-1.5 ${
                                                contentTypes.granths
                                                    ? 'border-sky-500 bg-sky-50 text-sky-700'
                                                    : 'border-slate-300 bg-white text-slate-600'
                                            }`}
                                        >
                                            {contentTypes.granths && (
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                                </svg>
                                            )}
                                            📜 Mool Shastra
                                        </button>
                                    </div>
                                </div>

                                <div className="border-t border-slate-200 pt-4 mb-4"></div>

                                {/* Granth Filter Section */}
                                <div>
                                    <h4 className="text-sm font-semibold text-slate-600 mb-3">Filter by ...</h4>

                                    {/* Radio Buttons */}
                                    <div className="space-y-2 mb-4">
                                        <label className="flex items-center gap-2 text-slate-700 cursor-pointer">
                                            <input
                                                type="radio"
                                                name="granthMode"
                                                checked={granthMode === 'all'}
                                                onChange={() => {
                                                    setGranthMode('all');
                                                    setSelectedGranths([]);
                                                }}
                                                className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500"
                                            />
                                            <span className="text-base font-medium">All Granths</span>
                                        </label>
                                        <label className="flex items-center gap-2 text-slate-700 cursor-pointer">
                                            <input
                                                type="radio"
                                                name="granthMode"
                                                checked={granthMode === 'specific'}
                                                onChange={() => setGranthMode('specific')}
                                                className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500"
                                            />
                                            <span className="text-base font-medium">Specific Granths</span>
                                        </label>
                                    </div>

                                    {/* Granth Selection */}
                                    {granthMode === 'specific' && (
                                        <div className="space-y-3">
                                            <div className="text-sm text-slate-500 mb-2">
                                                Select specific Granths:
                                            </div>

                                            {/* Search Box */}
                                            <input
                                                type="text"
                                                value={searchTerm}
                                                onChange={(e) => setSearchTerm(e.target.value)}
                                                placeholder="🔍 Search Granths..."
                                                className="w-full p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 text-base focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
                                            />

                                            {/* Granth List */}
                                            <div className="relative">
                                                <div
                                                    className="max-h-64 overflow-y-auto border border-slate-200 rounded-md"
                                                    style={{
                                                        scrollbarWidth: 'thin',
                                                        scrollbarColor: '#94a3b8 #f1f5f9'
                                                    }}
                                                >
                                                    <style>{`
                                                        .max-h-64::-webkit-scrollbar {
                                                            width: 8px;
                                                        }
                                                        .max-h-64::-webkit-scrollbar-track {
                                                            background: #f1f5f9;
                                                            border-radius: 4px;
                                                        }
                                                        .max-h-64::-webkit-scrollbar-thumb {
                                                            background: #94a3b8;
                                                            border-radius: 4px;
                                                        }
                                                        .max-h-64::-webkit-scrollbar-thumb:hover {
                                                            background: #64748b;
                                                        }
                                                    `}</style>
                                                    {filteredGranths.length > 0 ? (
                                                        filteredGranths.map((granth, index) => (
                                                            <label
                                                                key={index}
                                                                className="flex items-center gap-3 p-3 hover:bg-slate-50 cursor-pointer border-b border-slate-100 last:border-b-0"
                                                            >
                                                                <input
                                                                    type="checkbox"
                                                                    checked={selectedGranths.includes(granth)}
                                                                    onChange={() => handleGranthToggle(granth)}
                                                                    className="form-checkbox h-5 w-5 text-sky-600 focus:ring-sky-500 rounded"
                                                                />
                                                                <span className="text-slate-700">{granth}</span>
                                                            </label>
                                                        ))
                                                    ) : (
                                                        <div className="p-4 text-center text-slate-500 text-sm">
                                                            No Granths found
                                                        </div>
                                                    )}
                                                </div>
                                                {filteredGranths.length > 5 && (
                                                    <div className="text-center text-xs text-slate-400 mt-1">
                                                        ↓ Scroll for more ↓
                                                    </div>
                                                )}
                                            </div>

                                            {selectedGranths.length > 0 && (
                                                <div className="text-sm text-slate-600">
                                                    {selectedGranths.length} Granth{selectedGranths.length > 1 ? 's' : ''} selected
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Footer */}
                            <div className="p-4 border-t border-slate-200 flex gap-2 sticky bottom-0 bg-white rounded-b-xl md:rounded-b-xl">
                                <button
                                    onClick={handleClearAll}
                                    className="flex-1 px-4 py-2 border border-slate-300 rounded-md text-slate-700 font-semibold hover:bg-slate-50 transition-colors"
                                >
                                    Clear All
                                </button>
                                <button
                                    onClick={handleApply}
                                    className="flex-1 px-4 py-2 bg-sky-600 text-white rounded-md font-semibold hover:bg-sky-700 transition-colors"
                                >
                                    Apply {granthMode === 'specific' && selectedGranths.length > 0 && `(${selectedGranths.length})`}
                                </button>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export const AdvancedSearch = ({ exactMatch, setExactMatch, excludeWords, setExcludeWords }) => {
    const [showExactMatchTooltip, setShowExactMatchTooltip] = useState(false);
    const [showExcludeWordsTooltip, setShowExcludeWordsTooltip] = useState(false);

    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">Advanced Search</h3>
            <div className="space-y-3">
                <div className="relative">
                    <label className="flex items-center gap-2 text-slate-700">
                        <input
                            type="checkbox"
                            checked={exactMatch}
                            onChange={(e) => setExactMatch(e.target.checked)}
                            className="form-checkbox h-4 w-4 text-sky-600 focus:ring-sky-500 rounded"
                        />
                        <span className="text-base font-medium">Exact Phrase Match</span>
                        <button
                            type="button"
                            className="text-slate-400 hover:text-slate-600 cursor-help ml-1 transition-colors"
                            onMouseEnter={() => setShowExactMatchTooltip(true)}
                            onMouseLeave={() => setShowExactMatchTooltip(false)}
                            onClick={() => setShowExactMatchTooltip(!showExactMatchTooltip)}
                        >
                            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                            </svg>
                        </button>
                    </label>
                    {showExactMatchTooltip && (
                        <div className="absolute left-0 top-full mt-1 bg-slate-800 text-white text-xs rounded px-2 py-1 z-10 whitespace-nowrap">
                            Search for the exact phrase rather than individual words
                        </div>
                    )}
                </div>
                <div>
                    <div className="relative">
                        <label className="block text-sm font-medium text-slate-700 mb-1">
                            Exclude Words
                            <button
                                type="button"
                                className="text-slate-400 hover:text-slate-600 cursor-help ml-1 transition-colors"
                                onMouseEnter={() => setShowExcludeWordsTooltip(true)}
                                onMouseLeave={() => setShowExcludeWordsTooltip(false)}
                                onClick={() => setShowExcludeWordsTooltip(!showExcludeWordsTooltip)}
                            >
                                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                                </svg>
                            </button>
                        </label>
                        {showExcludeWordsTooltip && (
                            <div className="absolute left-0 top-full mt-1 bg-slate-800 text-white text-xs rounded px-2 py-1 z-10 whitespace-nowrap">
                                Enter words separated by commas to exclude from results
                            </div>
                        )}
                    </div>
                    <input
                        type="text"
                        value={excludeWords}
                        onChange={(e) => setExcludeWords(e.target.value)}
                        placeholder="word1, word2, word3..."
                        className="w-1/2 p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 text-base focus:ring-1 focus:ring-sky-500 font-sans"
                    />
                </div>
            </div>
        </div>
    );
};

export const SearchOptions = ({ language, setLanguage }) => {
    const languageOptions = [
        { value: 'hindi', label: 'Hindi', disabled: false },
        { value: 'gujarati', label: 'Gujarati', disabled: false }
    ];
    
    return (
        <div>
            <div>
                <h3 className="text-sm font-semibold mb-2 text-slate-600 uppercase tracking-wider">Language</h3>
                <div className="flex gap-4">
                    {languageOptions.map(lang => (
                        <label key={lang.value} className={`flex items-center gap-1.5 text-base ${lang.disabled ? 'text-slate-400 cursor-not-allowed' : 'text-slate-700 cursor-pointer'}`}>
                            <input 
                                type="radio" 
                                name="language" 
                                value={lang.value} 
                                checked={language === lang.value} 
                                onChange={(e) => setLanguage(e.target.value)} 
                                disabled={lang.disabled}
                                className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500 disabled:opacity-50 disabled:cursor-not-allowed" 
                            />
                            <span className="capitalize">
                                {lang.label}
                                {lang.disabled && <span className="ml-1 text-xs text-slate-400">(Coming soon)</span>}
                            </span>
                        </label>
                    ))}
                </div>
            </div>
        </div>
    );
};
