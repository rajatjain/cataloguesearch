import React, { useState, useEffect, useRef } from 'react';
import { getScriptureData, getPDFWithCache, pdfCache } from '../../utils/scriptureCache';

const ScriptureEval = ({ selectedFile, onFileSelect, basePaths, baseDirectoryHandles }) => {
    // Scripture data state
    const [scriptureData, setScriptureData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    
    // Navigation state
    const [currentVerse, setCurrentVerse] = useState(0);
    const [showAllVerses, setShowAllVerses] = useState(false);
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
            setCurrentVerse(0);
            setShowAllVerses(false);
            
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

    const navigateVerse = (direction) => {
        if (!scriptureData) return;
        
        const newIndex = direction === 'next' 
            ? Math.min(currentVerse + 1, scriptureData.verses.length - 1)
            : Math.max(currentVerse - 1, 0);
        setCurrentVerse(newIndex);
        
        // Auto-navigate to the verse's page in PDF if available
        const verse = scriptureData.verses[newIndex];
        if (verse && verse.page_num && pdfDoc) {
            navigateToPDFPage(verse.page_num);
        }
    };

    const jumpToVerse = (type, typeNum) => {
        if (!scriptureData) return;
        
        const verseIndex = scriptureData.verses.findIndex(v => v.type === type && v.type_num === typeNum);
        if (verseIndex !== -1) {
            setCurrentVerse(verseIndex);
            
            // Auto-navigate to the verse's page in PDF if available
            const verse = scriptureData.verses[verseIndex];
            if (verse && verse.page_num && pdfDoc) {
                navigateToPDFPage(verse.page_num);
            }
        }
    };

    const getVersesByType = (type) => {
        if (!scriptureData) return [];
        return scriptureData.verses.filter(v => v.type === type);
    };

    const getDisplayVerses = () => {
        if (!scriptureData) return [];
        
        if (showAllVerses) {
            return scriptureData.verses;
        }
        
        const verses = scriptureData.verses;
        const total = verses.length;
        
        if (total <= 10) return verses;
        
        // Show first 5 and last 5
        return [
            ...verses.slice(0, 5),
            { isExpander: true },
            ...verses.slice(-5)
        ];
    };

    const VerseCard = ({ verse, index, isActive }) => {
        if (verse.isExpander) {
            return (
                <div className="text-center py-4">
                    <button
                        onClick={() => setShowAllVerses(true)}
                        className="text-sky-600 hover:text-sky-800 font-medium text-sm flex items-center mx-auto"
                    >
                        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                        Show All {scriptureData.verses.length} Verses
                    </button>
                </div>
            );
        }

        return (
            <div 
                className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                    isActive 
                        ? 'border-sky-500 bg-sky-50' 
                        : 'border-slate-200 hover:border-slate-300'
                }`}
                onClick={() => {
                    setCurrentVerse(index);
                    // Auto-navigate to the verse's page in PDF if available
                    if (verse.page_num && pdfDoc) {
                        navigateToPDFPage(verse.page_num);
                    }
                }}
            >
                <div className="flex items-center justify-between mb-2">
                    <div className="flex flex-col">
                        <span className="text-sm font-medium text-sky-600">
                            {verse.type} {verse.type_num}
                        </span>
                        {verse.adhikar && (
                            <span className="text-xs text-purple-600 font-medium">
                                {verse.adhikar}
                            </span>
                        )}
                    </div>
                    {verse.page_num && (
                        <span className="text-xs text-slate-500">
                            Page {verse.page_num}
                        </span>
                    )}
                </div>
                <div className="text-sm text-slate-700 line-clamp-3">
                    {verse.verse}
                </div>
                {verse.translation && (
                    <div className="text-xs text-slate-600 mt-2 line-clamp-2">
                        {verse.translation}
                    </div>
                )}
            </div>
        );
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

                    {/* Right Panel - Verse Display */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-medium text-slate-800">
                                {scriptureData.name}
                            </h3>
                            <div className="text-sm text-slate-600">
                                {scriptureData.verses.length} verses
                            </div>
                        </div>

                        {/* Navigation Controls */}
                        <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                            <div className="flex items-center space-x-2">
                                <button
                                    onClick={() => navigateVerse('prev')}
                                    disabled={currentVerse === 0}
                                    className="p-2 border border-slate-300 rounded hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                    </svg>
                                </button>
                                
                                <span className="text-sm text-slate-600">
                                    {currentVerse + 1} of {scriptureData.verses.length}
                                </span>
                                
                                <button
                                    onClick={() => navigateVerse('next')}
                                    disabled={currentVerse === scriptureData.verses.length - 1}
                                    className="p-2 border border-slate-300 rounded hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                </button>
                            </div>

                            <JumpToVerseInput />
                        </div>

                        {/* Verse List */}
                        <div className="space-y-3 max-h-96 overflow-y-auto">
                            {getDisplayVerses().map((verse, index) => (
                                <VerseCard
                                    key={verse.isExpander ? 'expander' : verse.seq_num}
                                    verse={verse}
                                    index={verse.isExpander ? null : scriptureData.verses.findIndex(v => v.seq_num === verse.seq_num)}
                                    isActive={!verse.isExpander && index === currentVerse}
                                />
                            ))}
                        </div>

                        {/* Selected Verse Details */}
                        {scriptureData.verses[currentVerse] && (
                            <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex flex-col">
                                            <h4 className="font-semibold text-slate-800">
                                                {scriptureData.verses[currentVerse].type} {scriptureData.verses[currentVerse].type_num}
                                            </h4>
                                            {scriptureData.verses[currentVerse].adhikar && (
                                                <span className="text-sm text-purple-600 font-medium">
                                                    {scriptureData.verses[currentVerse].adhikar}
                                                </span>
                                            )}
                                        </div>
                                        {scriptureData.verses[currentVerse].page_num && (
                                            <span className="text-sm text-slate-500">
                                                Page {scriptureData.verses[currentVerse].page_num}
                                            </span>
                                        )}
                                    </div>
                                    
                                    <div className="text-slate-700">
                                        <strong>Original:</strong> {scriptureData.verses[currentVerse].verse}
                                    </div>
                                    
                                    {scriptureData.verses[currentVerse].translation && (
                                        <div className="text-slate-700">
                                            <strong>Translation:</strong> {scriptureData.verses[currentVerse].translation}
                                        </div>
                                    )}
                                    
                                    {scriptureData.verses[currentVerse].meaning && (
                                        <div className="text-slate-700">
                                            <strong>Meaning:</strong> {scriptureData.verses[currentVerse].meaning}
                                        </div>
                                    )}
                                    
                                    {scriptureData.verses[currentVerse].teeka && scriptureData.verses[currentVerse].teeka.length > 0 && (
                                        <div className="text-slate-700">
                                            <strong>Teeka:</strong>
                                            <div className="mt-1 space-y-2">
                                                {scriptureData.verses[currentVerse].teeka.map((teekaItem, index) => (
                                                    <div key={index} className="pl-2 border-l-2 border-slate-300">
                                                        {teekaItem}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {scriptureData.verses[currentVerse].bhavarth && scriptureData.verses[currentVerse].bhavarth.length > 0 && (
                                        <div className="text-slate-700">
                                            <strong>Bhavarth:</strong>
                                            <div className="mt-1 space-y-2">
                                                {scriptureData.verses[currentVerse].bhavarth.map((bhavarthItem, index) => (
                                                    <div key={index} className="pl-2 border-l-2 border-slate-300">
                                                        {bhavarthItem}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
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