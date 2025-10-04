// Share utilities for Aagam-Khoj search results

// Generate shareable URL for a specific search result
export const generateShareURL = () => {
    return window.location.origin;
};

// Format Granth share content
export const formatGranthShareContent = (query, result, shareUrl) => {
    const cleanContent = result?.content_snippet
        ? result.content_snippet.replace(/<[^>]*>/g, '').trim()
        : 'Search result from Aagam-Khoj';

    const granthName = result?.original_filename ? result.original_filename.split('/').pop().replace('.md', '') : 'Unknown Granth';
    const author = result?.metadata?.author || 'Unknown Author';
    const adhikar = result?.metadata?.adhikar || '';

    // Determine if it's verse or prose
    let locationInfo = '';
    if (result?.metadata?.verse_seq_num !== undefined) {
        const verseType = result?.metadata?.verse_type || 'Verse';
        const verseStart = result?.metadata?.verse_type_start_num;
        const verseEnd = result?.metadata?.verse_type_end_num;
        const verseNum = verseStart === verseEnd ? verseStart : `${verseStart}-${verseEnd}`;
        locationInfo = adhikar ? `${adhikar} › ${verseType} ${verseNum}` : `${verseType} ${verseNum}`;
    } else if (result?.metadata?.prose_seq_num !== undefined) {
        const proseHeading = result?.metadata?.prose_heading || 'Prose Section';
        locationInfo = adhikar ? `${adhikar} › ${proseHeading}` : proseHeading;
    }

    return {
        title: `Found in Aagam-Khoj: "${query}"`,
        text: `Query: ${query}\n\nExtract: "${cleanContent}"\n\nGranth: ${granthName}\n\nAuthor: ${author}\n\nLocation: ${locationInfo}\n\nSearch more at: ${shareUrl}`,
        url: shareUrl,
        isGranth: true,
        granthName,
        author,
        locationInfo
    };
};

// Format Pravachan share content
export const formatPravachanShareContent = (query, result, shareUrl, language = 'hindi') => {
    const cleanContent = result?.content_snippet
        ? result.content_snippet.replace(/<[^>]*>/g, '').trim()
        : 'Search result from Aagam-Khoj';

    const granth = result?.metadata?.Granth || 'Unknown Source';
    const series = result?.metadata?.Series || '';
    const pageNumber = result?.page_number || '';
    const filename = result?.original_filename ? result.original_filename.split('/').pop() : '';
    const pravachankar = result?.Pravachankar || 'Unknown';

    // Build pravachan details
    let pravachanDetails = '';
    if (series) pravachanDetails += `${series}, `;
    pravachanDetails += filename;
    pravachanDetails += `, Page ${pageNumber}`;

    // Language-specific labels
    const pravachankarLabel = language === 'gujarati' ? 'પ્રવચનકાર' : 'प्रवचनकार';

    return {
        title: `Found in Aagam-Khoj: "${query}"`,
        text: `Query: ${query}\n\nExtract: "${cleanContent}"\n\nGranth: ${granth}\n\n${pravachankarLabel}: ${pravachankar}\n\nPravachan Details: ${pravachanDetails}\n\nSearch more at: ${shareUrl}`,
        url: shareUrl,
        isGranth: false,
        granth,
        pravachankar,
        pravachanDetails,
        pravachankarLabel
    };
};

// Main dispatcher function - determines result type and calls appropriate formatter
export const formatShareContent = (query, result, shareUrl, language = 'hindi') => {
    const isGranthResult = result?.metadata?.verse_seq_num !== undefined || result?.metadata?.prose_seq_num !== undefined;

    if (isGranthResult) {
        return formatGranthShareContent(query, result, shareUrl);
    } else {
        return formatPravachanShareContent(query, result, shareUrl, language);
    }
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