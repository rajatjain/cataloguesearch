import React, { useState, useEffect, useCallback } from 'react';

// --- MOCK API SERVICE ---
// In a real application, this would be in a separate file (e.g., services/api.js)
// and would use fetch() to make actual network requests.

const mockMetadata = {
    "provider": ["TIFR", "IISC", "NCBS", "InStem"],
    "iisc_department": ["Physics", "Biology", "Chemistry", "Mathematics"],
    "year": ["2021", "2022", "2023", "2024"]
};

const mockSearchResults = {
    total: 28,
    results: [
        {
            original_file_name: "document_xyz.pdf",
            page_no: 15,
            bookmarks: ["General", "Science"],
            snippets: [
                "This is the first snippet where the important **search** term appears in context.",
                "Another part of the page shows the **search** result with more details."
            ]
        },
        {
            original_file_name: "research_paper_alpha.pdf",
            page_no: 3,
            bookmarks: ["Physics"],
            snippets: [
                "The primary **search** was conducted over a period of six months."
            ]
        },
        {
            original_file_name: "catalogue_data_2023.docx",
            page_no: 88,
            bookmarks: [],
            snippets: [
                "For a successful **search**, one must define the parameters clearly.",
                "This **search** yielded many interesting results from the chemistry department."
            ]
        },
        {
            original_file_name: "hindi_literature_review.pdf",
            page_no: 42,
            bookmarks: ["Literature", "Hindi"],
            snippets: [
                "यह एक महत्वपूर्ण **खोज** है जो हमारे अध्ययन को आगे बढ़ाएगी।",
                "इस **खोज** के परिणाम बहुत उत्साहजनक थे।"
            ]
        }
    ]
};


const api = {
    getMetadata: () => {
        console.log("API: Fetching metadata...");
        return new Promise(resolve => {
            setTimeout(() => {
                console.log("API: Metadata received.", mockMetadata);
                resolve(mockMetadata);
            }, 500);
        });
    },
    search: (requestPayload) => {
        console.log("API: Sending search request...", requestPayload);
        return new Promise(resolve => {
            setTimeout(() => {
                console.log("API: Search results received.", mockSearchResults);
                resolve(mockSearchResults);
            }, 1000);
        });
    }
};

// --- HELPER & ICON COMPONENTS ---

/**
 * A simple spinner component to indicate loading states.
 */
const Spinner = () => (
    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
);

/**
 * Filter Icon SVG
 */
const FilterIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-.293.707L13 10.414V15a1 1 0 01-.293.707l-2 2A1 1 0 019 17v-6.586L3.293 6.707A1 1 0 013 6V3z" clipRule="evenodd" />
    </svg>
);


// --- UI COMPONENTS ---

/**
 * Module 1: Image Banner
 */
const Banner = () => (
    <div className="bg-sky-100 h-40 flex items-center justify-center rounded-lg mb-4">
        <img
            src="https://placehold.co/1200x160/e0f2fe/0c4a6e?text=Catalogue+Search"
            alt="Catalogue Search Banner"
            className="w-full h-full object-cover rounded-lg"
        />
    </div>
);

/**
 * Description Text
 */
const Description = () => (
    <div className="text-center mb-8 px-4 text-gray-600 leading-relaxed">
        <p>Welcome to the Catalogue Search utility, your gateway to exploring a vast archive of documents.</p>
        <p>Use the powerful search bar to find specific terms and apply filters to refine your results.</p>
    </div>
);


/**
 * Module 2: Search Box
 */
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

/**
 * Module 3: Metadata Filters
 */
const MetadataFilters = ({ metadata, activeFilters, onAddFilter, onRemoveFilter }) => {
    const [selectedKey, setSelectedKey] = useState("");
    const [selectedValue, setSelectedValue] = useState("");
    const [availableValues, setAvailableValues] = useState([]);

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
                    {Object.keys(metadata).map(key => <option key={key} value={key}>{key}</option>)}
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


/**
 * Modules 4 & 5: Language and Proximity Options
 */
const SearchOptions = ({ language, setLanguage, proximity, setProximity }) => {
    const proximityOptions = [
        { label: 'Near', value: 10 }, { label: 'Medium', value: 20 }, { label: 'Far', value: 30 },
    ];
    const languageOptions = ['hindi', 'gujarati'];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t border-gray-200">
            <div>
                <h3 className="text-md font-semibold mb-3 text-gray-700">Language</h3>
                <div className="flex gap-4">
                    <label className="flex items-center gap-2 text-gray-800">
                        <input type="radio" name="language" value="" checked={language === ""} onChange={() => setLanguage("")} className="form-radio h-4 w-4 text-blue-600 focus:ring-blue-500" />
                        Any
                    </label>
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
 * Module 7.1: Result Card
 */
const ResultCard = ({ result }) => {
    const highlightSnippet = (snippet) => {
        const highlighted = snippet.replace(/\*\*(.*?)\*\*/g, `<strong class="bg-yellow-300 text-black px-1 rounded-sm">$1</strong>`);
        return { __html: highlighted };
    };

    return (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 transition-shadow hover:shadow-md">
            <div className="border-b border-gray-200 pb-3 mb-4 text-sm text-gray-500 flex flex-wrap gap-x-4 gap-y-2">
                <span className="font-semibold text-gray-800">📄 {result.original_file_name}</span>
                <span>Page: {result.page_no}</span>
                {result.bookmarks && result.bookmarks.length > 0 && (
                    <span>🔖 Bookmarks: {result.bookmarks.join(', ')}</span>
                )}
            </div>
            <div className="space-y-3 text-gray-700">
                {result.snippets.map((snippet, index) => (
                    <p key={index} dangerouslySetInnerHTML={highlightSnippet(snippet)} />
                ))}
            </div>
        </div>
    );
};

/**
 * Module 7 (Pagination): Pagination Controls
 */
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
 * Module 7: Results Display
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

    const itemsPerPage = 4;
    const totalPages = Math.ceil(searchData.total / itemsPerPage);

    return (
        <div className="mt-10">
            <div className="text-gray-600 mb-4">
                Showing {searchData.results.length} of {searchData.total} results.
            </div>
            <div className="space-y-6">
                {searchData.results.map((result, index) => (
                    <ResultCard key={`${result.original_file_name}-${index}`} result={result} />
                ))}
            </div>
            <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />
        </div>
    );
};


// --- MAIN APP COMPONENT ---

export default function App() {
    // State for search inputs
    const [query, setQuery] = useState('');
    const [activeFilters, setActiveFilters] = useState([]);
    const [language, setLanguage] = useState('');
    const [proximity, setProximity] = useState(20);

    // State for UI
    const [showFilters, setShowFilters] = useState(false);

    // State for API data and loading status
    const [metadata, setMetadata] = useState({});
    const [searchData, setSearchData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    // State for pagination
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
            alert("Please enter a search query.");
            return;
        }

        setIsLoading(true);
        setSearchData(null);
        setCurrentPage(page);

        const requestPayload = {
            query: query,
            filters: activeFilters.reduce((acc, filter) => {
                if (!acc[filter.key]) acc[filter.key] = [];
                acc[filter.key].push(filter.value);
                return acc;
            }, {}),
            language: language || null,
            proximity: proximity,
            page: page,
            size: 4
        };

        const data = await api.search(requestPayload);
        setSearchData(data);
        setIsLoading(false);
    }, [query, activeFilters, language, proximity]);

    const handlePageChange = (page) => {
        handleSearch(page);
    };

    return (
        <div className="bg-gray-50 text-gray-900 min-h-screen font-sans">
            <div className="container mx-auto p-4 md:p-8">
                <header>
                    <Banner />
                    <Description />
                </header>

                <main>
                    {/* Search Controls Card */}
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 mb-8">
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-start">
                            <div className="md:col-span-3">
                                <SearchBar query={query} setQuery={setQuery} />
                            </div>
                            <button
                                onClick={() => handleSearch(1)}
                                disabled={isLoading}
                                className="bg-green-600 text-white font-bold py-4 px-6 rounded-lg text-lg hover:bg-green-700 transition duration-300 disabled:bg-gray-400 flex items-center justify-center w-full"
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

                        {/* Collapsible Filter Section */}
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
                                />
                            </div>
                        )}
                    </div>

                    {/* Results Section */}
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
