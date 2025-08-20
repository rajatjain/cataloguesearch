import React, { useState, useEffect, useCallback, useRef } from 'react';

// --- API SERVICE ---
const API_BASE_URL = '/api';

const api = {
    getMetadata: async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/metadata`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) { console.error("API Error: Could not fetch metadata", error); return {}; }
    },
    search: async (requestPayload) => {
        try {
            const response = await fetch(`${API_BASE_URL}/search`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestPayload),
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            return { ...data, results: data.results || [], vector_results: data.vector_results || [] };
        } catch (error) { console.error("API Error: Could not perform search", error); return { total_results: 0, results: [], total_vector_results: 0, vector_results: [] }; }
    },
    getSimilarDocuments: async (docId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/similar-documents/${docId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            return { ...data, results: data.results || [] };
        } catch (error) { console.error("API Error: Could not fetch similar documents", error); return { total_results: 0, results: [] }; }
    },
    getParagraphContext: async (chunkId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/context/${chunkId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) { console.error("API Error: Could not fetch context", error); return null; }
    }
};

// --- HELPER & ICON COMPONENTS ---
const Spinner = () => <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>;
const ChevronUpIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" /></svg>;
const ChevronDownIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" /></svg>;
const SimilarIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor"><path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>;
const ExpandIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 1v4m0 0h-4m4 0l-5-5" /></svg>;
const PdfIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>;
const BetaBadge = () => <span className="inline-block bg-orange-100 text-orange-800 text-xs font-semibold px-2 py-0.5 rounded-full ml-2">BETA</span>;
const MenuIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>;
const CloseIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>;


// --- UI COMPONENTS ---
const Navigation = ({ currentPage, setCurrentPage }) => {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    
    const menuItems = [
        { id: 'home', label: 'Home', showSearch: true },
        { id: 'aagam-khoj', label: 'Aagam Khoj', showSearch: true },
        { id: 'about', label: 'About', showSearch: false },
        { id: 'contact', label: 'Contact/Feedback', showSearch: false }
    ];
    
    const handleMenuClick = (itemId) => {
        setCurrentPage(itemId);
        setIsMobileMenuOpen(false);
    };
    
    return (
        <nav className="bg-white shadow-sm border-b border-slate-200 sticky top-0 z-40">
            <div className="max-w-6xl mx-auto px-4">
                <div className="flex items-center justify-between h-16">
                    {/* Logo */}
                    <div className="flex items-center space-x-4">
                        <img 
                            src="/images/swalakshya.png" 
                            alt="Swalakshya Logo" 
                            className="h-10 w-auto" 
                            onError={(e) => { e.target.onerror = null; e.target.src='https://placehold.co/40x40/f1f5f9/475569?text=S' }} 
                        />
                    </div>
                    
                    {/* Desktop Menu */}
                    <div className="hidden md:flex space-x-8">
                        {menuItems.map((item) => (
                            <button
                                key={item.id}
                                onClick={() => handleMenuClick(item.id)}
                                className={`px-3 py-2 text-base font-medium transition-colors duration-200 ${
                                    currentPage === item.id 
                                        ? 'text-sky-600 border-b-2 border-sky-600' 
                                        : 'text-slate-600 hover:text-slate-900'
                                }`}
                            >
                                {item.label}
                            </button>
                        ))}
                    </div>
                    
                    {/* Mobile Menu Button */}
                    <div className="md:hidden">
                        <button
                            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                            className="p-2 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors duration-200"
                        >
                            {isMobileMenuOpen ? <CloseIcon /> : <MenuIcon />}
                        </button>
                    </div>
                </div>
                
                {/* Mobile Menu */}
                {isMobileMenuOpen && (
                    <div className="md:hidden border-t border-slate-200 bg-white">
                        <div className="px-2 pt-2 pb-3 space-y-1">
                            {menuItems.map((item) => (
                                <button
                                    key={item.id}
                                    onClick={() => handleMenuClick(item.id)}
                                    className={`block w-full text-left px-3 py-2 text-base font-medium rounded-md transition-colors duration-200 ${
                                        currentPage === item.id 
                                            ? 'text-sky-600 bg-sky-50' 
                                            : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                                    }`}
                                >
                                    {item.label}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </nav>
    );
};

const Header = ({ currentPage }) => {
    if (currentPage === 'about') {
        return (
            <div className="text-center py-12">
                <h1 className="text-4xl font-bold text-slate-800 mb-4">About Aagam-Khoj</h1>
                <div className="max-w-2xl mx-auto text-slate-600 space-y-4">
                    <p>Aagam-Khoj (आगम-खोज) is a comprehensive search platform for exploring the profound teachings and Pravachans of Pujya Gurudev Shri Kanji Swami.</p>
                    <p>This digital repository allows seekers to search through extensive collections of spiritual wisdom, making the timeless teachings easily accessible to all.</p>
                </div>
            </div>
        );
    }
    
    if (currentPage === 'contact') {
        return (
            <div className="text-center py-12">
                <h1 className="text-4xl font-bold text-slate-800 mb-4">Contact & Feedback</h1>
                <div className="max-w-lg mx-auto text-slate-600 space-y-4">
                    <p>We value your feedback and suggestions for improving Aagam-Khoj.</p>
                    <p>Please reach out to us through our community channels or submit your feedback to help us serve you better.</p>
                    <div className="pt-4">
                        <p className="text-slate-500 text-sm">More contact options coming soon...</p>
                    </div>
                </div>
            </div>
        );
    }
    
    // For 'home' and 'aagam-khoj' pages
    return (
        <div className="text-center py-6 mb-4">
            <div className="inline-block">
                <div className="bg-slate-100 h-32 md:h-40 flex items-center justify-center mb-4 overflow-hidden">
                    <img 
                        src="/images/banner.jpg" 
                        alt="Swa-Lakshya Banner" 
                        className="h-full object-contain" 
                        onError={(e) => { e.target.onerror = null; e.target.src='https://placehold.co/1200x160/f1f5f9/475569?text=Jain+Catalogue+Search' }} 
                    />
                </div>
                <div className="h-32 md:h-40 flex flex-col items-center justify-center">
                    <h1 className="text-4xl font-bold text-slate-800 font-display">Aagam-Khoj (आगम-खोज)</h1>
                    <p className="text-base text-slate-500 mt-1 font-sans">Get answers from Pravachans of Pujya Gurudev Shri Kanji Swami!</p>
                </div>
            </div>
        </div>
    );
};

const SearchBar = ({ query, setQuery, onSearch }) => (
    <div className="relative">
        <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && onSearch()} placeholder="Enter your search query..." className="w-full p-3 pl-4 text-lg bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 text-slate-900 font-sans" />
    </div>
);

const MetadataFilters = ({ metadata, activeFilters, onAddFilter, onRemoveFilter }) => {
    const [selectedKey, setSelectedKey] = useState("");
    const [selectedValue, setSelectedValue] = useState("");
    const [availableValues, setAvailableValues] = useState([]);
    const dropdownFilterKeys = Object.keys(metadata);
    useEffect(() => {
        if (selectedKey && metadata[selectedKey]) {
            setAvailableValues(metadata[selectedKey]);
            setSelectedValue("");
        } else { setAvailableValues([]); }
    }, [selectedKey, metadata]);
    const handleAddClick = () => {
        if (selectedKey && selectedValue) {
            onAddFilter({ key: selectedKey, value: selectedValue });
            setSelectedKey(""); setSelectedValue("");
        }
    };
    return (
        <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">Filter by Category</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <select value={selectedKey} onChange={(e) => setSelectedKey(e.target.value)} className="p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 w-full text-base focus:ring-1 focus:ring-sky-500 font-sans"><option value="">Select Category...</option>{dropdownFilterKeys.map(key => <option key={key} value={key}>{key}</option>)}</select>
                <select value={selectedValue} onChange={(e) => setSelectedValue(e.target.value)} disabled={!selectedKey} className="p-2 bg-slate-50 border border-slate-300 rounded-md text-slate-800 w-full text-base disabled:opacity-50 disabled:cursor-not-allowed focus:ring-1 focus:ring-sky-500 font-sans"><option value="">Select Value...</option>{availableValues.map(val => <option key={val} value={val}>{val}</option>)}</select>
                <button onClick={handleAddClick} disabled={!selectedKey || !selectedValue} className="p-2 bg-sky-600 text-white font-semibold rounded-md hover:bg-sky-700 transition duration-200 disabled:bg-slate-300 disabled:cursor-not-allowed text-base font-sans">Add Filter</button>
            </div>
            {activeFilters.length > 0 && (<div className="flex flex-wrap gap-1.5 items-center pt-2"><span className="font-semibold text-slate-500 text-sm">Active:</span>{activeFilters.map((filter, index) => (<div key={index} className="bg-sky-100 text-sky-800 px-2 py-0.5 rounded-full flex items-center gap-2 text-sm font-medium"><span>{filter.key}: <strong>{filter.value}</strong></span><button onClick={() => onRemoveFilter(index)} className="text-sky-600 hover:text-sky-800 font-bold">&times;</button></div>))}</div>)}
        </div>
    );
};

const SearchOptions = ({ language, setLanguage, proximity, setProximity, searchType, setSearchType }) => {
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
                            <input type="radio" name="language" value={lang} checked={language === lang} onChange={(e) => setLanguage(e.target.value)} className="form-radio h-4 w-4 text-sky-600 focus:ring-sky-500" />
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
                        <span className="text-base font-medium flex items-center">Better Relevance <span className="text-sm text-slate-500">(slower)</span><BetaBadge /></span>
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
                        <span className="text-base font-medium">Better Speed <span className="text-sm text-slate-500">(slightly less relevant)</span></span>
                    </label>
                </div>
             </div>
        </div>
    );
};

const ResultCard = ({ result, onFindSimilar, onExpand, isFirst }) => {
    const getHighlightedHTML = () => {
        const content = result.content_snippet || result.text_content_hindi || '';
        // CORRECTED: The highlight class is now consistently `bg-sky-200` for all results to ensure visibility.
        return { __html: content.replace(/<em>/g, `<mark class="bg-sky-200 text-slate-800 px-1 rounded">`).replace(/<\/em>/g, '</mark>') };
    };

    const cardClasses = isFirst
        ? "bg-white p-4 rounded-lg border-2 border-sky-500 shadow-md"
        : "bg-white p-3 rounded-md border border-slate-200 transition-shadow hover:shadow-sm";

    return (
        <div className={cardClasses}>
            <div className="border-b border-slate-200 pb-2 mb-2 text-sm text-slate-500 flex flex-wrap gap-x-3 gap-y-1 items-center">
                {result.metadata?.Granth && <span className="font-bold text-slate-700">{result.metadata.Granth}</span>}
                {result.metadata?.Series && <span>{result.metadata.Series}</span>}
                <span className="text-slate-600">{result.filename}</span>
                <span>Page: {result.page_number}</span>
                {result.file_url && (
                    <a 
                        href={`${result.file_url}#page=${result.page_number}`}
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 font-medium flex items-center"
                    >
                        <PdfIcon />View PDF
                    </a>
                )}
                {result.bookmarks && <span className="truncate max-w-xs">Details: {result.bookmarks}</span>}
                <div className="ml-auto flex items-center gap-3 text-sm">
                    <button onClick={() => onExpand(result.document_id)} className="text-sky-600 hover:text-sky-800 font-medium flex items-center"><ExpandIcon />Expand</button>
                    <button onClick={() => onFindSimilar(result)} className="text-sky-600 hover:text-sky-800 font-medium flex items-center"><SimilarIcon />More Like This</button>
                </div>
            </div>
            <div className={`${isFirst ? 'text-lg' : 'text-base'} text-slate-700 leading-relaxed font-sans`}><p className="whitespace-pre-wrap" dangerouslySetInnerHTML={getHighlightedHTML()} /></div>
        </div>
    );
};

const Pagination = ({ currentPage, totalPages, onPageChange }) => {
    if (totalPages <= 1) return null;

    // This function builds the smart page list (e.g., [1, 2, '...', 22, 23, 24, '...', 49, 50])
    const getPaginationRange = () => {
        // If there are 7 or fewer pages, show all of them without any ellipses.
        if (totalPages <= 7) {
            return Array.from({ length: totalPages }, (_, i) => i + 1);
        }

        // Use a Set to automatically handle duplicate page numbers
        const pages = new Set();

        // Always show the first 2 pages
        pages.add(1);
        pages.add(2);

        // Add pages around the current page
        if (currentPage > 1) pages.add(currentPage - 1);
        pages.add(currentPage);
        if (currentPage < totalPages) pages.add(currentPage + 1);

        // Always show the last 2 pages
        pages.add(totalPages - 1);
        pages.add(totalPages);

        // Convert set to a sorted array and insert ellipses where there are gaps
        const result = [];
        let lastPage = 0;
        const sortedPages = Array.from(pages).sort((a, b) => a - b);

        for (const page of sortedPages) {
            if (page > lastPage + 1) {
                result.push('...');
            }
            result.push(page);
            lastPage = page;
        }

        return result;
    };

    const pageRange = getPaginationRange();

    return (
        <nav className="flex justify-center items-center gap-1 mt-4">
            {/* Previous Page Button */}
            <button onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1} className="px-2 py-1 text-sm bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed">
                &laquo;
            </button>

            {/* Page Number Buttons and Ellipses */}
            {pageRange.map((page, index) => {
                if (typeof page === 'string') {
                    // Render an ellipsis
                    return <span key={`ellipsis-${index}`} className="px-2.5 py-1 text-sm text-slate-500 flex items-center">...</span>;
                }
                // Render a page number button
                return (
                    <button
                        key={page}
                        onClick={() => onPageChange(page)}
                        className={`px-2.5 py-1 text-sm rounded-md border ${currentPage === page ? 'bg-sky-600 text-white border-sky-600 font-bold' : 'bg-white border-slate-300 hover:bg-slate-50'}`}
                    >
                        {page}
                    </button>
                );
            })}

            {/* Next Page Button */}
            <button onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === totalPages} className="px-2 py-1 text-sm bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed">
                &raquo;
            </button>
        </nav>
    );
};

const Tabs = ({ activeTab, setActiveTab, searchData, similarDocumentsData, onClearSimilar }) => {
    const keywordCount = searchData?.total_results || 0;
    const vectorCount = searchData?.total_vector_results || 0;
    const similarCount = similarDocumentsData?.total_results || 0;
    const hasSuggestions = searchData?.suggestions && searchData.suggestions.length > 0;
    const tabStyle = "px-3 py-2 font-semibold text-base rounded-t-md cursor-pointer transition-colors duration-200 flex items-center gap-2 border-b-2";
    const activeTabStyle = "bg-white text-sky-600 border-sky-500";
    const inactiveTabStyle = "bg-transparent text-slate-500 hover:text-slate-700 border-transparent";
    return (
        <div className="flex border-b border-slate-200">
            {searchData?.results?.length > 0 && <button onClick={() => setActiveTab('keyword')} className={`${tabStyle} ${activeTab === 'keyword' ? activeTabStyle : inactiveTabStyle}`}>Keyword Results <span className="text-sm font-normal bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{keywordCount}</span></button>}
            {!hasSuggestions && <button onClick={() => setActiveTab('vector')} className={`${tabStyle} ${activeTab === 'vector' ? activeTabStyle : inactiveTabStyle}`}>Semantic Results <span className="text-sm font-normal bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{vectorCount}</span></button>}
            {similarDocumentsData && <button onClick={() => setActiveTab('similar')} className={`${tabStyle} ${activeTab === 'similar' ? activeTabStyle : inactiveTabStyle}`}>More Like This <span className="text-sm font-normal bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{similarCount}</span><span onClick={(e) => { e.stopPropagation(); onClearSimilar(); }} className="text-red-400 hover:text-red-600 font-bold text-lg ml-1">&times;</span></button>}
        </div>
    );
};

const SuggestionsCard = ({ suggestions, originalQuery, onSuggestionClick }) => {
    if (!suggestions || suggestions.length === 0) return null;
    
    return (
        <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg mb-4">
            <div className="text-base text-yellow-800">
                <p className="mb-3">
                    No results found for "<span className="font-bold text-red-700">{originalQuery}</span>".
                </p>
                <p>
                    Did you mean: 
                    <span className="inline-flex flex-wrap items-center gap-2 ml-2">
                        {suggestions.map((suggestion, index) => (
                            <button
                                key={index}
                                onClick={() => onSuggestionClick(suggestion)}
                                className="text-blue-600 hover:text-blue-800 hover:bg-blue-50 font-bold cursor-pointer 
                                         underline decoration-2 underline-offset-2 
                                         px-2 py-1 rounded transition-colors duration-200
                                         border border-transparent hover:border-blue-300"
                            >
                                {suggestion}
                            </button>
                        ))}
                    </span>
                    ?
                </p>
            </div>
        </div>
    );
};

const SimilarSourceInfoCard = ({ sourceDoc }) => {
    if (!sourceDoc) return null;
    const getHighlightedHTML = () => {
        const content = sourceDoc.content_snippet || sourceDoc.text_content_hindi || '';
        return { __html: content.replace(/<em>/g, '<mark class="bg-sky-100 text-sky-900 px-1 rounded">').replace(/<\/em>/g, '</mark>') };
    };
    return (
        <div className="bg-sky-50 border border-sky-200 p-3 rounded-lg mb-3 text-sky-800">
            <h3 className="font-semibold text-sm mb-1.5">Showing results similar to:</h3>
            <div className="text-sm mb-2"><span className="font-medium">{sourceDoc.original_filename}</span><span className="ml-3">Page: {sourceDoc.page_number}</span></div>
            <blockquote className="border-l-4 border-sky-300 pl-2 text-base italic text-slate-600 font-sans"><p className="whitespace-pre-wrap" dangerouslySetInnerHTML={getHighlightedHTML()} /></blockquote>
        </div>
    );
};

const ResultsList = ({ results, totalResults, pageSize, currentPage, onPageChange, resultType, onFindSimilar, onExpand, searchType }) => {
    const totalPages = Math.ceil(totalResults / pageSize);
    return (
        <div className="bg-white p-3 md:p-4 rounded-b-md">
            {searchType === 'speed' && resultType === 'vector' && (
                <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg mb-4">
                    <p className="text-sm text-blue-800">
                        For more accurate relevance, select the "Better Relevance" option under "Filters" and try again (note that this is in beta).
                    </p>
                </div>
            )}
            <div className="text-sm text-slate-500 mb-3">Showing {results.length} of {totalResults} results.</div>
            <div className="space-y-3">
                {results.map((result, index) => (
                    <ResultCard
                        key={`${resultType}-${result.document_id}`}
                        result={result}
                        onFindSimilar={onFindSimilar}
                        onExpand={onExpand}
                        isFirst={currentPage === 1 && index === 0}
                    />
                ))}
            </div>
            <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />
        </div>
    );
};

const ExpandModal = ({ data, onClose, isLoading }) => {
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = 'unset'; };
    }, []);
    const Paragraph = ({ para, isCurrent }) => {
        if (!para) return <div className="p-3 rounded-md bg-slate-50 border border-dashed border-slate-300 text-center text-sm text-slate-400">Context not available.</div>;
        return <div className={`p-3 rounded-md ${isCurrent ? "bg-sky-100 border border-sky-300 ring-2 ring-sky-200" : "bg-slate-50 border border-slate-200"}`}><p className="text-slate-800 leading-relaxed text-base font-sans whitespace-pre-wrap">{para.content_snippet}</p></div>;
    };
    return (
        <div className="fixed inset-0 bg-black bg-opacity-60 z-50 flex justify-center items-center p-4" onClick={onClose}>
            <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="p-3 border-b border-slate-200 flex justify-between items-center"><h2 className="text-lg font-bold text-slate-800 font-display">Expanded Context</h2><button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-2xl font-bold">&times;</button></div>
                <div className="p-3 md:p-4 overflow-y-auto">
                    {isLoading ? <div className="text-center py-10"><div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500"></div><p className="mt-3 text-base text-slate-500">Loading Context...</p></div> : <div className="space-y-2"><Paragraph para={data?.previous} /><Paragraph para={data?.current} isCurrent={true} /><Paragraph para={data?.next} /></div>}
                </div>
            </div>
        </div>
    );
};

// --- MAIN APP COMPONENT ---
export default function App() {
    const [currentPage, setCurrentPage] = useState('home');
    const [query, setQuery] = useState('');
    const [activeFilters, setActiveFilters] = useState([]);
    const [language, setLanguage] = useState('hindi');
    const [proximity, setProximity] = useState(20);
    const [searchType, setSearchType] = useState('speed');
    const [showFilters, setShowFilters] = useState(false);
    const [metadata, setMetadata] = useState({});
    const [searchData, setSearchData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [activeTab, setActiveTab] = useState('keyword');
    const [keywordPage, setKeywordPage] = useState(1);
    const [vectorPage, setVectorPage] = useState(1);
    const [similarDocsPage, setSimilarDocsPage] = useState(1);
    const [similarDocumentsData, setSimilarDocumentsData] = useState(null);
    const [sourceDocForSimilarity, setSourceDocForSimilarity] = useState(null);
    const [modalData, setModalData] = useState(null);
    const [isContextLoading, setIsContextLoading] = useState(false);
    const PAGE_SIZE = 20;

    useEffect(() => { api.getMetadata().then(data => setMetadata(data)); }, []);
    const addFilter = (filter) => { if (!activeFilters.some(f => f.key === filter.key && f.value === filter.value)) { setActiveFilters([...activeFilters, filter]); } };
    const removeFilter = (index) => { setActiveFilters(activeFilters.filter((_, i) => i !== index)); };

    const handleSearch = useCallback(async (page = 1) => {
        if (!query.trim()) { alert("Please enter a search query."); return; }
        setIsLoading(true); setKeywordPage(page); setVectorPage(1); setSimilarDocumentsData(null); setSourceDocForSimilarity(null);
        const requestPayload = { query, allow_typos: false, categories: activeFilters.reduce((acc, f) => ({ ...acc, [f.key]: [...(acc[f.key] || []), f.value] }), {}), language: language === 'both' ? null : language, proximity_distance: proximity, page_number: page, page_size: PAGE_SIZE, enable_reranking: searchType === 'relevance' };
        const data = await api.search(requestPayload);
        setSearchData(data);
        if (data.results && data.results.length > 0) { setActiveTab('keyword'); } else { setActiveTab('vector'); }
        setIsLoading(false);
    }, [query, activeFilters, language, proximity, searchType]);

    const handleFindSimilar = async (sourceDoc) => {
        setIsLoading(true); setSourceDocForSimilarity(sourceDoc); setSimilarDocsPage(1);
        const data = await api.getSimilarDocuments(sourceDoc.document_id);
        setSimilarDocumentsData(data); setActiveTab('similar'); setIsLoading(false);
    };

    const handleExpand = async (chunkId) => {
        setIsContextLoading(true); setModalData({ previous: null, current: null, next: null });
        const data = await api.getParagraphContext(chunkId);
        setModalData(data); setIsContextLoading(false);
    };

    const handleCloseModal = () => setModalData(null);

    const handleClearSimilar = () => {
        setSimilarDocumentsData(null); setSourceDocForSimilarity(null);
        if (searchData?.results?.length > 0) { setActiveTab('keyword'); } else { setActiveTab('vector'); }
    };

    const handleSuggestionClick = (suggestion) => {
        setQuery(suggestion);
        // Trigger a new search with the suggestion
        const newQuery = suggestion;
        setIsLoading(true); setKeywordPage(1); setVectorPage(1); setSimilarDocumentsData(null); setSourceDocForSimilarity(null);
        const requestPayload = { query: newQuery, allow_typos: false, categories: activeFilters.reduce((acc, f) => ({ ...acc, [f.key]: [...(acc[f.key] || []), f.value] }), {}), language: language === 'both' ? null : language, proximity_distance: proximity, page_number: 1, page_size: PAGE_SIZE, enable_reranking: searchType === 'relevance' };
        api.search(requestPayload).then(data => {
            setSearchData(data);
            if (data.results && data.results.length > 0) { setActiveTab('keyword'); } else { setActiveTab('vector'); }
            setIsLoading(false);
        });
    };

    const handlePageChange = (page) => {
        switch (activeTab) {
            case 'keyword': handleSearch(page); break;
            case 'vector': setVectorPage(page); break;
            case 'similar': setSimilarDocsPage(page); break;
            default: break;
        }
    };

    const getPaginatedResults = (results, page) => {
        if (!results) return [];
        return results.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
    };

    const paginatedVectorResults = getPaginatedResults(searchData?.vector_results, vectorPage);
    const paginatedSimilarResults = getPaginatedResults(similarDocumentsData?.results, similarDocsPage);

    const showSearchInterface = currentPage === 'home' || currentPage === 'aagam-khoj';

    return (
        <div className="bg-slate-50 text-slate-900 min-h-screen font-sans">
            {modalData && <ExpandModal data={modalData} onClose={handleCloseModal} isLoading={isContextLoading} />}
            <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} />
            <div className="container mx-auto p-4 md:p-5">
                <div className="max-w-[1200px] mx-auto">
                    <Header currentPage={currentPage} />
                </div>
                {showSearchInterface && (
                    <main className="max-w-[1200px] mx-auto">
                    <div className="bg-white p-3 md:p-4 rounded-lg shadow-sm border border-slate-200 mb-4">
                        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-center">
                            <div className="sm:col-span-3"><SearchBar query={query} setQuery={setQuery} onSearch={() => handleSearch(1)} /></div>
                            <button onClick={() => handleSearch(1)} disabled={isLoading} className="bg-sky-600 text-white font-bold py-3 px-4 rounded-md text-base hover:bg-sky-700 transition duration-300 disabled:bg-slate-300 flex items-center justify-center w-full">{isLoading ? <Spinner /> : 'Search'}</button>
                        </div>
                        <div className="mt-3"><button onClick={() => setShowFilters(!showFilters)} className="flex items-center text-sky-700 font-semibold hover:text-sky-800 text-sm">{showFilters ? <ChevronUpIcon /> : <ChevronDownIcon />}{showFilters ? 'Hide Filters' : 'Show Filters'}<span className="ml-2 bg-slate-200 text-slate-600 text-sm font-bold px-1.5 py-0.5 rounded-full">{activeFilters.length}</span></button></div>
                        {showFilters && <div className="mt-3 space-y-3"><MetadataFilters metadata={metadata} activeFilters={activeFilters} onAddFilter={addFilter} onRemoveFilter={removeFilter} /><SearchOptions language={language} setLanguage={setLanguage} proximity={proximity} setProximity={setProximity} searchType={searchType} setSearchType={setSearchType} /></div>}
                    </div>
                    {isLoading && <div className="text-center py-8"><div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500"></div><p className="mt-3 text-base text-slate-500">Searching...</p></div>}
                    {!isLoading && (searchData || similarDocumentsData) && (
                        <div className="mt-4">
                            <SuggestionsCard suggestions={searchData?.suggestions} originalQuery={query} onSuggestionClick={handleSuggestionClick} />
                            <Tabs activeTab={activeTab} setActiveTab={setActiveTab} searchData={searchData} similarDocumentsData={similarDocumentsData} onClearSimilar={handleClearSimilar} />
                            {activeTab === 'keyword' && searchData?.results.length > 0 && <ResultsList results={searchData.results} totalResults={searchData.total_results} pageSize={PAGE_SIZE} currentPage={keywordPage} onPageChange={handlePageChange} resultType="keyword" onFindSimilar={handleFindSimilar} onExpand={handleExpand} searchType={searchType} />}
                            {activeTab === 'vector' && (searchData?.vector_results.length > 0 ? <ResultsList results={paginatedVectorResults} totalResults={searchData.total_vector_results} pageSize={PAGE_SIZE} currentPage={vectorPage} onPageChange={handlePageChange} resultType="vector" onFindSimilar={handleFindSimilar} onExpand={handleExpand} searchType={searchType} /> : searchData && <div className="text-center py-8 text-base text-slate-500 bg-white rounded-b-md border-t-0">No results found. Try a different query.</div>)}
                            {activeTab === 'similar' && <div className="bg-white p-3 md:p-4 rounded-b-md"><SimilarSourceInfoCard sourceDoc={sourceDocForSimilarity} />{similarDocumentsData?.results.length > 0 ? <ResultsList results={paginatedSimilarResults} totalResults={similarDocumentsData.total_results} pageSize={PAGE_SIZE} currentPage={similarDocsPage} onPageChange={handlePageChange} resultType="similar" onFindSimilar={handleFindSimilar} onExpand={handleExpand} searchType={searchType} /> : <div className="text-center py-8 text-base text-slate-500">No similar documents found.</div>}</div>}
                        </div>
                    )}
                    {!isLoading && !searchData && <div className="text-center py-8 text-base text-slate-500 bg-white rounded-lg border border-slate-200">Enter a query and click Search to see results.</div>}
                </main>
                )}
            </div>
        </div>
    );
}
