import React, { useState, useEffect, useCallback } from 'react';

// Import components
import { Navigation, Header } from './components/Navigation';
import { SearchBar, MetadataFilters, SearchOptions } from './components/SearchInterface';
import { ResultsList, SuggestionsCard, Tabs, SimilarSourceInfoCard } from './components/SearchResults';
import { ExpandModal, WelcomeModal } from './components/Modals';
import { FeedbackForm } from './components/Feedback';
import { Spinner, ChevronUpIcon, ChevronDownIcon } from './components/SharedComponents';

// Import API service
import { api } from './services/api';

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
    const [showWelcomePopup, setShowWelcomePopup] = useState(false);
    const PAGE_SIZE = 20;

    useEffect(() => { 
        api.getMetadata().then(data => setMetadata(data)); 
    }, []);

    useEffect(() => {
        try {
            const hasVisited = localStorage.getItem('aagamKhojHasVisited');
            if (!hasVisited) {
                setShowWelcomePopup(true);
                localStorage.setItem('aagamKhojHasVisited', 'true');
            }
        } catch (error) {
            console.warn('localStorage not available:', error);
        }
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
        
        const requestPayload = { 
            query, 
            allow_typos: false, 
            categories: activeFilters.reduce((acc, f) => ({ ...acc, [f.key]: [...(acc[f.key] || []), f.value] }), {}), 
            language: language, 
            proximity_distance: proximity, 
            page_number: page, 
            page_size: PAGE_SIZE, 
            enable_reranking: searchType === 'relevance' 
        };
        
        const data = await api.search(requestPayload);
        setSearchData(data);
        
        if (data.results && data.results.length > 0) { 
            setActiveTab('keyword'); 
        } else { 
            setActiveTab('vector'); 
        }
        setIsLoading(false);
    }, [query, activeFilters, language, proximity, searchType]);

    const handleFindSimilar = async (sourceDoc) => {
        setIsLoading(true); 
        setSourceDocForSimilarity(sourceDoc); 
        setSimilarDocsPage(1);
        const data = await api.getSimilarDocuments(sourceDoc.document_id);
        setSimilarDocumentsData(data); 
        setActiveTab('similar'); 
        setIsLoading(false);
    };

    const handleExpand = async (chunkId) => {
        setIsContextLoading(true); 
        setModalData({ previous: null, current: null, next: null });
        const data = await api.getParagraphContext(chunkId);
        setModalData(data); 
        setIsContextLoading(false);
    };

    const handleCloseModal = () => setModalData(null);

    const handleWelcomeClose = () => {
        setShowWelcomePopup(false);
    };

    const handleWelcomeGoToUsageGuide = () => {
        setShowWelcomePopup(false);
        setCurrentPage('about');
    };

    const handleClearSimilar = () => {
        setSimilarDocumentsData(null); 
        setSourceDocForSimilarity(null);
        if (searchData?.results?.length > 0) { 
            setActiveTab('keyword'); 
        } else { 
            setActiveTab('vector'); 
        }
    };

    const handleSuggestionClick = (suggestion) => {
        setQuery(suggestion);
        // Trigger a new search with the suggestion
        const newQuery = suggestion;
        setIsLoading(true); 
        setKeywordPage(1); 
        setVectorPage(1); 
        setSimilarDocumentsData(null); 
        setSourceDocForSimilarity(null);
        
        const requestPayload = { 
            query: newQuery, 
            allow_typos: false, 
            categories: activeFilters.reduce((acc, f) => ({ ...acc, [f.key]: [...(acc[f.key] || []), f.value] }), {}), 
            language: language, 
            proximity_distance: proximity, 
            page_number: 1, 
            page_size: PAGE_SIZE, 
            enable_reranking: searchType === 'relevance' 
        };
        
        api.search(requestPayload).then(data => {
            setSearchData(data);
            if (data.results && data.results.length > 0) { 
                setActiveTab('keyword'); 
            } else { 
                setActiveTab('vector'); 
            }
            setIsLoading(false);
        });
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

    const showSearchInterface = currentPage === 'home' || currentPage === 'aagam-khoj';

    return (
        <div className="bg-slate-50 text-slate-900 min-h-screen font-sans">
            {modalData && (
                <ExpandModal 
                    data={modalData} 
                    onClose={handleCloseModal} 
                    isLoading={isContextLoading} 
                />
            )}
            
            {showWelcomePopup && (
                <WelcomeModal 
                    onClose={handleWelcomeClose} 
                    onGoToUsageGuide={handleWelcomeGoToUsageGuide} 
                />
            )}
            
            <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} />
            
            <div className="container mx-auto p-4 md:p-5">
                <div className="max-w-[1200px] mx-auto">
                    <Header currentPage={currentPage} />

                    {showSearchInterface && (
                        <main>
                            <div className="bg-white p-3 md:p-4 rounded-lg shadow-sm border border-slate-200 mb-4">
                                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-center">
                                    <div className="sm:col-span-3">
                                        <SearchBar 
                                            query={query} 
                                            setQuery={setQuery} 
                                            onSearch={() => handleSearch(1)} 
                                        />
                                    </div>
                                    <button 
                                        onClick={() => handleSearch(1)} 
                                        disabled={isLoading} 
                                        className="bg-sky-600 text-white font-bold py-3 px-4 rounded-md text-base hover:bg-sky-700 transition duration-300 disabled:bg-slate-300 flex items-center justify-center w-full"
                                    >
                                        {isLoading ? <Spinner /> : 'Search'}
                                    </button>
                                </div>
                                <div className="mt-3">
                                    <button 
                                        onClick={() => setShowFilters(!showFilters)} 
                                        className="flex items-center text-sky-700 font-semibold hover:text-sky-800 text-sm"
                                    >
                                        {showFilters ? <ChevronUpIcon /> : <ChevronDownIcon />}
                                        {showFilters ? 'Hide Filters' : 'Show Filters'}
                                        <span className="ml-2 bg-slate-200 text-slate-600 text-sm font-bold px-1.5 py-0.5 rounded-full">
                                            {activeFilters.length}
                                        </span>
                                    </button>
                                </div>
                                {showFilters && (
                                    <div className="mt-3 space-y-3">
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
                            
                            {isLoading && (
                                <div className="text-center py-8">
                                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500"></div>
                                    <p className="mt-3 text-base text-slate-500">Searching...</p>
                                </div>
                            )}
                            
                            {!isLoading && (searchData || similarDocumentsData) && (
                                <div className="mt-4">
                                    <SuggestionsCard 
                                        suggestions={searchData?.suggestions} 
                                        originalQuery={query} 
                                        onSuggestionClick={handleSuggestionClick} 
                                    />
                                    <Tabs 
                                        activeTab={activeTab} 
                                        setActiveTab={setActiveTab} 
                                        searchData={searchData} 
                                        similarDocumentsData={similarDocumentsData} 
                                        onClearSimilar={handleClearSimilar} 
                                    />
                                    {activeTab === 'keyword' && searchData?.results.length > 0 && (
                                        <ResultsList 
                                            results={searchData.results} 
                                            totalResults={searchData.total_results} 
                                            pageSize={PAGE_SIZE} 
                                            currentPage={keywordPage} 
                                            onPageChange={handlePageChange} 
                                            resultType="keyword" 
                                            onFindSimilar={handleFindSimilar} 
                                            onExpand={handleExpand} 
                                            searchType={searchType} 
                                        />
                                    )}
                                    {activeTab === 'vector' && (
                                        searchData?.vector_results.length > 0 ? (
                                            <ResultsList 
                                                results={paginatedVectorResults} 
                                                totalResults={searchData.total_vector_results} 
                                                pageSize={PAGE_SIZE} 
                                                currentPage={vectorPage} 
                                                onPageChange={handlePageChange} 
                                                resultType="vector" 
                                                onFindSimilar={handleFindSimilar} 
                                                onExpand={handleExpand} 
                                                searchType={searchType} 
                                            />
                                        ) : searchData && (
                                            <div className="text-center py-8 text-base text-slate-500 bg-white rounded-b-md border-t-0">
                                                No results found. Try a different query.
                                            </div>
                                        )
                                    )}
                                    {activeTab === 'similar' && (
                                        <div className="bg-white p-3 md:p-4 rounded-b-md">
                                            <SimilarSourceInfoCard sourceDoc={sourceDocForSimilarity} />
                                            {similarDocumentsData?.results.length > 0 ? (
                                                <ResultsList 
                                                    results={paginatedSimilarResults} 
                                                    totalResults={similarDocumentsData.total_results} 
                                                    pageSize={PAGE_SIZE} 
                                                    currentPage={similarDocsPage} 
                                                    onPageChange={handlePageChange} 
                                                    resultType="similar" 
                                                    onFindSimilar={handleFindSimilar} 
                                                    onExpand={handleExpand} 
                                                    searchType={searchType} 
                                                />
                                            ) : (
                                                <div className="text-center py-8 text-base text-slate-500">
                                                    No similar documents found.
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}
                            
                            {!isLoading && !searchData && (
                                <div className="text-center py-8 text-base text-slate-500 bg-white rounded-lg border border-slate-200">
                                    Enter a query and click Search to see results.
                                </div>
                            )}
                        </main>
                    )}

                    {currentPage === 'feedback' && (
                        <main>
                            <FeedbackForm onReturnToAagamKhoj={() => setCurrentPage('home')} />
                        </main>
                    )}
                </div>
            </div>
            
            {/* Mobile Navigation Buttons - Only visible on mobile */}
            {currentPage !== 'feedback' && (
                <button
                    onClick={() => setCurrentPage('feedback')}
                    className="md:hidden fixed bottom-6 right-6 bg-sky-600 text-white p-3 rounded-full shadow-lg hover:bg-sky-700 transition-colors duration-200 z-50"
                    aria-label="Feedback"
                >
                    {/* Email icon for feedback */}
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </button>
            )}
            
            {currentPage !== 'home' && currentPage !== 'aagam-khoj' && (
                <button
                    onClick={() => setCurrentPage('home')}
                    className="md:hidden fixed bottom-6 left-6 bg-slate-600 text-white p-3 rounded-full shadow-lg hover:bg-slate-700 transition-colors duration-200 z-50"
                    aria-label="Home"
                >
                    {/* Home icon */}
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                    </svg>
                </button>
            )}
        </div>
    );
}