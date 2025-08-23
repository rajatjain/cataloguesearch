import React from 'react';
import { SimilarIcon, ExpandIcon, PdfIcon } from './SharedComponents';

// --- SEARCH RESULTS COMPONENTS ---
export const ResultCard = ({ result, onFindSimilar, onExpand, isFirst }) => {
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

                <div className="ml-auto flex items-center gap-3 text-sm">
                    <button onClick={() => onExpand(result.document_id)} className="text-sky-600 hover:text-sky-800 font-medium flex items-center">
                        <ExpandIcon />Expand
                    </button>
                    <button onClick={() => onFindSimilar(result)} className="text-sky-600 hover:text-sky-800 font-medium flex items-center">
                        <SimilarIcon />More Like This
                    </button>
                </div>
            </div>
            <div className={`${isFirst ? 'text-lg' : 'text-base'} text-slate-700 leading-relaxed font-sans`}>
                <p className="whitespace-pre-wrap" dangerouslySetInnerHTML={getHighlightedHTML()} />
            </div>
        </div>
    );
};

export const Pagination = ({ currentPage, totalPages, onPageChange }) => {
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
            <button 
                onClick={() => onPageChange(currentPage - 1)} 
                disabled={currentPage === 1} 
                className="px-2 py-1 text-sm bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
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
                        className={`px-2.5 py-1 text-sm rounded-md border ${
                            currentPage === page 
                                ? 'bg-sky-600 text-white border-sky-600 font-bold' 
                                : 'bg-white border-slate-300 hover:bg-slate-50'
                        }`}
                    >
                        {page}
                    </button>
                );
            })}

            {/* Next Page Button */}
            <button 
                onClick={() => onPageChange(currentPage + 1)} 
                disabled={currentPage === totalPages} 
                className="px-2 py-1 text-sm bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
                &raquo;
            </button>
        </nav>
    );
};

export const Tabs = ({ activeTab, setActiveTab, searchData, similarDocumentsData, onClearSimilar }) => {
    const keywordCount = searchData?.total_results || 0;
    const vectorCount = searchData?.total_vector_results || 0;
    const similarCount = similarDocumentsData?.total_results || 0;
    const hasSuggestions = searchData?.suggestions && searchData.suggestions.length > 0;
    const tabStyle = "px-3 py-2 font-semibold text-base rounded-t-md cursor-pointer transition-colors duration-200 flex items-center gap-2 border-b-2";
    const activeTabStyle = "bg-white text-sky-600 border-sky-500";
    const inactiveTabStyle = "bg-transparent text-slate-500 hover:text-slate-700 border-transparent";
    
    return (
        <div className="flex border-b border-slate-200">
            {searchData?.results?.length > 0 && (
                <button 
                    onClick={() => setActiveTab('keyword')} 
                    className={`${tabStyle} ${activeTab === 'keyword' ? activeTabStyle : inactiveTabStyle}`}
                >
                    Keyword Results 
                    <span className="text-sm font-normal bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{keywordCount}</span>
                </button>
            )}
            {!hasSuggestions && vectorCount > 0 && (
                <button 
                    onClick={() => setActiveTab('vector')} 
                    className={`${tabStyle} ${activeTab === 'vector' ? activeTabStyle : inactiveTabStyle}`}
                >
                    Semantic Results 
                    <span className="text-sm font-normal bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{vectorCount}</span>
                </button>
            )}
            {similarDocumentsData && (
                <button 
                    onClick={() => setActiveTab('similar')} 
                    className={`${tabStyle} ${activeTab === 'similar' ? activeTabStyle : inactiveTabStyle}`}
                >
                    More Like This 
                    <span className="text-sm font-normal bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">{similarCount}</span>
                    <span 
                        onClick={(e) => { e.stopPropagation(); onClearSimilar(); }} 
                        className="text-red-400 hover:text-red-600 font-bold text-lg ml-1"
                    >
                        &times;
                    </span>
                </button>
            )}
        </div>
    );
};

export const SuggestionsCard = ({ suggestions, originalQuery, onSuggestionClick }) => {
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

export const SimilarSourceInfoCard = ({ sourceDoc }) => {
    if (!sourceDoc) return null;
    
    const getHighlightedHTML = () => {
        const content = sourceDoc.content_snippet || sourceDoc.text_content_hindi || '';
        return { __html: content.replace(/<em>/g, '<mark class="bg-sky-100 text-sky-900 px-1 rounded">').replace(/<\/em>/g, '</mark>') };
    };
    
    return (
        <div className="bg-sky-50 border border-sky-200 p-3 rounded-lg mb-3 text-sky-800">
            <h3 className="font-semibold text-sm mb-1.5">Showing results similar to:</h3>
            <div className="text-sm mb-2">
                <span className="font-medium">{sourceDoc.original_filename}</span>
                <span className="ml-3">Page: {sourceDoc.page_number}</span>
            </div>
            <blockquote className="border-l-4 border-sky-300 pl-2 text-base italic text-slate-600 font-sans">
                <p className="whitespace-pre-wrap" dangerouslySetInnerHTML={getHighlightedHTML()} />
            </blockquote>
        </div>
    );
};

export const ResultsList = ({ results, totalResults, pageSize, currentPage, onPageChange, resultType, onFindSimilar, onExpand, searchType }) => {
    const totalPages = Math.ceil(totalResults / pageSize);
    
    return (
        <div className="bg-white p-3 md:p-4 rounded-b-md">
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
