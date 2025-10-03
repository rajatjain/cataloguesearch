import React, { useState, useEffect, useRef } from 'react';
import { getScriptureData, getPDFWithCache, pdfCache } from '../../utils/scriptureCache';
import VerseCard from './VerseCard';
import VerseDetails from './VerseDetails';
import ProseCard from './ProseCard';
import ProseDetails from './ProseDetails';

const ScriptureEval = ({ selectedFile, onFileSelect, basePaths, baseDirectoryHandles }) => {
    // Scripture data state
    const [scriptureData, setScriptureData] = useState(null);
    const [allContent, setAllContent] = useState([]); // Merged verses + prose sorted by seq_num
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    // Navigation state
    const [currentItem, setCurrentItem] = useState(0); // Changed from currentVerse
    const [showAllItems, setShowAllItems] = useState(false); // Changed from showAllVerses
    const [availableTypes, setAvailableTypes] = useState([]);
    
    // PDF viewer state
    const [pdfUrl, setPdfUrl] = useState(null);
    const [pdfError, setPdfError] = useState(null);
    const [pdfDoc, setPdfDoc] = useState(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);
    
    // Cache stats for debugging
    const [cacheStats, setCacheStats] = useState(null);

    // Load cache stats on mount
    useEffect(() => {
        const loadCacheStats = async () => {
            try {
                const stats = await pdfCache.getCacheStats();
                setCacheStats(stats);
            } catch (err) {
                console.warn('Could not load cache stats:', err);
            }
        };
        loadCacheStats();
    }, [scriptureData]); // Update when scripture loads

    // PDF.js dynamic loading
    useEffect(() => {
        const loadPdfJs = async () => {
            if (!window.pdfjsLib) {
                try {
                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
                    document.head.appendChild(script);
                    
                    script.onload = () => {
                        console.log('PDF.js loaded successfully');
                        window.pdfjsLib.GlobalWorkerOptions.workerSrc = 
                            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
                    };
                } catch (error) {
                    console.error('Failed to load PDF.js:', error);
                    setPdfError('Failed to load PDF.js library. PDF functionality will not be available.');
                }
            } else {
                window.pdfjsLib.GlobalWorkerOptions.workerSrc = 
                    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            }
        };
        
        loadPdfJs();
    }, []);

    // Handle file browser selection
    useEffect(() => {
        const handleFileSelection = async () => {
            console.log('ScriptureEval received selectedFile:', selectedFile);
            if (selectedFile && selectedFile.relativePath && selectedFile.relativePath.endsWith('.md')) {
                console.log('Loading scripture with path:', selectedFile.relativePath);
                await loadScripture(selectedFile.relativePath);
            }
        };
        
        handleFileSelection();
    }, [selectedFile]);

    const loadScripture = async (relativePath) => {
        setIsLoading(true);
        setError(null);
        setScriptureData(null);
        setPdfUrl(null);
        setPdfError(null);
        
        try {
            // Load scripture data (always fresh from API)
            const data = await getScriptureData(relativePath);
            setScriptureData(data);

            // Merge verses and prose_sections, sorted by seq_num
            const verses = (data.verses || []).map(v => ({ ...v, contentType: 'verse' }));
            const proseSections = (data.prose_sections || []).map(p => ({ ...p, contentType: 'prose' }));
            const merged = [...verses, ...proseSections].sort((a, b) => a.seq_num - b.seq_num);
            setAllContent(merged);

            setCurrentItem(0);
            setShowAllItems(false);

            // Extract available verse types
            const types = [...new Set(data.verses.map(v => v.type))];
            setAvailableTypes(types);

            // Try to load PDF from file_url
            if (data.metadata && data.metadata.file_url) {
                setPdfUrl(data.metadata.file_url);
            }

        } catch (err) {
            setError(err.message);
            console.error('Error loading scripture:', err);
        } finally {
            setIsLoading(false);
        }
    };

    // Navigate across all content (verses + prose)
    const navigateContent = (direction) => {
        if (allContent.length === 0) return;

        const newIndex = direction === 'next'
            ? Math.min(currentItem + 1, allContent.length - 1)
            : Math.max(currentItem - 1, 0);
        setCurrentItem(newIndex);

        // Auto-navigate to the page in PDF if available
        const item = allContent[newIndex];
        if (item && item.page_num && pdfDoc) {
            navigateToPDFPage(item.page_num);
        }
    };

    const jumpToVerse = (type, typeNum) => {
        if (allContent.length === 0) return;

        const itemIndex = allContent.findIndex(
            item => item.contentType === 'verse' && item.type === type && item.type_start_num <= typeNum && item.type_end_num >= typeNum
        );
        if (itemIndex !== -1) {
            setCurrentItem(itemIndex);

            // Auto-navigate to the page in PDF if available
            const item = allContent[itemIndex];
            if (item && item.page_num && pdfDoc) {
                navigateToPDFPage(item.page_num);
            }
        }
    };

    const getDisplayContent = () => {
        if (allContent.length === 0) return [];

        if (showAllItems) {
            return allContent;
        }

        const total = allContent.length;

        if (total <= 10) return allContent;

        // Show first 5 and last 5
        return [
            ...allContent.slice(0, 5),
            { isExpander: true },
            ...allContent.slice(-5)
        ];
    };

    // Unified ContentCard that handles both verses and prose
    const ContentCard = ({ item, index, isActive }) => {
        if (item.isExpander) {
            return (
                <div className="text-center py-4">
                    <button
                        onClick={() => setShowAllItems(true)}
                        className="text-sky-600 hover:text-sky-800 font-medium text-sm flex items-center mx-auto"
                    >
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                        Show All {allContent.length} Items
                    </button>
                </div>
            );
        }

        if (item.contentType === 'verse') {
            return (
                <VerseCard
                    verse={item}
                    index={index}
                    isActive={isActive}
                    onClick={setCurrentItem}
                    pdfDoc={pdfDoc}
                    navigateToPDFPage={navigateToPDFPage}
                />
            );
        }

        if (item.contentType === 'prose') {
            return (
                <ProseCard
                    prose={item}
                    index={index}
                    isActive={isActive}
                    onClick={setCurrentItem}
                    pdfDoc={pdfDoc}
                    navigateToPDFPage={navigateToPDFPage}
                />
            );
        }

        return null;
    };

    // PDF loading and rendering functions
    const loadPDF = async (pdfUrl) => {
        if (!window.pdfjsLib) {
            setPdfError('PDF.js library not loaded. Please refresh the page.');
            return;
        }

        try {
            console.log('Loading PDF from:', pdfUrl);
            
            // Get PDF with caching
            const pdfBlob = await getPDFWithCache(pdfUrl);
            const blobUrl = URL.createObjectURL(pdfBlob);
            
            const pdf = await window.pdfjsLib.getDocument(blobUrl).promise;
            setPdfDoc(pdf);
            setTotalPages(pdf.numPages);
            setCurrentPage(1);
            
            // Render first page
            await renderPDFPage(pdf, 1);
        } catch (err) {
            console.error('Error loading PDF:', err);
            setPdfError(`Error loading PDF: ${err.message}`);
        }
    };

    const renderPDFPage = async (pdf, pageNum) => {
        try {
            const page = await pdf.getPage(pageNum);
            const scale = 1.5;
            const viewport = page.getViewport({ scale });
            
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            
            await page.render({ canvasContext: context, viewport: viewport }).promise;
            
            const dataUrl = canvas.toDataURL('image/png');
            setPdfPreviewUrl(dataUrl);
        } catch (err) {
            console.error('Error rendering PDF page:', err);
            setPdfError(`Error rendering PDF page: ${err.message}`);
        }
    };

    const handlePDFPageNavigation = async (direction) => {
        if (!pdfDoc) return;
        
        let newPage = currentPage;
        if (direction === 'prev' && currentPage > 1) {
            newPage = currentPage - 1;
        } else if (direction === 'next' && currentPage < totalPages) {
            newPage = currentPage + 1;
        }
        
        if (newPage !== currentPage) {
            setCurrentPage(newPage);
            await renderPDFPage(pdfDoc, newPage);
        }
    };

    const navigateToPDFPage = async (pageNum) => {
        if (!pdfDoc || pageNum < 1 || pageNum > totalPages) return;
        
        if (pageNum !== currentPage) {
            setCurrentPage(pageNum);
            await renderPDFPage(pdfDoc, pageNum);
        }
    };

    // Load PDF when pdfUrl is available
    useEffect(() => {
        if (pdfUrl && window.pdfjsLib) {
            loadPDF(pdfUrl);
        }
    }, [pdfUrl]);

    const JumpToVerseInput = () => {
        const [selectedType, setSelectedType] = useState('');
        const [inputNum, setInputNum] = useState('');

        const handleJump = () => {
            if (selectedType && inputNum) {
                const num = parseInt(inputNum);
                if (!isNaN(num)) {
                    jumpToVerse(selectedType, num);
                    setInputNum('');
                }
            }
        };

        const handleKeyPress = (e) => {
            if (e.key === 'Enter') {
                handleJump();
            }
        };

        return (
            <div className="flex items-center space-x-2">
                <select
                    value={selectedType}
                    onChange={(e) => setSelectedType(e.target.value)}
                    className="text-sm border border-slate-300 rounded px-2 py-1"
                >
                    <option value="">Type</option>
                    {availableTypes.map(type => (
                        <option key={type} value={type}>{type}</option>
                    ))}
                </select>
                
                <input
                    type="number"
                    value={inputNum}
                    onChange={(e) => setInputNum(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Number"
                    className="text-sm border border-slate-300 rounded px-2 py-1 w-20"
                    min="1"
                />
                
                <button
                    onClick={handleJump}
                    disabled={!selectedType || !inputNum}
                    className="text-sm bg-sky-600 text-white px-3 py-1 rounded disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-sky-700"
                >
                    Go
                </button>
            </div>
        );
    };


    return (
        <div className="bg-white rounded-lg shadow-sm border border-slate-200">
            <div className="p-6 border-b border-slate-200">
                <h2 className="text-xl font-semibold text-slate-800 mb-2">Scripture Evaluation</h2>
                <p className="text-slate-600 text-sm">
                    Evaluate markdown scripture files with side-by-side PDF viewing and verse navigation.
                </p>
                
                {/* PDF Cache Stats for debugging */}
                {cacheStats && (
                    <div className="mt-3 text-xs text-slate-500">
                        PDF Cache: {cacheStats.totalEntries} files, {cacheStats.totalSizeMB}MB / {cacheStats.maxSizeMB}MB 
                        ({cacheStats.utilizationPercent}% used)
                    </div>
                )}
            </div>

            {/* File Selection Info */}
            {selectedFile && selectedFile.relativePath && (
                <div className="p-4 bg-blue-50 border-b border-blue-200">
                    <div className="flex items-center">
                        <svg className="w-4 h-4 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <span className="text-blue-800 font-medium text-sm">Selected File:</span>
                        <span className="text-blue-700 text-sm ml-2">{selectedFile.relativePath}</span>
                    </div>
                    {!selectedFile.relativePath.endsWith('.md') && (
                        <div className="text-amber-600 text-xs mt-1">
                            ⚠️ Please select a .md (markdown) file for scripture evaluation
                        </div>
                    )}
                </div>
            )}

            {/* Loading State */}
            {isLoading && (
                <div className="flex items-center justify-center py-12">
                    <div className="flex items-center text-slate-600">
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-slate-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Loading scripture...
                    </div>
                </div>
            )}

            {/* Error State */}
            {error && (
                <div className="p-6">
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <div className="flex items-start">
                            <svg className="w-5 h-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <div>
                                <p className="text-red-800 font-medium text-sm">Error loading scripture</p>
                                <p className="text-red-700 text-sm mt-1">{error}</p>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Main Content */}
            {scriptureData && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
                    {/* Left Panel - PDF Viewer */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-medium text-slate-800">Original PDF</h3>
                            {scriptureData.metadata && (
                                <div className="text-sm text-slate-600">
                                    {scriptureData.metadata.author} • {scriptureData.metadata.language}
                                </div>
                            )}
                        </div>
                        
                        {/* PDF Page Navigation */}
                        {pdfDoc && (
                            <div className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-lg">
                                <button
                                    onClick={() => handlePDFPageNavigation('prev')}
                                    disabled={currentPage === 1}
                                    className="flex items-center px-3 py-1 bg-slate-200 text-slate-700 rounded disabled:opacity-50 hover:bg-slate-300"
                                >
                                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                    </svg>
                                    Previous
                                </button>
                                
                                <span className="text-sm text-slate-600 font-medium">
                                    Page {currentPage} of {totalPages}
                                </span>
                                
                                <button
                                    onClick={() => handlePDFPageNavigation('next')}
                                    disabled={currentPage === totalPages}
                                    className="flex items-center px-3 py-1 bg-slate-200 text-slate-700 rounded disabled:opacity-50 hover:bg-slate-300"
                                >
                                    Next
                                    <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                </button>
                            </div>
                        )}

                        {/* PDF Viewer */}
                        <div className="border border-slate-200 rounded-lg bg-slate-50 h-[600px] flex items-center justify-center overflow-hidden">
                            {pdfError ? (
                                <div className="text-center text-red-500">
                                    <svg className="w-12 h-12 mx-auto mb-2 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <p className="text-sm font-medium">PDF Error</p>
                                    <p className="text-xs mt-1">{pdfError}</p>
                                </div>
                            ) : pdfPreviewUrl ? (
                                <img 
                                    src={pdfPreviewUrl} 
                                    alt={`PDF page ${currentPage}`}
                                    className="max-w-full max-h-full object-contain"
                                />
                            ) : pdfUrl ? (
                                <div className="text-center text-slate-500">
                                    <svg className="animate-spin w-8 h-8 mx-auto mb-2 text-slate-400" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    <p className="text-sm">Loading PDF...</p>
                                </div>
                            ) : (
                                <div className="text-center text-slate-500">
                                    <svg className="w-12 h-12 mx-auto mb-2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                                    </svg>
                                    <p className="text-sm">PDF will be loaded from file_url</p>
                                    {scriptureData.metadata?.file_url && (
                                        <p className="text-xs mt-1 font-mono break-all">{scriptureData.metadata.file_url}</p>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right Panel - Content Display */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-medium text-slate-800">
                                {scriptureData.name}
                            </h3>
                            <div className="text-sm text-slate-600">
                                {scriptureData.verses.length} verses • {scriptureData.prose_sections ? scriptureData.prose_sections.length : 0} prose
                            </div>
                        </div>

                        {/* Navigation Controls */}
                        <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                            <div className="flex items-center space-x-2">
                                <button
                                    onClick={() => navigateContent('prev')}
                                    disabled={currentItem === 0}
                                    className="p-2 border border-slate-300 rounded hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                    </svg>
                                </button>

                                <span className="text-sm text-slate-600">
                                    {currentItem + 1} of {allContent.length}
                                </span>

                                <button
                                    onClick={() => navigateContent('next')}
                                    disabled={currentItem === allContent.length - 1}
                                    className="p-2 border border-slate-300 rounded hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                </button>
                            </div>

                            <JumpToVerseInput />
                        </div>

                        {/* Content List */}
                        <div className="space-y-3 max-h-96 overflow-y-auto">
                            {getDisplayContent().map((item, index) => (
                                <ContentCard
                                    key={item.isExpander ? 'expander' : item.seq_num}
                                    item={item}
                                    index={item.isExpander ? null : allContent.findIndex(c => c.seq_num === item.seq_num)}
                                    isActive={!item.isExpander && index === currentItem}
                                />
                            ))}
                        </div>

                        {/* Content Details */}
                        {allContent[currentItem] && allContent[currentItem].contentType === 'verse' && (
                            <VerseDetails verse={allContent[currentItem]} />
                        )}

                        {allContent[currentItem] && allContent[currentItem].contentType === 'prose' && (
                            <ProseDetails prose={allContent[currentItem]} />
                        )}
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!isLoading && !error && !scriptureData && (
                <div className="text-center py-12">
                    <svg className="mx-auto h-12 w-12 text-slate-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <h3 className="text-lg font-medium text-slate-800 mb-2">No Scripture Selected</h3>
                    <p className="text-slate-600 mb-4">
                        Use the "Browse Files" button to select a markdown (.md) scripture file for evaluation.
                    </p>
                    <p className="text-sm text-slate-500">
                        PDF files will be cached locally for faster subsequent access. Scripture data is always fetched fresh.
                    </p>
                </div>
            )}
        </div>
    );
};

export default ScriptureEval;