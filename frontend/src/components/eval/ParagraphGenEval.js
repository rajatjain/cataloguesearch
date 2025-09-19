import React, { useState, useRef, useEffect } from 'react';
import { Spinner } from '../SharedComponents';
import { api } from '../../services/api';
import FileBrowser from './FileBrowser';
import BookmarksModal from '../BookmarksModal';
import { 
    storeDirectoryHandles, 
    getStoredDirectoryHandles, 
    clearStoredDirectoryHandles,
    validateDirectoryHandles,
    navigateToPath,
    loadFilesFromDirectory,
    readFileContent
} from '../../utils/directoryHandlers';

const ParagraphGenEval = ({ onBrowseFiles, showFileBrowser, onCloseFileBrowser, basePaths: parentBasePaths, selectedFolder: propSelectedFolder, onBaseDirectoryHandlesChange }) => {
    const [selectedFolder, setSelectedFolder] = useState(propSelectedFolder || null);
    const [sourceHandle, setSourceHandle] = useState(null);
    const [targetHandle, setTargetHandle] = useState(null);
    const [fileList, setFileList] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(-1);
    const [sourceContent, setSourceContent] = useState('');
    const [targetContent, setTargetContent] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [jumpPageNumber, setJumpPageNumber] = useState('');
    const [basePaths, setBasePaths] = useState(parentBasePaths || null);
    const [baseDirectoryHandles, setBaseDirectoryHandles] = useState({
        pdf: null,
        ocr: null,
        text: null
    });
    const [permissionsGranted, setPermissionsGranted] = useState(false);
    
    // Bookmarks functionality
    const [bookmarks, setBookmarks] = useState([]);
    const [showBookmarksModal, setShowBookmarksModal] = useState(false);
    const [pdfDoc, setPdfDoc] = useState(null);
    
    // PDF.js loading
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
                } catch (error) {
                    console.error('Failed to load PDF.js:', error);
                }
            }
            
            if (window.pdfjsLib) {
                window.pdfjsLib.GlobalWorkerOptions.workerSrc = 
                    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            }
        };

        loadPdfJs();
    }, []);

    // Load persisted directory handles on component mount
    useEffect(() => {
        const loadPersistedHandles = async () => {
            try {
                const stored = await getStoredDirectoryHandles();
                if (stored.pdf && stored.ocr && stored.text) {
                    const isValid = await validateDirectoryHandles(stored);
                    if (isValid) {
                        setBaseDirectoryHandles(stored);
                        setPermissionsGranted(true);
                        
                        if (onBaseDirectoryHandlesChange) {
                            onBaseDirectoryHandlesChange(stored);
                        }
                        // console.log('Successfully restored directory handles from storage');
                    } else {
                        console.log('Stored handles no longer have permission, clearing storage');
                        await clearStoredDirectoryHandles();
                    }
                }
            } catch (err) {
                console.log('Could not restore directory handles:', err);
                await clearStoredDirectoryHandles();
            }
        };

        loadPersistedHandles();
    }, [onBaseDirectoryHandlesChange]);


    // Load base paths from API if not provided by parent
    useEffect(() => {
        if (!parentBasePaths) {
            const loadBasePaths = async () => {
                try {
                    const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api';
                    const response = await fetch(`${API_BASE_URL}/eval/paths`);
                    const data = await response.json();
                    setBasePaths(data);
                } catch (err) {
                    setError(`Failed to load configuration: ${err.message}`);
                }
            };
            loadBasePaths();
        } else {
            setBasePaths(parentBasePaths);
        }
    }, [parentBasePaths]);

    // Request base directory permissions when component loads
    const requestBaseDirectoryPermissions = async () => {
        if (!basePaths) return;
        
        try {
            setIsLoading(true);
            setError(null);
            
            // Check if File System Access API is available
            if (!window.showDirectoryPicker) {
                throw new Error('File System Access API is not supported in this browser. Please use Google Chrome for the best experience.');
            }
            
            // Request PDF directory
            const pdfHandle = await window.showDirectoryPicker();
            
            // Request OCR directory
            const ocrHandle = await window.showDirectoryPicker();
            
            // Request Text directory
            const textHandle = await window.showDirectoryPicker();
            
            // Store all handles
            const handles = {
                pdf: pdfHandle,
                ocr: ocrHandle,
                text: textHandle
            };
            setBaseDirectoryHandles(handles);
            setPermissionsGranted(true);
            
            // Store in IndexedDB for persistence
            await storeDirectoryHandles(handles);
            
            // Notify parent component about the base directory handles
            if (onBaseDirectoryHandlesChange) {
                onBaseDirectoryHandlesChange(handles);
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(`Error requesting directory permissions: ${err.message}`);
            }
        } finally {
            setIsLoading(false);
        }
    };

    // Update selectedFolder when prop changes and automatically process if permissions granted
    useEffect(() => {
        if (propSelectedFolder && propSelectedFolder !== selectedFolder) {
            setSelectedFolder(propSelectedFolder);
            // Automatically process if we have base directory permissions
            if (propSelectedFolder && permissionsGranted) {
                processSelectedFolder(propSelectedFolder);
            }
        }
    }, [propSelectedFolder, permissionsGranted]);

    // Process selected folder using base directory handles
    const processSelectedFolder = async (selection) => {
        if (!baseDirectoryHandles.ocr || !baseDirectoryHandles.text) {
            setError('Base directory permissions not granted. Please grant permissions first.');
            return;
        }

        try {
            setIsLoading(true);
            setError(null);

            // Navigate to the relative path in both OCR and Text directories
            const relativePath = selection.relativePath;
            
            // Get source directory handle (OCR)
            const sourceDir = await navigateToPath(baseDirectoryHandles.ocr, relativePath);
            if (!sourceDir) {
                setError(`Source directory not found: ${selection.sourcePath}`);
                return;
            }
            
            // Get target directory handle (Text)
            const targetDir = await navigateToPath(baseDirectoryHandles.text, relativePath);
            if (!targetDir) {
                setError(`Target directory not found: ${selection.targetPath}`);
                return;
            }

            setSourceHandle(sourceDir);
            setTargetHandle(targetDir);
            
            // Load and display files
            const files = await loadFiles(sourceDir);
            if (files.length > 0) {
                setCurrentIndex(0);
                await displayFiles(files[0], sourceDir, targetDir);
            }
        } catch (err) {
            setError(`Error processing selected folder: ${err.message}`);
        } finally {
            setIsLoading(false);
        }
    };


    const handleFolderSelect = async (selection) => {
        setSelectedFolder(selection);
        setError(null);
        
        // If permissions are granted, process immediately, otherwise use old flow
        if (permissionsGranted) {
            processSelectedFolder(selection);
        } else {
            promptForDirectories(selection);
        }
    };

    // Fallback function for manual directory selection (when permissions not granted)
    const promptForDirectories = async (selection) => {
        try {
            const message = `Selected: ${selection.selectedPDFFile || selection.selectedFolderName}
            
Calculated paths:
• Source: ${selection.sourcePath}
• Target: ${selection.targetPath}

Please select the SOURCE directory (${selection.sourcePath})`;
            
            if (window.confirm(message)) {
                const sourceHandle = await window.showDirectoryPicker();
                setSourceHandle(sourceHandle);
                
                const targetMessage = `Now select the TARGET directory (${selection.targetPath})`;
                if (window.confirm(targetMessage)) {
                    const targetHandle = await window.showDirectoryPicker();
                    setTargetHandle(targetHandle);
                    
                    checkAndStart(sourceHandle, targetHandle);
                } else {
                    setSourceHandle(null);
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(`Error selecting directories: ${err.message}`);
            }
            console.log("User cancelled directory selection.");
        }
    };

    const checkAndStart = async (sourceDir, targetDir) => {
        if (sourceDir && targetDir) {
            setIsLoading(true);
            setError(null);
            try {
                const files = await loadFiles(sourceDir);
                if (files.length > 0) {
                    setCurrentIndex(0);
                    await displayFiles(files[0], sourceDir, targetDir);
                }
            } catch (err) {
                setError(`Error loading files: ${err.message}`);
            } finally {
                setIsLoading(false);
            }
        }
    };

    const loadFiles = async (sourceDir) => {
        const sortedFiles = await loadFilesFromDirectory(sourceDir);
        setFileList(sortedFiles);
        return sortedFiles;
    };


    const displayFiles = async (fileName, sourceDir = sourceHandle, targetDir = targetHandle) => {
        if (!fileName || !sourceDir || !targetDir) return;

        setIsLoading(true);
        try {
            const [sourceText, targetText] = await Promise.all([
                readFileContent(sourceDir, fileName),
                readFileContent(targetDir, fileName)
            ]);

            setSourceContent(sourceText);
            setTargetContent(targetText);
            
            // Update jump page number input
            const pageNumber = parseInt(fileName.replace('page_', '').replace('.txt', ''), 10);
            setJumpPageNumber(pageNumber.toString());
        } catch (err) {
            setError(`Error displaying files: ${err.message}`);
        } finally {
            setIsLoading(false);
        }
    };

    const navigate = (direction) => {
        const newIndex = currentIndex + direction;
        if (newIndex >= 0 && newIndex < fileList.length) {
            setCurrentIndex(newIndex);
            displayFiles(fileList[newIndex]);
        }
    };

    const jumpToPage = () => {
        const pageNum = parseInt(jumpPageNumber, 10);
        if (isNaN(pageNum) || pageNum < 1) {
            return;
        }

        const fileName = `page_${String(pageNum).padStart(4, '0')}.txt`;
        const foundIndex = fileList.indexOf(fileName);

        if (foundIndex !== -1) {
            setCurrentIndex(foundIndex);
            displayFiles(fileName);
        } else {
            setError(`Page ${pageNum} (${fileName}) not found.`);
            setTimeout(() => setError(null), 3000);
        }
    };

    const handleKeyDown = (event) => {
        if (event.key === 'Enter') {
            jumpToPage();
        }
    };

    const getCurrentFileName = () => {
        return currentIndex >= 0 && currentIndex < fileList.length 
            ? fileList[currentIndex] 
            : '';
    };

    // Load bookmarks from the selected PDF file
    const loadPDFBookmarks = async () => {
        if (!selectedFolder?.selectedPDFFile || !baseDirectoryHandles.pdf) return;

        try {
            console.log('Loading bookmarks for:', selectedFolder);
            
            // The relativePath includes the full path to the PDF directory
            // We need to navigate to the parent directory and then get the PDF file
            const pathParts = selectedFolder.relativePath.split('/');
            const pdfDirectory = pathParts.slice(0, -1).join('/'); // Remove the last part (PDF name without extension)
            
            console.log('PDF directory path:', pdfDirectory);
            console.log('PDF file name:', selectedFolder.selectedPDFFile);
            
            const pdfDirHandle = await navigateToPath(
                baseDirectoryHandles.pdf, 
                pdfDirectory
            );
            
            if (!pdfDirHandle) {
                console.error('Could not navigate to PDF directory:', pdfDirectory);
                return;
            }
            
            const pdfFileHandle = await pdfDirHandle.getFileHandle(selectedFolder.selectedPDFFile);
            const pdfFile = await pdfFileHandle.getFile();
            const arrayBuffer = await pdfFile.arrayBuffer();
            
            if (window.pdfjsLib) {
                const loadingTask = window.pdfjsLib.getDocument(arrayBuffer);
                const pdf = await loadingTask.promise;
                setPdfDoc(pdf);
                
                // Extract bookmarks
                const outline = await pdf.getOutline();
                console.log('PDF outline result:', outline);
                if (outline && outline.length > 0) {
                    setBookmarks(outline);
                    console.log('Bookmarks loaded:', outline.length, outline);
                } else {
                    setBookmarks([]);
                    console.log('No bookmarks found in PDF');
                }
            }
        } catch (err) {
            console.error('Error loading PDF bookmarks:', err);
            setBookmarks([]);
        }
    };

    // Handle bookmark click to navigate to page
    const handleBookmarkClick = async (bookmark) => {
        if (!pdfDoc || !bookmark.dest) return;

        try {
            let dest = bookmark.dest;
            
            // If dest is a string, get the actual destination
            if (typeof dest === 'string') {
                dest = await pdfDoc.getDestination(dest);
            }
            
            if (dest && dest[0]) {
                const pageRef = dest[0];
                const pageIndex = await pdfDoc.getPageIndex(pageRef);
                const pageNumber = pageIndex + 1; // PDF pages are 1-indexed
                
                console.log(`Bookmark "${bookmark.title}" points to page ${pageNumber}`);
                
                // Jump to the corresponding page file
                jumpToPageByNumber(pageNumber);
            }
        } catch (err) {
            console.error('Error navigating to bookmark:', err);
        }
    };

    // Jump to a specific page number (helper function)
    const jumpToPageByNumber = (pageNumber) => {
        const fileName = `page_${String(pageNumber).padStart(4, '0')}.txt`;
        const foundIndex = fileList.indexOf(fileName);

        if (foundIndex !== -1) {
            setCurrentIndex(foundIndex);
            displayFiles(fileName);
            setJumpPageNumber(pageNumber.toString());
        } else {
            setError(`Page ${pageNumber} (${fileName}) not found in the comparison files.`);
            setTimeout(() => setError(null), 3000);
        }
    };

    // Load bookmarks when a PDF is selected and directories are set up
    useEffect(() => {
        if (selectedFolder?.selectedPDFFile && permissionsGranted && sourceHandle && targetHandle) {
            loadPDFBookmarks();
        }
    }, [selectedFolder, permissionsGranted, sourceHandle, targetHandle]);

    // Show directory selection if no directories selected
    if (!sourceHandle || !targetHandle) {
        return (
            <div className="bg-white rounded-lg shadow-sm border border-slate-200" style={{ width: '130%', maxWidth: 'none' }}>
                {/* Header */}
                <div className="p-4 border-b border-slate-200">
                    <h2 className="text-2xl font-bold text-slate-800 mb-2">Paragraph Generation Evaluation</h2>
                    <p className="text-slate-600">Compare generated paragraphs between source and target directories</p>
                </div>

                {/* Directory Selection */}
                <div className="p-8 text-center">
                    <h3 className="text-lg font-semibold text-slate-800 mb-4">Select Directories to Compare</h3>
                    <p className="text-slate-600 mb-6">Please select the source and target directories to begin comparison.</p>
                    
                    {basePaths && (
                        <div className="mb-6 p-4 bg-slate-50 rounded-lg">
                            <h4 className="font-semibold text-slate-700 mb-2">Configuration Paths:</h4>
                            <div className="text-sm text-slate-600 space-y-1">
                                <div><strong>Base PDF:</strong> {basePaths.base_pdf_path}</div>
                                <div><strong>OCR Path:</strong> {basePaths.base_ocr_path}</div>
                                <div><strong>Text Path:</strong> {basePaths.base_text_path}</div>
                            </div>
                        </div>
                    )}
                    
                    <div className="flex flex-col gap-4 max-w-md mx-auto">
                        {!permissionsGranted && (
                            <div className="mb-4">
                                <p className="text-sm text-slate-600 mb-4">
                                    First, grant permissions to your base directories for seamless operation.
                                </p>
                                <button
                                    onClick={requestBaseDirectoryPermissions}
                                    disabled={isLoading || !basePaths}
                                    className="w-full bg-sky-600 text-white font-semibold py-3 px-4 rounded-md hover:bg-sky-700 transition duration-200 disabled:bg-slate-400"
                                >
                                    {isLoading ? 'Setting up...' : 'Grant Directory Permissions'}
                                </button>
                            </div>
                        )}
                        
                        {permissionsGranted && (
                            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md">
                                <div className="flex items-center">
                                    <svg className="w-5 h-5 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                    </svg>
                                    <span className="text-green-800 font-medium">Directory permissions granted!</span>
                                </div>
                                <p className="text-sm text-green-700 mt-2">
                                    Now you can select PDF files and comparisons will start automatically.
                                </p>
                            </div>
                        )}
                        
                        <p className="text-sm text-slate-600 mb-2">
                            Use the Browse Files button above to select a PDF file from the base PDF directory.
                            {permissionsGranted 
                                ? ' Comparisons will start automatically!' 
                                : ' You\'ll need to manually select directories for each comparison.'}
                        </p>
                        
                        {/* Only show detailed folder info when permissions are NOT granted (manual mode) */}
                        {!permissionsGranted && selectedFolder && (
                            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-left">
                                <h4 className="font-semibold text-blue-800 mb-2">
                                    {selectedFolder.selectedPDFFile ? 'Selected PDF File:' : 'Selected Folder:'}
                                </h4>
                                <div className="text-sm text-blue-700 space-y-1 mb-4">
                                    {selectedFolder.selectedPDFFile && (
                                        <div><strong>PDF File:</strong> {selectedFolder.selectedPDFFile}</div>
                                    )}
                                    <div><strong>Directory Name:</strong> {selectedFolder.selectedFolderName}</div>
                                    <div><strong>Relative Path:</strong> {selectedFolder.relativePath}</div>
                                    <div><strong>Source Path:</strong> {selectedFolder.sourcePath}</div>
                                    <div><strong>Target Path:</strong> {selectedFolder.targetPath}</div>
                                </div>
                                <button
                                    onClick={() => promptForDirectories(selectedFolder)}
                                    className="w-full bg-green-600 text-white font-semibold py-2 px-4 rounded-md hover:bg-green-700 transition duration-200"
                                >
                                    Start Comparison - Select Directories
                                </button>
                            </div>
                        )}
                    </div>

                    {sourceHandle && (
                        <div className="mt-4 text-sm text-slate-600">
                            ✓ Source: {sourceHandle.name}
                        </div>
                    )}
                    {targetHandle && (
                        <div className="mt-2 text-sm text-slate-600">
                            ✓ Target: {targetHandle.name}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-lg shadow-sm border border-slate-200" style={{ width: '130%', maxWidth: 'none' }}>
                {/* Header */}
                <div className="p-4 border-b border-slate-200">
                    <h2 className="text-2xl font-bold text-slate-800 mb-2">Paragraph Generation Evaluation</h2>
                    <p className="text-slate-600">
                        {selectedFolder?.selectedPDFFile 
                            ? `Comparing: ${selectedFolder.relativePath}/${selectedFolder.selectedPDFFile}`
                            : `Comparing: ${sourceHandle?.name} vs ${targetHandle?.name}`
                        }
                    </p>
                </div>

            {/* Controls */}
            <div className="p-4 border-b border-slate-200 bg-slate-50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                        {/* Navigation Controls */}
                        <button
                            onClick={() => navigate(-1)}
                            disabled={currentIndex <= 0 || isLoading}
                            className="px-3 py-2 bg-slate-200 text-slate-700 rounded disabled:opacity-50 hover:bg-slate-300 transition-colors"
                        >
                            ← Previous
                        </button>
                        
                        <div className="text-sm font-medium text-slate-700 min-w-[200px] text-center">
                            {getCurrentFileName() && (
                                <>Displaying: {getCurrentFileName()}</>
                            )}
                        </div>
                        
                        <button
                            onClick={() => navigate(1)}
                            disabled={currentIndex >= fileList.length - 1 || isLoading}
                            className="px-3 py-2 bg-slate-200 text-slate-700 rounded disabled:opacity-50 hover:bg-slate-300 transition-colors"
                        >
                            Next →
                        </button>
                    </div>

                    {/* Jump Controls and Bookmarks */}
                    <div className="flex items-center space-x-2">
                        {/* Bookmarks Button - Show when PDF is selected */}
                        {selectedFolder?.selectedPDFFile && (
                            <button
                                onClick={() => setShowBookmarksModal(true)}
                                className={`px-3 py-1 text-sm rounded-md hover:bg-purple-700 transition-colors flex items-center ${
                                    bookmarks.length > 0 
                                        ? 'bg-purple-600 text-white' 
                                        : 'bg-gray-400 text-white cursor-not-allowed'
                                }`}
                                title={bookmarks.length > 0 ? `Show bookmarks (${bookmarks.length} found)` : "No bookmarks found in PDF"}
                                disabled={bookmarks.length === 0}
                            >
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                                </svg>
                                Bookmarks {bookmarks.length > 0 ? `(${bookmarks.length})` : '(0)'}
                            </button>
                        )}
                        
                        <label className="text-sm font-medium text-slate-700">
                            Jump to Page:
                        </label>
                        <input
                            type="number"
                            min="1"
                            value={jumpPageNumber}
                            onChange={(e) => setJumpPageNumber(e.target.value)}
                            onKeyDown={handleKeyDown}
                            className="w-20 px-2 py-1 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-sky-500 focus:border-sky-500"
                            disabled={isLoading}
                        />
                        <button
                            onClick={jumpToPage}
                            disabled={isLoading}
                            className="px-3 py-1 text-sm bg-sky-600 text-white rounded-md hover:bg-sky-700 transition-colors disabled:bg-slate-300"
                        >
                            Go
                        </button>
                    </div>

                    {/* Reset Button */}
                    <button
                        onClick={() => {
                            setSourceHandle(null);
                            setTargetHandle(null);
                            setFileList([]);
                            setCurrentIndex(-1);
                            setSourceContent('');
                            setTargetContent('');
                            setError(null);
                        }}
                        className="px-4 py-2 text-sm bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors"
                    >
                        Reset Directories
                    </button>
                </div>
            </div>

            {/* Error Display */}
            {error && (
                <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
                    <p className="text-red-800 text-sm">{error}</p>
                </div>
            )}

            {/* Loading State */}
            {isLoading && (
                <div className="p-4 text-center">
                    <Spinner />
                    <span className="ml-2 text-slate-600">Loading files...</span>
                </div>
            )}

            {/* Content Comparison */}
            {!isLoading && fileList.length > 0 && (
                <div className="flex flex-col lg:flex-row">
                    {/* Source Column */}
                    <div className="flex-1 p-4 border-r border-slate-200">
                        <div className="flex justify-between items-center mb-3">
                            <h3 className="text-lg font-semibold text-slate-800">Source</h3>
                            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded font-mono">
                                {sourceHandle?.name}
                            </span>
                        </div>
                        <div className="bg-slate-50 border border-slate-300 rounded-lg overflow-hidden">
                            <pre className="p-4 text-sm font-mono whitespace-pre-wrap max-h-[700px] overflow-y-auto text-slate-800">
                                {sourceContent}
                            </pre>
                        </div>
                    </div>

                    {/* Target Column */}
                    <div className="flex-1 p-4">
                        <div className="flex justify-between items-center mb-3">
                            <h3 className="text-lg font-semibold text-slate-800">Target</h3>
                            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded font-mono">
                                {targetHandle?.name}
                            </span>
                        </div>
                        <div className="bg-slate-50 border border-slate-300 rounded-lg overflow-hidden">
                            <pre className="p-4 text-sm font-mono whitespace-pre-wrap max-h-[700px] overflow-y-auto text-slate-800">
                                {targetContent}
                            </pre>
                        </div>
                    </div>
                </div>
            )}

            {/* No Files Found */}
            {!isLoading && fileList.length === 0 && sourceHandle && targetHandle && (
                <div className="p-8 text-center text-slate-500">
                    <svg className="mx-auto h-12 w-12 text-slate-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p>No 'page_xxxx.txt' files found in the selected directories.</p>
                </div>
            )}

            {/* Bookmarks Modal */}
            {showBookmarksModal && (
                <BookmarksModal
                    isOpen={showBookmarksModal}
                    onClose={() => setShowBookmarksModal(false)}
                    bookmarks={bookmarks}
                    onBookmarkClick={handleBookmarkClick}
                    title={selectedFolder?.selectedPDFFile ? `Bookmarks - ${selectedFolder.selectedPDFFile}` : "PDF Bookmarks"}
                />
            )}
        </div>
    );
};

export default ParagraphGenEval;