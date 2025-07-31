import React, { useState, useEffect, useCallback } from 'react';

// --- API SERVICE ---
const API_BASE_URL = 'http://localhost:8000';

const api = {
    getMetadata: async () => {
        console.log("API: Fetching metadata...");
        try {
            const response = await fetch(`${API_BASE_URL}/metadata`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error("API Error: Could not fetch metadata", error);
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
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            return { ...data, results: data.results || [], vector_results: data.vector_results || [] };
        } catch (error) {
            console.error("API Error: Could not perform search", error);
            return { total_results: 0, results: [], total_vector_results: 0, vector_results: [] };
        }
    },
    getSimilarDocuments: async (docId) => {
        console.log(`API: Fetching similar documents for doc_id: ${docId}`);
        try {
            const response = await fetch(`${API_BASE_URL}/similar-documents/${docId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            return { ...data, results: data.results || [] };
        } catch (error) {
            console.error("API Error: Could not fetch similar documents", error);
            return { total_results: 0, results: [] };
        }
    }
};

// --- HELPER & ICON COMPONENTS ---

const Spinner = () => <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>;

const FilterIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-.293.707L13 10.414V15a1 1 0 01-.293.707l-2 2A1 1 0 019 17v-6.586L3.293 6.707A1 1 0 013 6V3z" clipRule="evenodd" />
    </svg>
);

const SimilarIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1 inline-block" viewBox="0 0 20 20" fill="currentColor">
      <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
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

const SearchOptions = ({ language, setLanguage, proximity, setProximity, allowTypos, setAllowTypos }) => {
    const languageOptions = ['hindi', 'gujarati', 'both'];
    const proximityOptions = [
        { label: 'exact phrase', value: 0 },
        { label: 'near (10 words)', value: 10 },
        { label: 'medium (20 words)', value: 20 },
        { label: 'far (30 words)', value: 30 }
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6 border-t border-gray-200">
            <div>
                <label className="flex items-center gap-3 text-gray-800">
                    <input
                        type="checkbox"
                        checked={allowTypos}
                        onChange={(e) => {
                            const checked = e.target.checked;
                            setAllowTypos(checked);
                            if (checked && proximity === 0) {
                                setProximity(10);
                            }
                        }}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <span className="text-md font-semibold text-gray-700">Allow Typos</span>
                </label>
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
                        <label key={opt.value} className={`flex items-center gap-2 ${allowTypos && opt.value === 0 ? 'text-gray-400' : 'text-gray-800'}`}>
                            <input
                                type="radio"
                                name="proximity"
                                value={opt.value}
                                checked={proximity === opt.value}
                                onChange={() => setProximity(opt.value)}
                                disabled={allowTypos && opt.value === 0}
                                className="form-radio h-4 w-4 text-blue-600 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                            />
                            {opt.label}
                        </label>
                    ))}
                </div>
            </div>
        </div>
    );
};

const ResultCard = ({ result, onFindSimilar }) => {
    const getHighlightedHTML = () => {
        const content = result.content_snippet || result.text_content_hindi || '';
        const styledSnippet = content
            .replace(/<em>/g, '<mark class="bg-yellow-200 text-black px-1 rounded font-medium">')
            .replace(/<\/em>/g, '</mark>');
        return { __html: styledSnippet };
    };

    return (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 transition-shadow hover:shadow-md">
            <div className="border-b border-gray-200 pb-3 mb-4 text-sm text-gray-500 flex flex-wrap gap-x-4 gap-y-2 items-center">
                <span className="font-semibold text-gray-800">📄 {result.original_filename}</span>
                <span>Page: {result.page_number}</span>
                {result.bookmarks && result.bookmarks.length > 0 && (
                    <span>🔖 Bookmarks: {result.bookmarks}</span>
                )}
                <button
                    onClick={() => onFindSimilar(result)}
                    className="text-blue-600 hover:text-blue-800 font-semibold text-xs ml-auto flex items-center"
                >
                    <SimilarIcon />
                    More Like This
                </button>
            </div>
            <div className="space-y-3 text-gray-700">
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

const Tabs = ({ activeTab, setActiveTab, searchData, similarDocumentsData, onClearSimilar }) => {
    const keywordCount = searchData?.total_results || 0;
    const vectorCount = searchData?.total_vector_results || 0;
    const similarCount = similarDocumentsData?.total_results || 0;

    const tabStyle = "px-4 py-2 font-semibold text-lg rounded-t-lg cursor-pointer transition-colors duration-200 flex items-center gap-2";
    const activeTabStyle = "bg-white text-blue-600 border-b-2 border-blue-600";
    const inactiveTabStyle = "bg-gray-200 text-gray-600 hover:bg-gray-300";

    return (
        <div className="flex border-b border-gray-300">
            {/* Conditionally render Keyword Results tab */}
            {searchData?.results?.length > 0 && (
                 <button onClick={() => setActiveTab('keyword')} className={`${tabStyle} ${activeTab === 'keyword' ? activeTabStyle : inactiveTabStyle}`}>
                    Keyword Results <span className="text-sm font-normal bg-gray-300 px-2 py-1 rounded-full">{keywordCount}</span>
                </button>
            )}
            <button onClick={() => setActiveTab('vector')} className={`${tabStyle} ${activeTab === 'vector' ? activeTabStyle : inactiveTabStyle}`}>
                Semantic Results <span className="text-sm font-normal bg-gray-300 px-2 py-1 rounded-full">{vectorCount}</span>
            </button>
            {similarDocumentsData && (
                 <button onClick={() => setActiveTab('similar')} className={`${tabStyle} ${activeTab === 'similar' ? activeTabStyle : inactiveTabStyle}`}>
                    More Like This <span className="text-sm font-normal bg-gray-300 px-2 py-1 rounded-full">{similarCount}</span>
                    <span onClick={(e) => { e.stopPropagation(); onClearSimilar(); }} className="text-red-500 hover:text-red-700 font-bold text-lg">&times;</span>
                </button>
            )}
        </div>
    );
};

const SimilarSourceInfoCard = ({ sourceDoc }) => {
    if (!sourceDoc) return null;

    const getHighlightedHTML = () => {
        const content = sourceDoc.content_snippet || sourceDoc.text_content_hindi || '';
        const styledSnippet = content
            .replace(/<em>/g, '<mark class="bg-blue-100 text-blue-900 px-1 rounded font-medium">')
            .replace(/<\/em>/g, '</mark>');
        return { __html: styledSnippet };
    };

    return (
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg mb-6 text-blue-800">
            <h3 className="font-bold text-lg mb-2">Showing results similar to:</h3>
            <div className="text-md mb-3">
                <span className="font-semibold">📄 {sourceDoc.original_filename}</span>
                <span className="ml-4">Page: {sourceDoc.page_number}</span>
            </div>
            <blockquote className="border-l-4 border-blue-300 pl-4 italic text-gray-700">
                 <p dangerouslySetInnerHTML={getHighlightedHTML()} />
            </blockquote>
        </div>
    );
};

const ResultsList = ({ results, totalResults, pageSize, currentPage, onPageChange, resultType, onFindSimilar }) => {
    const totalPages = Math.ceil(totalResults / pageSize);

    return (
        <div className="bg-white p-6 rounded-b-lg">
            <div className="text-gray-600 mb-4">
                Showing {results.length} of {totalResults} results.
            </div>
            <div className="space-y-6">
                {results.map((result, index) => (
                    <ResultCard
                        key={`${resultType}-${result.document_id}-${index}`}
                        result={result}
                        onFindSimilar={onFindSimilar}
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
    const [allowTypos, setAllowTypos] = useState(false);

    const [showFilters, setShowFilters] = useState(false);
    const [metadata, setMetadata] = useState({});
    const [searchData, setSearchData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    // State for tabs and independent pagination
    const [activeTab, setActiveTab] = useState('keyword');
    const [keywordPage, setKeywordPage] = useState(1);
    const [vectorPage, setVectorPage] = useState(1);
    const [similarDocsPage, setSimilarDocsPage] = useState(1);

    // State for the new "More Like This" feature
    const [similarDocumentsData, setSimilarDocumentsData] = useState(null);
    const [sourceDocForSimilarity, setSourceDocForSimilarity] = useState(null);

    const PAGE_SIZE = 20;

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
            alert("Please enter a search query.");
            return;
        }
        setIsLoading(true);
        setKeywordPage(page);
        setVectorPage(1);
        setSimilarDocumentsData(null);
        setSourceDocForSimilarity(null);

        const languageToSend = language === 'both' ? null : language;

        const requestPayload = {
            query: query, allow_typos: allowTypos, categories: activeFilters.reduce((acc, filter) => {
                if (!acc[filter.key]) acc[filter.key] = [];
                acc[filter.key].push(filter.value);
                return acc;
            }, {}), language: languageToSend, proximity_distance: proximity, page_number: page, page_size: PAGE_SIZE
        };

        const data = await api.search(requestPayload);
        setSearchData(data);

        // If keyword results exist, show them by default. Otherwise, default to semantic.
        if (data.results && data.results.length > 0) {
            setActiveTab('keyword');
        } else {
            setActiveTab('vector');
        }

        setIsLoading(false);
    }, [query, activeFilters, language, proximity, allowTypos]);

    const handleFindSimilar = async (sourceDoc) => {
        setIsLoading(true);
        setSourceDocForSimilarity(sourceDoc);
        setSimilarDocsPage(1);
        const data = await api.getSimilarDocuments(sourceDoc.document_id);
        setSimilarDocumentsData(data);
        setActiveTab('similar');
        setIsLoading(false);
    };

    const handleClearSimilar = () => {
        setSimilarDocumentsData(null);
        setSourceDocForSimilarity(null);
        // Return to keyword tab if it exists, otherwise vector
        if (searchData?.results?.length > 0) {
            setActiveTab('keyword');
        } else {
            setActiveTab('vector');
        }
    };

    const handlePageChange = (page) => {
        switch (activeTab) {
            case 'keyword':
                handleSearch(page);
                break;
            case 'vector':
                setVectorPage(page);
                break;
            case 'similar':
                setSimilarDocsPage(page);
                break;
            default:
                break;
        }
    };

    const getPaginatedResults = (results, page) => {
        if (!results) return [];
        return results.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
    };

    const paginatedVectorResults = getPaginatedResults(searchData?.vector_results, vectorPage);
    const paginatedSimilarResults = getPaginatedResults(similarDocumentsData?.results, similarDocsPage);

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
                            <button onClick={() => handleSearch(1)} disabled={isLoading} className="bg-green-600 text-white font-bold py-4 px-6 rounded-lg text-lg hover:bg-green-700 transition duration-300 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center w-full">
                                {isLoading ? <Spinner /> : 'Search'}
                            </button>
                        </div>

                        <div className="mt-4">
                            <button onClick={() => setShowFilters(!showFilters)} className="flex items-center text-blue-600 font-semibold hover:text-blue-800">
                                <FilterIcon />
                                {showFilters ? 'Hide Filters' : 'Show Filters'}
                                <span className="ml-2 bg-blue-100 text-blue-800 text-xs font-bold px-2 py-0.5 rounded-full">{activeFilters.length}</span>
                            </button>
                        </div>

                        {showFilters && (
                            <div className="mt-6 space-y-6">
                                <MetadataFilters metadata={metadata} activeFilters={activeFilters} onAddFilter={addFilter} onRemoveFilter={removeFilter} />
                                <SearchOptions language={language} setLanguage={setLanguage} proximity={proximity} setProximity={setProximity} allowTypos={allowTypos} setAllowTypos={setAllowTypos} />
                            </div>
                        )}
                    </div>

                    {isLoading && (
                         <div className="text-center py-10">
                            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                            <p className="mt-4 text-lg text-gray-600">Searching...</p>
                        </div>
                    )}

                    {!isLoading && (searchData || similarDocumentsData) && (
                        <div>
                            <Tabs activeTab={activeTab} setActiveTab={setActiveTab} searchData={searchData} similarDocumentsData={similarDocumentsData} onClearSimilar={handleClearSimilar} />

                            {activeTab === 'keyword' && (
                                searchData?.results.length > 0 ? (
                                    <ResultsList results={searchData.results} totalResults={searchData.total_results} pageSize={PAGE_SIZE} currentPage={keywordPage} onPageChange={handlePageChange} resultType="keyword" onFindSimilar={handleFindSimilar} />
                                ) : null
                            )}

                             {activeTab === 'vector' && (
                                searchData?.vector_results.length > 0 ? (
                                    <ResultsList results={paginatedVectorResults} totalResults={searchData.total_vector_results} pageSize={PAGE_SIZE} currentPage={vectorPage} onPageChange={handlePageChange} resultType="vector" onFindSimilar={handleFindSimilar} />
                                ) : searchData && <div className="text-center py-10 text-gray-500 bg-white rounded-b-lg border-t-0">No results found. Try a different query.</div>
                            )}

                            {activeTab === 'similar' && (
                                <div className="bg-white p-6 rounded-b-lg">
                                    <SimilarSourceInfoCard sourceDoc={sourceDocForSimilarity} />
                                    {similarDocumentsData?.results.length > 0 ? (
                                        <ResultsList results={paginatedSimilarResults} totalResults={similarDocumentsData.total_results} pageSize={PAGE_SIZE} currentPage={similarDocsPage} onPageChange={handlePageChange} resultType="similar" onFindSimilar={handleFindSimilar} />
                                    ) : <div className="text-center py-10 text-gray-500">No similar documents found.</div>}
                                </div>
                            )}
                        </div>
                    )}

                    {!isLoading && !searchData && (
                        <div className="text-center py-10 text-gray-500 bg-gray-100 rounded-lg border border-gray-200">
                            Enter a query and click Search to see results.
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}
