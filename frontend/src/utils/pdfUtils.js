/**
 * Helper function to recursively add page numbers to PDF bookmarks
 * @param {Array} bookmarkItems - Array of bookmark objects from PDF outline
 * @param {Object} pdfDoc - PDF.js document object
 * @returns {Array} - Array of bookmark objects with pageNumber property added
 */
export const addPageNumbersToBookmarks = async (bookmarkItems, pdfDoc) => {
    const processedItems = [];

    for (const item of bookmarkItems) {
        const processedItem = { ...item };

        // Calculate page number for this bookmark
        try {
            if (item.dest) {
                let dest = item.dest;

                // If dest is a string, get the actual destination
                if (typeof dest === 'string') {
                    dest = await pdfDoc.getDestination(dest);
                }

                if (dest && dest[0]) {
                    const pageRef = dest[0];
                    const pageIndex = await pdfDoc.getPageIndex(pageRef);
                    processedItem.pageNumber = pageIndex + 1; // PDF pages are 1-indexed
                }
            }
        } catch (err) {
            console.error(`Error calculating page number for "${item.title}":`, err);
        }

        // Recursively process nested items
        if (item.items && item.items.length > 0) {
            processedItem.items = await addPageNumbersToBookmarks(item.items, pdfDoc);
        }

        processedItems.push(processedItem);
    }

    return processedItems;
};