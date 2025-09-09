// Share utilities for Aagam-Khoj search results

// Generate shareable URL for a specific search result
export const generateShareURL = () => {
    return window.location.origin;
};

// Format share content for different platforms
export const formatShareContent = (query, result, shareUrl) => {
    const granth = result?.metadata?.Granth || 'Unknown Source';
    const series = result?.metadata?.Series || '';
    const pageNumber = result?.page_number || '';
    const filename = result?.original_filename ? result.original_filename.split('/').pop() : '';
    const pravachankar = result?.Pravachankar || 'Unknown';
    
    // Clean content snippet - remove HTML tags and don't truncate
    const cleanContent = result?.content_snippet 
        ? result.content_snippet.replace(/<[^>]*>/g, '').trim()
        : 'Search result from Aagam-Khoj';
    
    // Build pravachan details
    let pravachanDetails = '';
    if (series) pravachanDetails += `${series}, `;
    pravachanDetails += filename;
    pravachanDetails += `, Page ${pageNumber}`;
    
    return {
        title: `Found in Aagam-Khoj: "${query}"`,
        text: `Query: ${query}\n\nExtract: "${cleanContent}"\n\nGranth: ${granth}\n\nप्रवचनकार: ${pravachankar}\n\nPravachan Details: ${pravachanDetails}\n\nSearch more at: ${shareUrl}`,
        url: shareUrl
    };
};

// Copy to clipboard function
export const copyToClipboard = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
        }
    }
    
    // Fallback for older browsers
    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        return successful;
    } catch (error) {
        console.error('Fallback copy failed:', error);
        return false;
    }
};

// Track share events for analytics
export const trackShareEvent = (method, query, resultId) => {
    // Track share usage (can be integrated with analytics)
    console.log('Share event:', { method, query, resultId });
    
    // If you have Google Analytics or other analytics
    // gtag('event', 'share', {
    //     method: method,
    //     content_type: 'search_result',
    //     item_id: resultId
    // });
};