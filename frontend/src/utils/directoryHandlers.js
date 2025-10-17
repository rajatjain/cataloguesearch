// --- DIRECTORY HANDLE UTILITIES ---
// Shared utilities for File System Access API operations

/**
 * Opens IndexedDB for storing directory handles
 */
export const openDirectoryHandleDB = () => {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('EvalDirectoryHandles', 1);
        
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('handles')) {
                db.createObjectStore('handles');
            }
        };
    });
};

/**
 * Gets a value from IndexedDB object store
 */
export const getFromStore = (store, key) => {
    return new Promise((resolve, reject) => {
        const request = store.get(key);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
    });
};

/**
 * Stores directory handles in IndexedDB
 */
export const storeDirectoryHandles = async (handles) => {
    try {
        console.log('[PERMISSIONS] Storing directory handles:', {
            pdf: handles.pdf?.name || 'null',
            ocr: handles.ocr?.name || 'null',
            text: handles.text?.name || 'null'
        });

        const db = await openDirectoryHandleDB();
        const transaction = db.transaction(['handles'], 'readwrite');
        const store = transaction.objectStore('handles');

        await Promise.all([
            store.put(handles.pdf, 'pdf'),
            store.put(handles.ocr, 'ocr'),
            store.put(handles.text, 'text')
        ]);

        console.log('[PERMISSIONS] ✅ Directory handles stored successfully in IndexedDB');
    } catch (err) {
        console.error('[PERMISSIONS] ❌ Error storing directory handles:', err);
    }
};

/**
 * Retrieves stored directory handles from IndexedDB
 */
export const getStoredDirectoryHandles = async () => {
    try {
        console.log('[PERMISSIONS] Attempting to retrieve stored directory handles from IndexedDB...');
        const db = await openDirectoryHandleDB();
        const transaction = db.transaction(['handles'], 'readonly');
        const store = transaction.objectStore('handles');

        const [pdf, ocr, text] = await Promise.all([
            getFromStore(store, 'pdf'),
            getFromStore(store, 'ocr'),
            getFromStore(store, 'text')
        ]);

        const result = { pdf, ocr, text };
        console.log('[PERMISSIONS] Retrieved handles from IndexedDB:', {
            pdf: pdf?.name || 'null',
            ocr: ocr?.name || 'null',
            text: text?.name || 'null',
            allPresent: !!(pdf && ocr && text)
        });

        return result;
    } catch (err) {
        console.error('[PERMISSIONS] ❌ Error reading from IndexedDB:', err);
        return { pdf: null, ocr: null, text: null };
    }
};

/**
 * Clears stored directory handles from IndexedDB
 */
export const clearStoredDirectoryHandles = async () => {
    try {
        console.log('[PERMISSIONS] ⚠️ CLEARING all stored directory handles from IndexedDB');
        console.trace('[PERMISSIONS] Clear called from:');
        const db = await openDirectoryHandleDB();
        const transaction = db.transaction(['handles'], 'readwrite');
        const store = transaction.objectStore('handles');
        await store.clear();
        console.log('[PERMISSIONS] ✅ Directory handles cleared from IndexedDB');
    } catch (err) {
        console.error('[PERMISSIONS] ❌ Error clearing stored handles:', err);
    }
};

/**
 * Validates if stored directory handles still have permissions
 */
export const validateDirectoryHandles = async (handles) => {
    try {
        console.log('[PERMISSIONS] Validating directory handle permissions...');

        // Use queryPermission() instead of requestPermission() for automatic checks
        // queryPermission() doesn't require user activation and just checks the current state
        const [pdfPermission, ocrPermission, textPermission] = await Promise.all([
            handles.pdf?.queryPermission({ mode: 'read' }),
            handles.ocr?.queryPermission({ mode: 'read' }),
            handles.text?.queryPermission({ mode: 'read' })
        ]);

        const isValid = pdfPermission === 'granted' &&
                        ocrPermission === 'granted' &&
                        textPermission === 'granted';

        console.log('[PERMISSIONS] Validation result:', {
            pdf: pdfPermission,
            ocr: ocrPermission,
            text: textPermission,
            isValid
        });

        return isValid;
    } catch (err) {
        console.error('[PERMISSIONS] ❌ Error validating directory handles:', err);
        return false;
    }
};

/**
 * Navigates to a relative path within a base directory handle
 */
export const navigateToPath = async (baseHandle, relativePath) => {
    if (!relativePath) return baseHandle;
    
    const pathParts = relativePath.split('/').filter(part => part.length > 0);
    let currentHandle = baseHandle;
    
    for (const part of pathParts) {
        try {
            currentHandle = await currentHandle.getDirectoryHandle(part);
        } catch (err) {
            console.error(`Failed to navigate to path part: ${part}`, err);
            return null;
        }
    }
    
    return currentHandle;
};

/**
 * Loads files matching a pattern from a directory
 */
export const loadFilesFromDirectory = async (directoryHandle, fileRegex = /^page_\d{4}\.(txt|json)$/) => {
    const fileSet = new Set();

    for await (const entry of directoryHandle.values()) {
        if (entry.kind === 'file' && fileRegex.test(entry.name)) {
            fileSet.add(entry.name);
        }
    }

    return Array.from(fileSet).sort();
};

/**
 * Reads content from a file in a directory
 */
export const readFileContent = async (dirHandle, fileName) => {
    try {
        const fileHandle = await dirHandle.getFileHandle(fileName);
        const file = await fileHandle.getFile();
        return await file.text();
    } catch (e) {
        console.error(`Error reading ${fileName}:`, e);
        return `--- File not found: ${fileName} ---`;
    }
};