import React, { useState, useEffect } from 'react';
import { BetaBadge } from './SharedComponents';

// --- SEARCH INTERFACE COMPONENTS ---
export const SearchBar = ({ query, setQuery, onSearch }) => (
    <div className="relative">
        <input 
            type="text" 
            value={query} 
            onChange={(e) => setQuery(e.target.value)} 
            onKeyDown={(e) => e.key === 'Enter' && onSearch()} 
            placeholder="Enter your search query..." 
            className="w-full p-3 pl-4 text-lg bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 text-slate-900 font-sans" 
        />
    </div>
);

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
    
    const handleAddClick = () => {
        if (selectedKey && selectedValue) {
            onAddFilter({ key: selectedKey, value: selectedValue });
            setSelectedKey(""); 
            setSelectedValue("");
        }
    };
    
    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">Filter by Category</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
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
                    onChange={(e) => setSelectedValue(e.target.value)} 
                    disabled={!selectedKey} 
                    className="p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 w-full text-base disabled:opacity-50 disabled:cursor-not-allowed focus:ring-1 focus:ring-sky-500 font-sans"
                >
                    <option value="">Select Value...</option>
                    {availableValues.map(val => <option key={val} value={val}>{val}</option>)}
                </select>
                <button 
                    onClick={handleAddClick} 
                    disabled={!selectedKey || !selectedValue} 
                    className="p-2 bg-sky-600 text-white font-semibold rounded-md hover:bg-sky-700 transition duration-200 disabled:bg-slate-300 disabled:cursor-not-allowed text-base font-sans"
                >
                    Add Filter
                </button>
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

export const SearchOptions = ({ language, setLanguage, proximity, setProximity, searchType, setSearchType }) => {
    const languageOptions = ['hindi', 'gujarati', 'both'];
    const proximityOptions = [
        { label: 'Exact Phrase', value: 0 },
        { label: 'Near (10)', value: 10 },
        { label: 'Medium (20)', value: 20 },
        { label: 'Far (30)', value: 30 }
    ];
    
    return (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-3 border-t border-slate-200">
             <div>
                <h3 className="text-sm font-semibold mb-2 text-slate-600 uppercase tracking-wider">Language</h3>
                <div className="flex gap-4">
                    {languageOptions.map(lang => (
                        <label key={lang} className="flex items-center gap-1.5 text-slate-700 capitalize text-base">
                            <input 
                                type="radio" 
                                name="language" 
                                value={lang} 
                                checked={language === lang} 
                                onChange={(e) => setLanguage(e.target.value)} 
                                className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500" 
                            />
                            {lang}
                        </label>
                    ))}
                </div>
             </div>
             <div>
                <h3 className="text-sm font-semibold mb-2 text-slate-600 uppercase tracking-wider">Proximity</h3>
                <div className="flex flex-wrap gap-3">
                    {proximityOptions.map(opt => (
                        <label key={opt.value} className="flex items-center gap-1.5 text-base text-slate-700">
                            <input
                                type="radio"
                                name="proximity"
                                value={opt.value}
                                checked={proximity === opt.value}
                                onChange={() => setProximity(opt.value)}
                                className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500"
                            />
                            {opt.label}
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