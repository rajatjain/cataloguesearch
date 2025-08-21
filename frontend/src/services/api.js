// --- API SERVICE ---
const API_BASE_URL = '/api';

export const api = {
    getMetadata: async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/metadata`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) { 
            console.error("API Error: Could not fetch metadata", error); 
            return {}; 
        }
    },
    
    search: async (requestPayload) => {
        try {
            const response = await fetch(`${API_BASE_URL}/search`, {
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(requestPayload),
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            return { ...data, results: data.results || [], vector_results: data.vector_results || [] };
        } catch (error) { 
            console.error("API Error: Could not perform search", error); 
            return { total_results: 0, results: [], total_vector_results: 0, vector_results: [] }; 
        }
    },
    
    getSimilarDocuments: async (docId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/similar-documents/${docId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            return { ...data, results: data.results || [] };
        } catch (error) { 
            console.error("API Error: Could not fetch similar documents", error); 
            return { total_results: 0, results: [] }; 
        }
    },
    
    getParagraphContext: async (chunkId) => {
        try {
            const response = await fetch(`${API_BASE_URL}/context/${chunkId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) { 
            console.error("API Error: Could not fetch context", error); 
            return null; 
        }
    },
    
    submitFeedback: async (feedbackData) => {
        try {
            const response = await fetch(`${API_BASE_URL}/feedback`, {
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(feedbackData),
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        } catch (error) { 
            console.error("API Error: Could not submit feedback", error); 
            throw error; 
        }
    }
};