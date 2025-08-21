import React from 'react';

const About = () => {
    return (
        <div className="max-w-4xl mx-auto p-6 bg-white">
            <h1 className="text-3xl font-bold text-gray-900 mb-6">Aagam Khoj - User Guide</h1>
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">Overview</h2>
            <p className="mb-8 text-gray-700 leading-relaxed">
                Aagam Khoj is a comprehensive digital catalog and search platform for thousands of Pravachans (spiritual discourses) delivered by Pujya Gurudev Shri Kanji Swami. The platform makes these teachings easily discoverable and accessible through advanced search capabilities.
            </p>

            <hr className="my-8 border-gray-300" />
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Core Features</h2>
            
            <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                <span className="mr-2">🔍</span>Search Capabilities
            </h3>
            
            <h4 className="text-lg font-medium text-gray-700 mb-3">Keyword Search</h4>
            <p className="mb-2 text-gray-700">Find Pravachans containing specific terms or phrases.</p>
            <ul className="mb-4 ml-6 text-gray-700 list-disc">
                <li className="mb-1">Direct keyword matching across all documents</li>
                <li className="mb-1">Example: <code className="bg-gray-100 px-2 py-1 rounded">"कुंदकुन्दाचार्य विदेह"</code></li>
            </ul>
            
            <h4 className="text-lg font-medium text-gray-700 mb-3">Semantic Search</h4>
            <p className="mb-2 text-gray-700">Discover relevant Pravachans through natural language questions.</p>
            <ul className="mb-6 ml-6 text-gray-700 list-disc">
                <li className="mb-1">AI-powered understanding of context and meaning</li>
                <li className="mb-1">Get answers to philosophical and spiritual questions</li>
                <li className="mb-1">Example: <code className="bg-gray-100 px-2 py-1 rounded">"सम्यक् एकान्त क्या है?"</code></li>
            </ul>
            
            <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                <span className="mr-2">📁</span>Document Management
            </h3>
            
            <h4 className="text-lg font-medium text-gray-700 mb-3">PDF Access</h4>
            <ul className="mb-4 ml-6 text-gray-700 list-disc">
                <li className="mb-1">View original source documents directly</li>
                <li className="mb-1">Each search result includes a PDF viewer icon</li>
                <li className="mb-1">Maintain reference to authentic sources</li>
            </ul>
            
            <h4 className="text-lg font-medium text-gray-700 mb-3">Similar Content Discovery</h4>
            <ul className="mb-6 ml-6 text-gray-700 list-disc">
                <li className="mb-1">"More like this" feature for each result</li>
                <li className="mb-1">Find related Pravachans based on content similarity</li>
                <li className="mb-1">Explore interconnected teachings</li>
            </ul>
            
            <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                <span className="mr-2">🎯</span>Search Refinement
            </h3>
            
            <h4 className="text-lg font-medium text-gray-700 mb-3">Filters</h4>
            <ul className="mb-4 ml-6 text-gray-700 list-disc">
                <li className="mb-1">Narrow searches to specific Pravachan categories</li>
                <li className="mb-1">Apply multiple filters simultaneously</li>
                <li className="mb-1">Customize search scope</li>
            </ul>
            
            <h4 className="text-lg font-medium text-gray-700 mb-3">Relevance Options</h4>
            <ul className="mb-8 ml-6 text-gray-700 list-disc">
                <li className="mb-1"><strong>Quick Search</strong> (Default): Faster results with good accuracy</li>
                <li className="mb-1"><strong>Better Relevance</strong>: Enhanced semantic search for more precise results</li>
            </ul>
            
            <hr className="my-8 border-gray-300" />
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Usage Guidelines</h2>
            
            <h3 className="text-xl font-semibold text-gray-800 mb-4">Writing Effective Search Queries</h3>
            
            <h4 className="text-lg font-medium text-gray-700 mb-3">Language Support</h4>
            
            <div className="mb-4">
                <h5 className="font-semibold text-gray-700 mb-2">Hindi (Recommended)</h5>
                <p className="mb-2 text-gray-700">Native script queries work best</p>
                <div className="mb-3">
                    <p className="mb-1 text-gray-700">Examples:</p>
                    <ul className="ml-6 text-gray-700 list-disc">
                        <li className="mb-1"><code className="bg-gray-100 px-2 py-1 rounded">"कुंदकुन्दाचार्य विदेह"</code> - Keyword search</li>
                        <li className="mb-1"><code className="bg-gray-100 px-2 py-1 rounded">"सम्यक् एकान्त क्या है?"</code> - Question-based search</li>
                        <li className="mb-1"><code className="bg-gray-100 px-2 py-1 rounded">"दृष्टि के विषय और ज्ञान के विषय में क्या फ़र्क़ है?"</code> - Complex queries</li>
                    </ul>
                </div>
            </div>
            
            <div className="mb-4">
                <h5 className="font-semibold text-gray-700 mb-2">English</h5>
                <p className="mb-2 text-gray-700">Fully supported for questions and searches</p>
                <div className="mb-3">
                    <p className="mb-1 text-gray-700">Examples:</p>
                    <ul className="ml-6 text-gray-700 list-disc">
                        <li className="mb-1"><code className="bg-gray-100 px-2 py-1 rounded">"What is Samyak Ekant?"</code></li>
                        <li className="mb-1"><code className="bg-gray-100 px-2 py-1 rounded">"When did Kundkund Acharya go to Videh Kshetra?"</code></li>
                    </ul>
                </div>
            </div>
            
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
                <p className="font-semibold text-yellow-800 mb-2">⚠️ Avoid: Hindi words written in English script</p>
                <ul className="ml-6 text-yellow-700 list-disc">
                    <li className="mb-1">❌ <code className="bg-yellow-100 px-2 py-1 rounded">"Kanji Swami kaun hai?"</code> - Will not give desired results</li>
                    <li className="mb-1">✅ Use either: <code className="bg-green-100 px-2 py-1 rounded">"कांजी स्वामी कौन हैं?"</code> or <code className="bg-green-100 px-2 py-1 rounded">"Who is Kanji Swami?"</code></li>
                </ul>
            </div>

            <hr className="my-8 border-gray-300" />
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Quick Start Guide</h2>
            
            <ol className="mb-8 ml-6 text-gray-700 list-decimal">
                <li className="mb-3">
                    <strong>Basic Search</strong>
                    <ul className="ml-6 mt-1 list-disc">
                        <li className="mb-1">Enter keywords or questions in the search bar</li>
                        <li className="mb-1">Press Enter or click Search</li>
                    </ul>
                </li>
                <li className="mb-3">
                    <strong>Apply Filters</strong>
                    <ul className="ml-6 mt-1 list-disc">
                        <li className="mb-1">Click "Filters" below the search bar</li>
                        <li className="mb-1">Select categories to narrow results</li>
                        <li className="mb-1">Choose relevance option if needed</li>
                    </ul>
                </li>
                <li className="mb-3">
                    <strong>Review Results</strong>
                    <ul className="ml-6 mt-1 list-disc">
                        <li className="mb-1">Click on any result to view details</li>
                        <li className="mb-1">Use PDF icon to see original document</li>
                        <li className="mb-1">Click "More like this" for similar content</li>
                    </ul>
                </li>
                <li className="mb-3">
                    <strong>Refine Your Search</strong>
                    <ul className="ml-6 mt-1 list-disc">
                        <li className="mb-1">Modify query based on initial results</li>
                        <li className="mb-1">Adjust filters as needed</li>
                        <li className="mb-1">Switch between quick and better relevance modes</li>
                    </ul>
                </li>
            </ol>
            
            <hr className="my-8 border-gray-300" />
            
        </div>
    );
};

export default About;