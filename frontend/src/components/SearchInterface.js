import React, { useState, useEffect, useRef } from 'react';
import { BetaBadge } from './SharedComponents';

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

export const MetadataFilters = ({ metadata, activeFilters, onAddFilter, onRemoveFilter }) => {
    const [selectedKey, setSelectedKey] = useState("");
    const [selectedValue, setSelectedValue] = useState("");
    const [availableValues, setAvailableValues] = useState([]);
    const dropdownFilterKeys = Object.keys(metadata);
    
    useEffect(() => {
        if (selectedKey && metadata[selectedKey]) {
            setAvailableValues(metadata[selectedKey]);
            setSelectedValue("");
        } else { 
            setAvailableValues([]); 
        }
    }, [selectedKey, metadata]);
    
    const handleValueChange = (value) => {
        setSelectedValue(value);
        if (selectedKey && value) {
            onAddFilter({ key: selectedKey, value: value });
            setSelectedKey(""); 
            setSelectedValue("");
        }
    };
    
    return (
        <div className="w-1/2 space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">Filter by Category</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <select 
                    value={selectedKey} 
                    onChange={(e) => setSelectedKey(e.target.value)} 
                    className="p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 w-full text-base focus:ring-1 focus:ring-sky-500 font-sans"
                >
                    <option value="">Select Category...</option>
                    {dropdownFilterKeys.map(key => <option key={key} value={key}>{key}</option>)}
                </select>
                <select 
                    value={selectedValue} 
                    onChange={(e) => handleValueChange(e.target.value)} 
                    disabled={!selectedKey} 
                    className="p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 w-full text-base disabled:opacity-50 disabled:cursor-not-allowed focus:ring-1 focus:ring-sky-500 font-sans"
                >
                    <option value="">Select Value...</option>
                    {availableValues.map(val => <option key={val} value={val}>{val}</option>)}
                </select>
            </div>
            {activeFilters.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center pt-2">
                    <span className="font-semibold text-slate-500 text-sm">Active:</span>
                    {activeFilters.map((filter, index) => (
                        <div key={index} className="bg-sky-100 text-sky-800 px-2 py-0.5 rounded-full flex items-center gap-2 text-sm font-medium">
                            <span>{filter.key}: <strong>{filter.value}</strong></span>
                            <button onClick={() => onRemoveFilter(index)} className="text-sky-600 hover:text-sky-800 font-bold">&times;</button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export const AdvancedSearch = ({ exactMatch, setExactMatch, excludeWords, setExcludeWords }) => {
    const [showExactMatchTooltip, setShowExactMatchTooltip] = useState(false);
    const [showExcludeWordsTooltip, setShowExcludeWordsTooltip] = useState(false);

    return (
        <div className="w-1/2 space-y-3">
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
                        className="w-full p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 text-base focus:ring-1 focus:ring-sky-500 font-sans"
                    />
                </div>
            </div>
        </div>
    );
};

export const SearchOptions = ({ language, setLanguage, searchType, setSearchType }) => {
    const languageOptions = [
        { value: 'hindi', label: 'Hindi', disabled: false },
        { value: 'gujarati', label: 'Gujarati', disabled: true }
    ];
    
    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-slate-200">
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
             <div>
                <h3 className="text-sm font-semibold mb-2 text-slate-600 uppercase tracking-wider">Search Type</h3>
                <div className="flex flex-col gap-2">
                    <label className="flex items-center gap-2 text-slate-700">
                        <input
                            type="radio"
                            name="searchType"
                            value="relevance"
                            checked={searchType === 'relevance'}
                            onChange={(e) => setSearchType(e.target.value)}
                            className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500"
                        />
                        <span className="text-base font-medium flex items-center">
                            Better Relevance <span className="text-sm text-slate-500">(slower)</span><BetaBadge />
                        </span>
                    </label>
                    <label className="flex items-center gap-2 text-slate-700">
                        <input
                            type="radio"
                            name="searchType"
                            value="speed"
                            checked={searchType === 'speed'}
                            onChange={(e) => setSearchType(e.target.value)}
                            className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500"
                        />
                        <span className="text-base font-medium">
                            Better Speed <span className="text-sm text-slate-500">(slightly less relevant)</span>
                        </span>
                    </label>
                </div>
             </div>
        </div>
    );
};