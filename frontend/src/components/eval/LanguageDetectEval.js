import React, { useState } from 'react';

const LanguageDetectEval = () => {
    const [inputText, setInputText] = useState('');
    const [classificationMethod, setClassificationMethod] = useState('rule_based');
    const [results, setResults] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const classifyText = async () => {
        if (!inputText.trim()) {
            setError('Please enter some text to classify');
            return;
        }

        setIsLoading(true);
        setError(null);
        setResults([]);

        try {
            // Split text into lines
            const lines = inputText.split('\n').filter(line => line.trim() !== '');

            // Use batch API for much faster processing
            const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api';

            const response = await fetch(`${API_BASE_URL}/eval/language/classify/batch`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    texts: lines,
                    method: classificationMethod
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const batchResult = await response.json();

            // Format results with line numbers
            const lineResults = batchResult.results.map((result, i) => ({
                lineNumber: i + 1,
                text: result.text,
                language: result.language,
                confidence: result.confidence,
                method: result.method,
                details: result.details,
                error: result.language === 'error' ? result.details?.error : null
            }));

            setResults(lineResults);
        } catch (err) {
            setError(`Classification failed: ${err.message}`);
        } finally {
            setIsLoading(false);
        }
    };

    const getLanguageColor = (language) => {
        switch (language) {
            case 'sanskrit':
                return 'bg-purple-100 text-purple-800 border-purple-300';
            case 'hindi':
                return 'bg-blue-100 text-blue-800 border-blue-300';
            case 'error':
                return 'bg-red-100 text-red-800 border-red-300';
            default:
                return 'bg-slate-100 text-slate-800 border-slate-300';
        }
    };

    const getConfidenceColor = (confidence) => {
        if (confidence >= 0.8) return 'text-green-600 font-semibold';
        if (confidence >= 0.6) return 'text-amber-600 font-medium';
        return 'text-red-600 font-medium';
    };

    const clearAll = () => {
        setInputText('');
        setResults([]);
        setError(null);
    };

    const loadSampleText = () => {
        const sampleText = `श्री भगवान् उवाच
यह एक हिंदी वाक्य है।
धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः
मैं आज बाजार जा रहा हूं।
अथातो ब्रह्मजिज्ञासा
क्या आप मेरी मदद कर सकते हैं?`;
        setInputText(sampleText);
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
                <h2 className="text-2xl font-bold text-slate-800 mb-2">Language Detection Evaluation</h2>
                <p className="text-slate-600">
                    Classify Devanagari text as Sanskrit or Hindi. Enter multiple lines of text, and each line will be classified independently.
                </p>
            </div>

            {/* Input Section */}
            <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
                <div className="space-y-4">
                    {/* Classification Method Selector */}
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                            Classification Method
                        </label>
                        <div className="flex flex-wrap gap-4">
                            <label className="flex items-center">
                                <input
                                    type="radio"
                                    value="rule_based"
                                    checked={classificationMethod === 'rule_based'}
                                    onChange={(e) => setClassificationMethod(e.target.value)}
                                    className="mr-2"
                                />
                                <span className="text-sm text-slate-700">
                                    Rule-based <span className="text-slate-500">(Heuristics)</span>
                                </span>
                            </label>
                            <label className="flex items-center">
                                <input
                                    type="radio"
                                    value="indicbert"
                                    checked={classificationMethod === 'indicbert'}
                                    onChange={(e) => setClassificationMethod(e.target.value)}
                                    className="mr-2"
                                />
                                <span className="text-sm text-slate-700">
                                    IndicBERT <span className="text-slate-500">(Transformer)</span>
                                </span>
                            </label>
                            <label className="flex items-center">
                                <input
                                    type="radio"
                                    value="fasttext"
                                    checked={classificationMethod === 'fasttext'}
                                    onChange={(e) => setClassificationMethod(e.target.value)}
                                    className="mr-2"
                                />
                                <span className="text-sm text-slate-700">
                                    FastText <span className="text-slate-500">(ML-based)</span>
                                </span>
                            </label>
                            <label className="flex items-center">
                                <input
                                    type="radio"
                                    value="hybrid"
                                    checked={classificationMethod === 'hybrid'}
                                    onChange={(e) => setClassificationMethod(e.target.value)}
                                    className="mr-2"
                                />
                                <span className="text-sm text-slate-700">
                                    Hybrid <span className="text-slate-500">(Combined)</span>
                                </span>
                            </label>
                        </div>
                    </div>

                    {/* Text Input */}
                    <div>
                        <div className="flex justify-between items-center mb-2">
                            <label className="block text-sm font-medium text-slate-700">
                                Input Text (one line per entry)
                            </label>
                            <button
                                onClick={loadSampleText}
                                className="text-sm text-sky-600 hover:text-sky-700 font-medium"
                            >
                                Load Sample Text
                            </button>
                        </div>
                        <textarea
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            rows={10}
                            className="w-full p-3 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 font-mono text-sm"
                            placeholder="Enter Devanagari text here, one line per entry..."
                        />
                        <p className="text-sm text-slate-500 mt-1">
                            {inputText.split('\n').filter(line => line.trim() !== '').length} lines
                        </p>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex space-x-3">
                        <button
                            onClick={classifyText}
                            disabled={isLoading || !inputText.trim()}
                            className={`px-6 py-2 font-semibold rounded-md transition-colors ${
                                isLoading || !inputText.trim()
                                    ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                                    : 'bg-sky-600 text-white hover:bg-sky-700'
                            }`}
                        >
                            {isLoading ? (
                                <span className="flex items-center">
                                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Classifying...
                                </span>
                            ) : (
                                'Classify Text'
                            )}
                        </button>
                        <button
                            onClick={clearAll}
                            disabled={isLoading}
                            className="px-6 py-2 font-semibold text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 transition-colors"
                        >
                            Clear All
                        </button>
                    </div>

                    {/* Error Display */}
                    {error && (
                        <div className="bg-red-50 border border-red-200 rounded-md p-4">
                            <div className="flex items-start">
                                <svg className="w-5 h-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <div>
                                    <p className="text-red-800 font-medium text-sm">Error</p>
                                    <p className="text-red-700 text-sm mt-1">{error}</p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Results Section */}
            {results.length > 0 && (
                <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-6">
                    <h3 className="text-lg font-semibold text-slate-800 mb-4">
                        Classification Results ({results.length} lines)
                    </h3>

                    {/* Summary */}
                    <div className="mb-4 p-4 bg-slate-50 rounded-md">
                        <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                                <span className="font-medium text-slate-700">Sanskrit: </span>
                                <span className="text-purple-600 font-semibold">
                                    {results.filter(r => r.language === 'sanskrit').length}
                                </span>
                            </div>
                            <div>
                                <span className="font-medium text-slate-700">Hindi: </span>
                                <span className="text-blue-600 font-semibold">
                                    {results.filter(r => r.language === 'hindi').length}
                                </span>
                            </div>
                            <div>
                                <span className="font-medium text-slate-700">Errors: </span>
                                <span className="text-red-600 font-semibold">
                                    {results.filter(r => r.language === 'error').length}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Results Table */}
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200">
                            <thead className="bg-slate-50">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider w-16">
                                        Line
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">
                                        Text
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider w-32">
                                        Language
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider w-32">
                                        Confidence
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-slate-200">
                                {results.map((result, idx) => (
                                    <tr key={idx} className="hover:bg-slate-50">
                                        <td className="px-4 py-3 text-sm text-slate-500">
                                            {result.lineNumber}
                                        </td>
                                        <td className="px-4 py-3 text-sm text-slate-800 font-mono">
                                            {result.text}
                                        </td>
                                        <td className="px-4 py-3">
                                            {result.error ? (
                                                <span className="text-xs text-red-600">{result.error}</span>
                                            ) : (
                                                <span className={`inline-flex px-3 py-1 text-xs font-medium rounded-full border ${getLanguageColor(result.language)}`}>
                                                    {result.language.charAt(0).toUpperCase() + result.language.slice(1)}
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">
                                            {!result.error && (
                                                <span className={`text-sm ${getConfidenceColor(result.confidence)}`}>
                                                    {(result.confidence * 100).toFixed(1)}%
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};

export default LanguageDetectEval;