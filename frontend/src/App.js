import React, { useState, useEffect, useCallback } from 'react';

// --- API SERVICE ---
const API_BASE_URL = 'http://localhost:8000';

const api = {
    getMetadata: async () => {
        console.log("API: Fetching metadata for categories...");
        try {
            const response = await fetch(`${API_BASE_URL}/metadata`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log("API: Category metadata received.", data);
            return data;
        } catch (error) {
            console.error("API Error: Could not fetch category metadata", error);
            return {};
        }
    },
    search: async (requestPayload) => {
        console.log("API: Sending search request...", requestPayload);
        try {
            const response = await fetch(`${API_BASE_URL}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestPayload),
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log("API: Search results received.", data);
            return data;
        } catch (error) {
            console.error("API Error: Could not perform search", error);
            return { total: 0, results: [] };
        }
    }
};

// --- HELPER & ICON COMPONENTS ---

const Spinner = () => (
    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
);

const FilterIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-.293.707L13 10.414V15a1 1 0 01-.293.707l-2 2A1 1 0 019 17v-6.586L3.293 6.707A1 1 0 013 6V3z" clipRule="evenodd" />
    </svg>
);


// --- UI COMPONENTS ---

const Banner = () => (
    <div className="bg-sky-100 h-40 flex items-center justify-center rounded-lg mb-4">
        <img
            src="/images/banner.jpg"
            alt="Jain Catalogue Search Banner"
            className="w-full h-full object-contain rounded-lg"
            onError={(e) => { e.target.onerror = null; e.target.src='https://placehold.co/1200x200/E0F2FE/334155?text=Jain+Catalogue+Search' }}
        />
    </div>
);

const Description = () => (
    <div className="text-center mb-8 px-4 text-gray-600 leading-relaxed">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">Jain Catalogue Search</h1>
        <p>This interface allows a Mumukshu to search through a vast collection of sermons</p>
        <p>delivered by Pujya Gurudev Shri Kanji Swami.</p>
    </div>
);

const SearchBar = ({ query, setQuery }) => (
    <div className="relative">
        <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your search query..."
            className="w-full p-4 pl-5 text-lg bg-white border-2 border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900"
        />
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
        <div className="space-y-4">
            <h3 className="text-md font-semibold text-gray-700">Filter by Category</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <select
                    value={selectedKey}
                    onChange={(e) => setSelectedKey(e.target.value)}
                    className="p-3 bg-gray-50 border border-gray-300 rounded-md text-gray-900 w-full focus:ring-2 focus:ring-blue-500"
                >
                    <option value="">Select Category...</option>
                    {dropdownFilterKeys.map(key => <option key={key} value={key}>{key}</option>)}
                </select>
                <select
                    value={selectedValue}
                    onChange={(e) => setSelectedValue(e.target.value)}
                    disabled={!selectedKey}
                    className="p-3 bg-gray-50 border border-gray-300 rounded-md text-gray-900 w-full disabled:opacity-50 disabled:cursor-not-allowed focus:ring-2 focus:ring-blue-500"
                >
                    <option value="">Select Value...</option>
                    {availableValues.map(val => <option key={val} value={val}>{val}</option>)}
                </select>
                <button
                    onClick={handleAddClick}
                    disabled={!selectedKey || !selectedValue}
                    className="p-3 bg-blue-600 text-white font-bold rounded-md hover:bg-blue-700 transition duration-200 disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                    Add Filter
                </button>
            </div>
            {activeFilters.length > 0 && (
                <div className="flex flex-wrap gap-2 items-center pt-3">
                    <span className="font-semibold text-gray-600 text-sm">Active:</span>
                    {activeFilters.map((filter, index) => (
                        <div key={index} className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full flex items-center gap-2 text-sm font-medium">
                            <span>{filter.key}: <strong>{filter.value}</strong></span>
                            <button onClick={() => onRemoveFilter(index)} className="text-blue-600 hover:text-blue-800 font-bold">
                                &#x2715;
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

const SearchOptions = ({ language, setLanguage, proximity, setProximity, searchType, setSearchType }) => {
    const languageOptions = ['hindi', 'gujarati', 'both'];
    const proximityOptions = [
        { label: 'exact phrase', value: 0 },
        { label: 'near (10 words)', value: 10 },
        { label: 'medium (20 words)', value: 20 },
        { label: 'far (30 words)', value: 30 }
    ];
    const searchTypeOptions = [
        { label: 'Strict Search', value: 'strict' },
        { label: 'Allow Typos', value: 'fuzzy' }
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6 border-t border-gray-200">
            <div>
                <h3 className="text-md font-semibold mb-3 text-gray-700">Search Type</h3>
                <div className="flex gap-4">
                    {searchTypeOptions.map(opt => (
                        <label key={opt.value} className="flex items-center gap-2 text-gray-800">
                            <input type="radio" name="searchType" value={opt.value} checked={searchType === opt.value} onChange={() => setSearchType(opt.value)} className="form-radio h-4 w-4 text-blue-600 focus:ring-blue-500" />
                            {opt.label}
                        </label>
                    ))}
                </div>
            </div>
            <div>
                <h3 className="text-md font-semibold mb-3 text-gray-700">Language</h3>
                <div className="flex gap-4">
                    {languageOptions.map(lang => (
                        <label key={lang} className="flex items-center gap-2 text-gray-800 capitalize">
                            <input type="radio" name="language" value={lang} checked={language === lang} onChange={(e) => setLanguage(e.target.value)} className="form-radio h-4 w-4 text-blue-600 focus:ring-blue-500" />
                            {lang}
                        </label>
                    ))}
                </div>
            </div>
            <div>
                <h3 className="text-md font-semibold mb-3 text-gray-700">Proximity</h3>
                <div className="flex flex-wrap gap-4">
                    {proximityOptions.map(opt => (
                        <label key={opt.value} className="flex items-center gap-2 text-gray-800">
                            <input type="radio" name="proximity" value={opt.value} checked={proximity === opt.value} onChange={() => setProximity(opt.value)} className="form-radio h-4 w-4 text-blue-600 focus:ring-blue-500" />
                            {opt.label}
                        </label>
                    ))}
                </div>
            </div>
        </div>
    );
};

/**
 * Renders a single search result card.
 * It now receives HTML with <em> tags in `content_snippet` and styles them.
 */
const ResultCard = ({ result }) => {
    /**
     * Replaces <em> tags from OpenSearch with styled <mark> tags
     * and returns an object suitable for dangerouslySetInnerHTML.
     */
    const getHighlightedHTML = () => {
        if (!result.content_snippet) {
            return { __html: '' };
        }
        const styledSnippet = result.content_snippet
            .replace(/<em>/g, '<mark class="bg-yellow-200 text-black px-1 rounded font-medium">')
            .replace(/<\/em>/g, '</mark>');
        return { __html: styledSnippet };
    };

    return (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 transition-shadow hover:shadow-md">
            <div className="border-b border-gray-200 pb-3 mb-4 text-sm text-gray-500 flex flex-wrap gap-x-4 gap-y-2">
                <span className="font-semibold text-gray-800">📄 {result.original_filename}</span>
                <span>Page: {result.page_number}</span>
                {result.bookmarks && result.bookmarks.length > 0 && (
                    <span>🔖 Bookmarks: {result.bookmarks}</span>
                )}
            </div>
            <div className="space-y-3 text-gray-700">
                {/* Use dangerouslySetInnerHTML to render the HTML from the API */}
                <p dangerouslySetInnerHTML={getHighlightedHTML()} />
            </div>
        </div>
    );
};

const Pagination = ({ currentPage, totalPages, onPageChange }) => {
    if (totalPages <= 1) return null;
    const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

    return (
        <nav className="flex justify-center items-center gap-2 mt-8">
            <button onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1} className="px-3 py-1 bg-white border border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed">
                &laquo;
            </button>
            {pages.map(page => (
                <button key={page} onClick={() => onPageChange(page)} className={`px-3 py-1 rounded-md border ${currentPage === page ? 'bg-blue-600 text-white border-blue-600 font-bold' : 'bg-white border-gray-300 hover:bg-gray-100'}`}>
                    {page}
                </button>
            ))}
            <button onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === totalPages} className="px-3 py-1 bg-white border border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed">
                &raquo;
            </button>
        </nav>
    );
};

/**
 * Renders the list of search results.
 */
const Results = ({ searchData, isLoading, currentPage, onPageChange }) => {
    if (isLoading) {
        return (
             <div className="text-center py-10">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                <p className="mt-4 text-lg text-gray-600">Searching...</p>
            </div>
        );
    }

    if (!searchData) {
        return <div className="text-center py-10 text-gray-500 bg-gray-100 rounded-lg border border-gray-200">Enter a query and click Search to see results.</div>;
    }

    if (searchData.results.length === 0) {
        return <div className="text-center py-10 text-gray-500 bg-white rounded-lg border border-gray-200">No results found for your query.</div>;
    }

    const totalPages = Math.ceil(searchData.total_results / searchData.page_size);

    return (
        <div className="mt-10">
            <div className="text-gray-600 mb-4">
                Showing {searchData.results.length} of {searchData.total_results} results.
            </div>
            <div className="space-y-6">
                {searchData.results.map((result, index) => (
                    <ResultCard
                        key={`${result.original_filename}-${index}`}
                        result={result}
                    />
                ))}
            </div>
            <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />
        </div>
    );
};


// --- MAIN APP COMPONENT ---

export default function App() {
    const [query, setQuery] = useState('');
    const [activeFilters, setActiveFilters] = useState([]);
    const [language, setLanguage] = useState('hindi');
    const [proximity, setProximity] = useState(20);
    const [searchType, setSearchType] = useState('strict');

    const [showFilters, setShowFilters] = useState(false);
    const [metadata, setMetadata] = useState({});
    const [searchData, setSearchData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    const [currentPage, setCurrentPage] = useState(1);

    useEffect(() => {
        api.getMetadata().then(data => setMetadata(data));
    }, []);

    const addFilter = (filter) => {
        if (!activeFilters.some(f => f.key === filter.key && f.value === filter.value)) {
            setActiveFilters([...activeFilters, filter]);
        }
    };

    const removeFilter = (index) => {
        setActiveFilters(activeFilters.filter((_, i) => i !== index));
    };

    const handleSearch = useCallback(async (page = 1) => {
        if (!query.trim()) {
            // Using a simple browser alert for now. Consider a modal for a better UX.
            alert("Please enter a search query.");
            return;
        }
        setIsLoading(true);
        setCurrentPage(page);

        const languageToSend = language === 'both' ? null : language;

        const requestPayload = {
            query: query,
            search_type: searchType,
            categories: activeFilters.reduce((acc, filter) => {
                if (!acc[filter.key]) acc[filter.key] = [];
                acc[filter.key].push(filter.value);
                return acc;
            }, {}),
            language: languageToSend,
            proximity_distance: proximity,
            page_number: page,
            page_size: 20
        };

        const data = await api.search(requestPayload);
        setSearchData(data);
        setIsLoading(false);
    }, [query, activeFilters, language, proximity, searchType]);

    const handlePageChange = (page) => {
        if (searchData && page > 0 && page <= Math.ceil(searchData.total_results / searchData.page_size)) {
            handleSearch(page);
        }
    };

    return (
        <div className="bg-gray-50 text-gray-900 min-h-screen font-sans">
            <div className="container mx-auto p-4 md:p-8">
                <header>
                    <Banner />
                    <Description />
                </header>

                <main>
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 mb-8">
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-start">
                            <div className="md:col-span-3">
                                <SearchBar query={query} setQuery={setQuery} />
                            </div>
                            <button
                                onClick={() => handleSearch(1)}
                                disabled={isLoading}
                                className="bg-green-600 text-white font-bold py-4 px-6 rounded-lg text-lg hover:bg-green-700 transition duration-300 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center w-full"
                            >
                                {isLoading ? <Spinner /> : 'Search'}
                            </button>
                        </div>

                        <div className="mt-4">
                            <button
                                onClick={() => setShowFilters(!showFilters)}
                                className="flex items-center text-blue-600 font-semibold hover:text-blue-800"
                            >
                                <FilterIcon />
                                {showFilters ? 'Hide Filters' : 'Show Filters'}
                                <span className="ml-2 bg-blue-100 text-blue-800 text-xs font-bold px-2 py-0.5 rounded-full">
                                    {activeFilters.length}
                                </span>
                            </button>
                        </div>

                        {showFilters && (
                            <div className="mt-6 space-y-6">
                                <MetadataFilters
                                    metadata={metadata}
                                    activeFilters={activeFilters}
                                    onAddFilter={addFilter}
                                    onRemoveFilter={removeFilter}
                                />
                                <SearchOptions
                                    language={language}
                                    setLanguage={setLanguage}
                                    proximity={proximity}
                                    setProximity={setProximity}
                                    searchType={searchType}
                                    setSearchType={setSearchType}
                                />
                            </div>
                        )}
                    </div>

                    <Results
                        searchData={searchData}
                        isLoading={isLoading}
                        currentPage={currentPage}
                        onPageChange={handlePageChange}
                    />
                </main>
            </div>
        </div>
    );
}