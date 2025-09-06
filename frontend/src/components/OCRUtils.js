import React, { useState, useRef, useEffect } from 'react';
import { Spinner } from './SharedComponents';

const API_BASE_URL = 'http://localhost:8500/api';

const OCRUtils = () => {
    const [selectedFile, setSelectedFile] = useState(null);
    const [language, setLanguage] = useState('hin');
    const [cropTop, setCropTop] = useState(0);
    const [cropBottom, setCropBottom] = useState(0);
    const [showOutlines, setShowOutlines] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [ocrResults, setOcrResults] = useState(null);
    const [error, setError] = useState(null);
    const [isPDF, setIsPDF] = useState(false);
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [pdfDoc, setPdfDoc] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [bookmarks, setBookmarks] = useState([]);
    const [showBookmarks, setShowBookmarks] = useState(false);
    const [showBookmarkModal, setShowBookmarkModal] = useState(false);

    // New state for batch processing
    const [batchJobId, setBatchJobId] = useState(null);
    const [batchJobStatus, setBatchJobStatus] = useState(null);
    const [batchProgress, setBatchProgress] = useState(0);
    const [batchTotalPages, setBatchTotalPages] = useState(0);
    const [batchZipFilename, setBatchZipFilename] = useState(null);

    const fileInputRef = useRef(null);
    const imageContainerRef = useRef(null);
    const pollingIntervalRef = useRef(null);

    // PDF.js dynamic loading
    useEffect(() => {
        const loadPdfJs = async () => {
            if (!window.pdfjsLib) {
                try {
                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
                    script.async = true;
                    
                    await new Promise((resolve, reject) => {
                        script.onload = resolve;
                        script.onerror = reject;
                        document.head.appendChild(script);
                    });
                }
                catch (error) {
                    console.error('Failed to load PDF.js:', error);
                    setError('Failed to load PDF.js library. PDF functionality will not be available.');
                }
            }
            
            if (window.pdfjsLib) {
                window.pdfjsLib.GlobalWorkerOptions.workerSrc = 
                    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            }
        };

        loadPdfJs();

        // Cleanup polling on component unmount
        return () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, []);

    const resetBatchState = () => {
        setBatchJobId(null);
        setBatchJobStatus(null);
        setBatchProgress(0);
        setBatchTotalPages(0);
        setBatchZipFilename(null);
        if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
        }
    };

    const handleFileSelect = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setSelectedFile(file);
        setOcrResults(null);
        setError(null);
        resetBatchState();
        
        const fileType = file.type;
        setIsPDF(fileType === 'application/pdf');

        if (fileType === 'application/pdf') {
            await loadPDF(file);
        } else {
            loadImagePreview(file);
        }
    };

    const loadImagePreview = (file) => {
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
    };

    const loadPDF = async (file) => {
        if (!window.pdfjsLib) {
            setError('PDF.js library not loaded. Please refresh the page.');
            return;
        }

        try {
            const arrayBuffer = await file.arrayBuffer();
            const pdf = await window.pdfjsLib.getDocument(arrayBuffer).promise;
            setPdfDoc(pdf);
            setTotalPages(pdf.numPages);
            setCurrentPage(1);
            
            try {
                const outline = await pdf.getOutline();
                if (outline && outline.length > 0) {
                    setBookmarks(outline);
                    setShowBookmarks(true);
                } else {
                    setBookmarks([]);
                    setShowBookmarks(false);
                }
            } catch (outlineErr) {
                console.warn('Could not load PDF outline:', outlineErr);
                setBookmarks([]);
                setShowBookmarks(false);
            }
            
            await renderPDFPage(pdf, 1);
        } catch (err) {
            setError(`Error loading PDF: ${err.message}`);
            console.error('PDF loading error:', err);
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
            setPreviewUrl(dataUrl);
        } catch (err) {
            setError(`Error rendering PDF page: ${err.message}`);
        }
    };

    const handlePageNavigation = async (direction) => {
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
            setOcrResults(null);
        }
    };

    const convertCurrentPageToImage = async () => {
        if (!pdfDoc) return null;
        
        try {
            const page = await pdfDoc.getPage(currentPage);
            const scale = 1.5;
            const viewport = page.getViewport({ scale });
            
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            
            await page.render({ canvasContext: context, viewport: viewport }).promise;
            
            return new Promise((resolve) => {
                canvas.toBlob((blob) => {
                    resolve(new File([blob], `page_${currentPage}.png`, { type: 'image/png' }));
                }, 'image/png');
            });
        } catch (err) {
            setError(`Error converting PDF page: ${err.message}`);
            return null;
        }
    };

    const handleOCRProcess = async () => {
        if (!selectedFile) {
            setError('Please select a file first');
            return;
        }

        setIsLoading(true);
        setError(null);
        setOcrResults(null);
        resetBatchState();

        try {
            let fileToProcess = selectedFile;
            
            if (isPDF) {
                fileToProcess = await convertCurrentPageToImage();
                if (!fileToProcess) {
                    throw new Error('Failed to convert PDF page to image');
                }
            }

            const formData = new FormData();
            formData.append('image', fileToProcess);
            formData.append('language', language);
            formData.append('crop_top', cropTop);
            formData.append('crop_bottom', cropBottom);

            const response = await fetch(`${API_BASE_URL}/ocr`, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || `HTTP error! status: ${response.status}`);
            }

            setOcrResults(data);
        } catch (err) {
            setError(`OCR processing failed: ${err.message}`);
            console.error('OCR Error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleBatchOCRProcess = async () => {
        if (!selectedFile || !isPDF) {
            setError('Please select a PDF file for batch processing.');
            return;
        }

        setIsLoading(true);
        setError(null);
        setOcrResults(null);
        resetBatchState();

        try {
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('language', language);

            const response = await fetch(`${API_BASE_URL}/ocr/batch`, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start batch job.');
            }

            setBatchJobId(data.job_id);
            setBatchJobStatus('queued');

        } catch (err) {
            setError(`Failed to start batch OCR job: ${err.message}`);
            setIsLoading(false);
        }
    };

    const handleCancelBatchJob = async () => {
        if (!batchJobId) return;

        try {
            setBatchJobStatus('canceling');
            const response = await fetch(`${API_BASE_URL}/ocr/batch/cancel/${batchJobId}`, {
                method: 'POST',
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Failed to cancel job.');
            }

            // The polling will handle the final state change
        } catch (err) {
            setError(`Error canceling job: ${err.message}`);
        }
    };

    useEffect(() => {
        if (batchJobId && (batchJobStatus === 'queued' || batchJobStatus === 'preparing' || batchJobStatus === 'processing' || batchJobStatus === 'canceling')) {
            pollingIntervalRef.current = setInterval(async () => {
                try {
                    const response = await fetch(`${API_BASE_URL}/ocr/batch/status/${batchJobId}`);
                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.detail || 'Failed to get job status.');
                    }

                    setBatchJobStatus(data.status);
                    setBatchProgress(data.progress);
                    setBatchTotalPages(data.total_pages);

                    if (data.status === 'completed') {
                        setBatchZipFilename(data.zip_filename);
                    }

                    if (data.status === 'completed' || data.status === 'failed' || data.status === 'canceled') {
                        clearInterval(pollingIntervalRef.current);
                        setIsLoading(false);
                        if (data.status === 'failed') {
                            setError(`Batch processing failed: ${data.error}`);
                        }
                    }
                } catch (err) {
                    setError(`Error polling for job status: ${err.message}`);
                    clearInterval(pollingIntervalRef.current);
                    setIsLoading(false);
                }
            }, 3000);
        }

        return () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, [batchJobId, batchJobStatus]);


    const clearHighlights = () => {
        if (imageContainerRef.current) {
            const highlights = imageContainerRef.current.querySelectorAll('.highlight-box');
            highlights.forEach(highlight => highlight.remove());
        }
    };

    const addHighlights = (boxes, isParagraphSpecific = false) => {
        if (!imageContainerRef.current || !previewUrl) return;

        const img = imageContainerRef.current.querySelector('img');
        if (!img) return;

        const scaleX = img.clientWidth / img.naturalWidth;
        const scaleY = img.clientHeight / img.naturalHeight;

        boxes.forEach((box) => {
            const highlightDiv = document.createElement('div');
            highlightDiv.className = 'highlight-box';
            highlightDiv.style.position = 'absolute';
            highlightDiv.style.border = isParagraphSpecific ? '2px solid #28a745' : '2px solid blue';
            highlightDiv.style.backgroundColor = isParagraphSpecific ? 'rgba(40, 167, 69, 0.2)' : 'rgba(0, 0, 255, 0.1)';
            highlightDiv.style.pointerEvents = 'none';
            
            highlightDiv.style.left = (box.x * scaleX) + 'px';
            highlightDiv.style.top = (box.y * scaleY) + 'px';
            highlightDiv.style.width = (box.width * scaleX) + 'px';
            highlightDiv.style.height = (box.height * scaleY) + 'px';
            
            imageContainerRef.current.appendChild(highlightDiv);
        });
    };

    const updateHighlights = () => {
        clearHighlights();
        
        if (!ocrResults || !showOutlines) {
            return;
        }
        
        if (ocrResults.boxes && ocrResults.boxes.length > 0) {
            addHighlights(ocrResults.boxes);
        }
    };

    const handleParagraphClick = (paragraph, index) => {
        clearHighlights();
        if (paragraph.boxes && paragraph.boxes.length > 0) {
            addHighlights(paragraph.boxes, true);
        }
        
        const paragraphElements = document.querySelectorAll('.paragraph-item');
        paragraphElements.forEach(el => el.classList.remove('active'));
        
        const clickedElement = document.querySelector(`[data-paragraph-index="${index}"]`);
        if (clickedElement) {
            clickedElement.classList.add('active');
        }
    };

    useEffect(() => {
        updateHighlights();
    }, [showOutlines, ocrResults]);

    const handleBookmarkClick = async (bookmark) => {
        if (!pdfDoc || !bookmark.dest) return;
        
        try {
            let dest = bookmark.dest;
            if (typeof dest === 'string') {
                dest = await pdfDoc.getDestination(dest);
            }
            
            if (dest && dest.length > 0) {
                const pageRef = dest[0];
                const pageNumber = await pdfDoc.getPageIndex(pageRef) + 1;
                
                if (pageNumber !== currentPage) {
                    setCurrentPage(pageNumber);
                    await renderPDFPage(pdfDoc, pageNumber);
                    setOcrResults(null);
                }
            }
            
            setShowBookmarkModal(false);
        } catch (err) {
            console.error('Error navigating to bookmark:', err);
        }
    };

    const BookmarkItem = ({ item, level = 0 }) => {
        const [isExpanded, setIsExpanded] = useState(level < 2);
        
        const hasChildren = item.items && item.items.length > 0;
        const indent = level * 16;
        
        return (
            <div className="select-none">
                <div 
                    className="flex items-center py-1 px-2 hover:bg-slate-100 rounded cursor-pointer text-sm"
                    style={{ paddingLeft: `${8 + indent}px` }}
                    onClick={() => handleBookmarkClick(item)}
                >
                    {hasChildren && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setIsExpanded(!isExpanded);
                            }}
                            className="mr-1 p-0.5 hover:bg-slate-200 rounded flex-shrink-0"
                        >
                            <svg 
                                className={`w-3 h-3 transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                                fill="none" 
                                stroke="currentColor" 
                                viewBox="0 0 24 24"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                        </button>
                    )}
                    {!hasChildren && <div className="w-4 flex-shrink-0" />}
                    <span 
                        className="text-slate-700 hover:text-slate-900 truncate flex-1"
                        title={item.title}
                    >
                        {item.title}
                    </span>
                </div>
                
                {hasChildren && isExpanded && (
                    <div>
                        {item.items.map((child, index) => (
                            <BookmarkItem key={index} item={child} level={level + 1} />
                        ))}
                    </div>
                )}
            </div>
        );
    };

    const ProgressBar = ({ progress, total }) => {
        const percentage = total > 0 ? Math.round((progress / total) * 100) : 0;
        return (
            <div className="w-full bg-slate-200 rounded-full h-2.5">
                <div 
                    className="bg-sky-600 h-2.5 rounded-full transition-all duration-500" 
                    style={{ width: `${percentage}%` }}
                ></div>
            </div>
        );
    };

    return (
        <div>
            {/* Bookmarks Modal */}
            {showBookmarkModal && bookmarks.length > 0 && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[80vh] overflow-hidden">
                        <div className="flex items-center justify-between p-4 border-b border-slate-200">
                            <h3 className="text-lg font-semibold text-slate-800">Select Bookmark</h3>
                            <button
                                onClick={() => setShowBookmarkModal(false)}
                                className="text-slate-500 hover:text-slate-700 p-1 rounded"
                                title="Close bookmarks"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="p-4 overflow-y-auto max-h-[60vh]">
                            <div className="space-y-1">
                                {bookmarks.map((bookmark, index) => (
                                    <BookmarkItem key={index} item={bookmark} level={0} />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Main OCR Utils Panel Container */}
            <div className="bg-white rounded-lg shadow-sm border border-slate-200" style={{ width: '130%', maxWidth: 'none' }}>
                {/* Header */}
                <div className="p-4 border-b border-slate-200">
                    <h2 className="text-2xl font-bold text-slate-800 mb-2">OCR Utils</h2>
                    <p className="text-slate-600">Extract text from images and PDF documents with OCR technology</p>
                </div>

                {/* Controls */}
                <div className="p-4 border-b border-slate-200 bg-slate-50">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* File Input */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                Select File
                            </label>
                            <div className="relative">
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept="image/*,application/pdf"
                                    onChange={handleFileSelect}
                                    className="sr-only"
                                    id="file-upload"
                                />
                                <label
                                    htmlFor="file-upload"
                                    className="block w-full text-sm text-slate-500 border border-slate-300 rounded-md px-3 py-2 cursor-pointer bg-white hover:bg-slate-50 transition-colors"
                                >
                                    <span className="inline-flex items-center">
                                        <span className="bg-sky-50 text-sky-700 font-semibold px-4 py-2 rounded-md mr-4 hover:bg-sky-100">
                                            Upload a file
                                        </span>
                                        <span className="text-slate-500">
                                            {selectedFile ? selectedFile.name : 'No file selected'}
                                        </span>
                                    </span>
                                </label>
                            </div>
                        </div>

                        {/* Language Selection */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                Language
                            </label>
                            <select
                                value={language}
                                onChange={(e) => setLanguage(e.target.value)}
                                className="block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-sky-500 focus:border-sky-500"
                            >
                                <option value="hin">Hindi</option>
                                <option value="guj">Gujarati</option>
                                <option value="eng">English</option>
                            </select>
                        </div>

                        {/* Crop Controls */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                Crop Top (%)
                            </label>
                            <input
                                type="number"
                                min="0"
                                max="50"
                                value={cropTop}
                                onChange={(e) => setCropTop(parseInt(e.target.value) || 0)}
                                className="block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-sky-500 focus:border-sky-500"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                Crop Bottom (%)
                            </label>
                            <input
                                type="number"
                                min="0"
                                max="50"
                                value={cropBottom}
                                onChange={(e) => setCropBottom(parseInt(e.target.value) || 0)}
                                className="block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-sky-500 focus:border-sky-500"
                            />
                        </div>
                    </div>

                    {/* Additional Controls */}
                    <div className="flex items-center justify-between mt-4">
                        <div className="flex items-center space-x-4">
                            {/* Outline Toggle */}
                            <label className="flex items-center text-sm text-slate-700">
                                <input
                                    type="checkbox"
                                    checked={showOutlines}
                                    onChange={(e) => setShowOutlines(e.target.checked)}
                                    className="mr-2 h-4 w-4 text-sky-600 focus:ring-sky-500 border-slate-300 rounded"
                                />
                                Show text outlines
                            </label>

                            {/* PDF Navigation */}
                            {isPDF && pdfDoc && (
                                <div className="flex items-center space-x-2 text-sm">
                                    <button
                                        onClick={() => handlePageNavigation('prev')}
                                        disabled={currentPage === 1}
                                        className="px-2 py-1 bg-slate-200 text-slate-700 rounded disabled:opacity-50 hover:bg-slate-300"
                                    >
                                        ←
                                    </button>
                                    <span className="text-slate-600">
                                        Page {currentPage} of {totalPages}
                                    </span>
                                    <button
                                        onClick={() => handlePageNavigation('next')}
                                        disabled={currentPage === totalPages}
                                        className="px-2 py-1 bg-slate-200 text-slate-700 rounded disabled:opacity-50 hover:bg-slate-300"
                                    >
                                        →
                                    </button>
                                </div>
                            )}

                            {/* Show bookmarks toggle */}
                            {isPDF && bookmarks.length > 0 && (
                                <button
                                    onClick={() => setShowBookmarkModal(true)}
                                    className="text-sm text-sky-600 hover:text-sky-800 flex items-center"
                                >
                                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                                    </svg>
                                    Show Bookmarks
                                </button>
                            )}
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center space-x-2">
                            {isPDF && (
                                <button
                                    onClick={handleBatchOCRProcess}
                                    disabled={!selectedFile || isLoading}
                                    className="bg-green-600 text-white font-semibold py-2 px-4 rounded-md hover:bg-green-700 transition duration-200 disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center"
                                >
                                    {isLoading && batchJobId ? (
                                        <>
                                            <Spinner />
                                            <span className="ml-2">Processing PDF...</span>
                                        </>
                                    ) : (
                                        'Download Full PDF Text'
                                    )}
                                </button>
                            )}
                            <button
                                onClick={handleOCRProcess}
                                disabled={!selectedFile || isLoading}
                                className="bg-sky-600 text-white font-semibold py-2 px-4 rounded-md hover:bg-sky-700 transition duration-200 disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center"
                            >
                                {isLoading && !batchJobId ? (
                                    <>
                                        <Spinner />
                                        <span className="ml-2">Processing...</span>
                                    </>
                                ) : (
                                    'Run OCR on Current Page'
                                )}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Batch Progress Bar */}
                {batchJobId && (
                    <div className="p-4 border-b border-slate-200">
                        <div className="flex items-center justify-between mb-2">
                            <h3 className="text-sm font-medium text-slate-700">
                                {batchJobStatus === 'queued' && 'Server at max limit, waiting for a slot to be freed....'}
                                {batchJobStatus === 'preparing' && 'Preparing PDF for processing...'}
                                {batchJobStatus === 'processing' && `Processing PDF... (${batchProgress} / ${batchTotalPages} pages)`}
                                {batchJobStatus === 'canceling' && 'Canceling job...'}
                                {batchJobStatus === 'canceled' && 'Job was canceled.'}
                                {batchJobStatus === 'completed' && 'PDF processing complete!'}
                                {batchJobStatus === 'failed' && 'PDF processing failed.'}
                            </h3>
                            {(batchJobStatus === 'processing' || batchJobStatus === 'queued' || batchJobStatus === 'preparing') && (
                                <button
                                    onClick={handleCancelBatchJob}
                                    className="text-sm bg-red-500 text-white font-semibold py-1 px-3 rounded-md hover:bg-red-600 transition duration-200"
                                >
                                    Cancel
                                </button>
                            )}
                        </div>
                        {(batchJobStatus === 'processing' || batchJobStatus === 'queued' || batchJobStatus === 'preparing') && (
                            <ProgressBar progress={batchProgress} total={batchTotalPages} />
                        )}
                        {batchJobStatus === 'completed' && (
                             <a
                                href={`${API_BASE_URL}/ocr/batch/download/${batchJobId}`}
                                download={batchZipFilename || 'extracted_text.zip'}
                                className="inline-block bg-sky-600 text-white font-semibold py-2 px-4 rounded-md hover:bg-sky-700 transition duration-200"
                            >
                                Download Zip File
                            </a>
                        )}
                    </div>
                )}

                {/* Error Display */}
                {error && (
                    <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
                        <p className="text-red-800 text-sm">{error}</p>
                    </div>
                )}

                {/* Content Panels */}
                <div className="flex flex-col lg:flex-row">
                    {/* Image Preview Panel */}
                    <div className="flex-1 p-4">
                        <h3 className="text-lg font-semibold text-slate-800 mb-3">Preview</h3>
                        <div 
                            ref={imageContainerRef}
                            className="relative border border-slate-300 rounded-lg overflow-hidden bg-slate-50 min-h-[300px] w-full"
                        >
                            {previewUrl ? (
                                <img
                                    src={previewUrl}
                                    alt="Preview"
                                    className="max-w-full max-h-[700px] object-contain"
                                    onLoad={updateHighlights}
                                />
                            ) : (
                                <div className="flex items-center justify-center h-64 text-slate-500">
                                    <div className="text-center">
                                        <svg className="mx-auto h-12 w-12 text-slate-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                                            <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                                        </svg>
                                        <p className="mt-2">Select an image or PDF file to preview</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Results Panel */}
                    <div className="flex-1 p-4 border-l border-slate-200">
                        <h3 className="text-lg font-semibold text-slate-800 mb-3">OCR Results</h3>
                        <div className="space-y-3 max-h-[700px] overflow-y-auto">
                            {ocrResults?.paragraphs?.length > 0 ? (
                                ocrResults.paragraphs.map((paragraph, index) => (
                                    <div
                                        key={index}
                                        data-paragraph-index={index}
                                        onClick={() => handleParagraphClick(paragraph, index)}
                                        className="paragraph-item bg-slate-50 border border-slate-200 rounded-lg p-3 cursor-pointer hover:bg-slate-100 transition-colors"
                                    >
                                        <div className="text-xs text-slate-500 font-semibold mb-2">
                                            Paragraph {index + 1}
                                        </div>
                                        <div className="text-sm text-slate-800 whitespace-pre-wrap font-mono">
                                            {paragraph.text}
                                        </div>
                                    </div>
                                ))
                            ) : ocrResults ? (
                                <div className="text-center py-8 text-slate-500">
                                    No text detected in the image.
                                </div>
                            ) : (
                                <div className="flex items-center justify-center h-64 text-slate-500 border border-slate-300 rounded-lg bg-slate-50">
                                    <div className="text-center">
                                        <svg className="mx-auto h-12 w-12 text-slate-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                        </svg>
                                        <p className="mt-2">Upload a file and run OCR to see extracted text here</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <style>{`
                    .highlight-box {
                        transition: background-color 0.3s ease;
                    }
                    .paragraph-item.active {
                        background-color: #d1fae5 !important;
                        border-color: #a7f3d0 !important;
                    }
                `}</style>
            </div>
        </div>
    );
};

export default OCRUtils;
