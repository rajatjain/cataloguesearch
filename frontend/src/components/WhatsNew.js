import React from 'react';

const WhatsNew = () => {
    // Helper function to render content with optional links
    const renderContent = (item) => {
        if (typeof item === 'string') {
            return <span className="text-slate-700">{item}</span>;
        } else if (item.link) {
            const isExternalLink = item.link.startsWith('http') || item.link.startsWith('//');
            return (
                <span className="text-slate-700">
                    {item.text}{' '}
                    <a 
                        href={item.link} 
                        target={isExternalLink ? "_blank" : "_self"}
                        rel={isExternalLink ? "noopener noreferrer" : undefined}
                        className="text-sky-600 hover:text-sky-800 underline font-medium"
                    >
                        {item.linkText || 'Learn more'}
                    </a>
                </span>
            );
        }
        return <span className="text-slate-700">{item.text}</span>;
    };

    const updates = [
        {
            date: "September 7, 2025",
            newContent: [
                "Pravachans on Padmanandi Panchvinchati 1960 Series",
                "Pravachans (compiled) on Kartikeya Anupreksha 1952 Series",
                "Total Indexed Pravachans: ~2500"
            ],
            newFeatures: [
                "Page load automatically focuses on search-box for ease of use",
                "Use \"/\" shortcut to focus on the search box"
            ]
        },
        {
            date: "August 29, 2025",
            newContent: [
                "Pravachans on Purusharth Siddhi Upay 1966 Series",
                "Pravachans on Natak Samaysaar 1971 Series",
                "Pravachans on Yogsaar 1966 Series",
                "Total Indexed Pravachans: ~2300"
            ],
            newFeatures: [
                "\"Share icon\" to share Pravachan snippets",
                "Fixing pagination issues in semantic search",
                {
                    text: "Usage Guide: Tips to install hindi/gujarati keyboard",
                    link: "/usage-guide#typing-guide",
                    linkText: "View Guide"
                },
                "Minor UI improvements"
            ]
        },
        {
            date: "August 24, 2025",
            newContent: [
                "Pravachans on Parmatma Prakash 1976-77 Series",
                "Pravachans on Samaysar Kalash Tika 1977-78 Series",
                "Total Indexed Pravachans: ~2000"
            ],
            newFeatures: [
                "\"Exclude Words\": Only show results which do not have these words",
                "Usage guide for new users",
                "Minor UI bug fixes",
            ]
        },
        {
            date: "August 17, 2025",
            newContent: [
                "Pravachans on Panchastikaya 1969-70 Series",
                "Pravachans on Asht Pahud 1973-74 Series",
                "Total Indexed Pravachans: ~1500"
            ],
            newFeatures: [
                {
                    text: "Website Launched!",
                    link: "https://www.swalakshya.me/",
                    linkText: "https://www.swalakshya.me/"
                },
                "Directly open and view the original PDF file along with the search results.",
                "\"Did you mean?\": Spell Check functionality",
                "Similar document discovery functionality", 
                "Numerous improvements in data quality",
            ]
        },
        {
            date: "August 10, 2025",
            newContent: [
                "Pravachans on Samaysar 1978-80 Series",
                "Pravachans on Pravachansar 1979-80 Series",
                "Pravachans on Niyamsar 1979-80 Series",
                "Total Indexed Pravachans: ~1000",
            ],
            newFeatures: [
                "Full lexical/keyword search",
                "BETA: Full semantic search (question/answer)",
                "\"More Like This\": Look at similar documents"
            ]
        }
    ];

    return (
        <div className="max-w-4xl mx-auto">
            <div className="text-center py-6">
                <h1 className="text-4xl font-bold text-slate-800 mb-4">What's New?</h1>
                <p className="text-lg text-slate-600 max-w-2xl mx-auto">
                    Stay updated with the latest improvements, new content, and features added to Aagam-Khoj.
                </p>
            </div>

            <div className="space-y-8">
                {updates.map((update, index) => (
                    <div key={index} className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                        {/* Header with Date */}
                        <div className="bg-sky-50 border-b border-sky-100 px-6 py-4">
                            <h2 className="text-xl font-semibold text-sky-800">{update.date}</h2>
                        </div>
                        
                        <div className="px-6 py-6">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                {/* New Content Section */}
                                <div>
                                    <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center">
                                        <svg className="w-5 h-5 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                        </svg>
                                        New Content
                                    </h3>
                                    <ul className="space-y-2">
                                        {update.newContent.map((item, itemIndex) => (
                                            <li key={itemIndex} className="flex items-start">
                                                <span className="flex-shrink-0 w-2 h-2 bg-green-500 rounded-full mt-2 mr-3"></span>
                                                {renderContent(item)}
                                            </li>
                                        ))}
                                    </ul>
                                </div>

                                {/* New Features Section */}
                                <div>
                                    <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center">
                                        <svg className="w-5 h-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                        </svg>
                                        New Features
                                    </h3>
                                    <ul className="space-y-2">
                                        {update.newFeatures.map((feature, featureIndex) => (
                                            <li key={featureIndex} className="flex items-start">
                                                <span className="flex-shrink-0 w-2 h-2 bg-blue-500 rounded-full mt-2 mr-3"></span>
                                                {renderContent(feature)}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Call to Action */}
            <div className="mt-12 text-center">
                <div className="bg-gradient-to-r from-sky-50 to-blue-50 rounded-lg p-8 border border-sky-100">
                    <h3 className="text-xl font-semibold text-slate-800 mb-3">Have suggestions for new features?</h3>
                    <p className="text-slate-600 mb-4">
                        We're always looking to improve Aagam-Khoj based on your feedback and needs.
                    </p>
                    <button 
                        onClick={() => window.location.href = '/feedback'}
                        className="bg-sky-600 text-white font-semibold py-2 px-6 rounded-md hover:bg-sky-700 transition-colors duration-200"
                    >
                        Share Your Feedback
                    </button>
                </div>
            </div>
        </div>
    );
};

export default WhatsNew;
