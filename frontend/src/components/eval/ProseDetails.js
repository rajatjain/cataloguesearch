import React from 'react';

const ProseDetails = ({ prose }) => {
    if (!prose) return null;

    return (
        <div className="border border-emerald-200 rounded-lg p-4 bg-emerald-50">
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <div className="flex flex-col flex-1">
                        <h4 className="font-semibold text-slate-800">
                            {prose.heading}
                        </h4>
                        {prose.adhikar && (
                            <span className="text-sm text-purple-600 font-medium">
                                {prose.adhikar}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-1 rounded font-medium">
                            #{prose.seq_num}
                        </span>
                        {prose.page_num && (
                            <span className="text-sm text-slate-500">
                                Page {prose.page_num}
                            </span>
                        )}
                    </div>
                </div>

                {/* Main Content Paragraphs */}
                {prose.content && prose.content.length > 0 && (
                    <div className="space-y-2">
                        {prose.content.map((para, index) => (
                            <div key={index} className="text-slate-700 leading-relaxed">
                                {para}
                            </div>
                        ))}
                    </div>
                )}

                {/* Subsections */}
                {prose.subsections && prose.subsections.length > 0 && (
                    <div className="mt-4 space-y-4">
                        <div className="text-sm font-medium text-slate-700 border-t border-emerald-200 pt-3">
                            Subsections:
                        </div>
                        {prose.subsections.map((subsection, subIndex) => (
                            <div key={subIndex} className="pl-4 border-l-2 border-emerald-300">
                                <div className="flex items-center justify-between mb-2">
                                    <h5 className="font-medium text-slate-800 text-sm">
                                        {subsection.heading}
                                    </h5>
                                    <span className="text-xs bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded">
                                        #{subsection.seq_num}
                                    </span>
                                </div>
                                <div className="space-y-2">
                                    {subsection.content.map((para, paraIndex) => (
                                        <div key={paraIndex} className="text-sm text-slate-700 leading-relaxed">
                                            {para}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ProseDetails;