import React from 'react';

const VerseDetails = ({ verse }) => {
    if (!verse) return null;

    return (
        <div className="border border-sky-200 rounded-lg p-4 bg-sky-50">
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <div className="flex flex-col">
                        <h4 className="font-semibold text-slate-800">
                            {verse.type} {verse.type_start_num}{verse.type_end_num !== verse.type_start_num && `-${verse.type_end_num}`}
                        </h4>
                        {verse.adhikar && (
                            <span className="text-sm text-purple-600 font-medium">
                                {verse.adhikar}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-xs bg-sky-100 text-sky-700 px-2 py-1 rounded font-medium">
                            #{verse.seq_num}
                        </span>
                        {verse.page_num && (
                            <span className="text-sm text-slate-500">
                                Page {verse.page_num}
                            </span>
                        )}
                    </div>
                </div>

                <div className="text-slate-700">
                    <strong>Original:</strong> {verse.verse}
                </div>

                {verse.translation && (
                    <div className="text-slate-700">
                        <strong>Translation:</strong> {verse.translation}
                    </div>
                )}

                {verse.meaning && (
                    <div className="text-slate-700">
                        <strong>Meaning:</strong> {verse.meaning}
                    </div>
                )}

                {verse.teeka && verse.teeka.length > 0 && (
                    <div className="text-slate-700">
                        <strong>Teeka:</strong>
                        <div className="mt-1 space-y-2">
                            {verse.teeka.map((teekaItem, index) => (
                                <div key={index} className="pl-2 border-l-2 border-slate-300">
                                    {teekaItem}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {verse.bhavarth && verse.bhavarth.length > 0 && (
                    <div className="text-slate-700">
                        <strong>Bhavarth:</strong>
                        <div className="mt-1 space-y-2">
                            {verse.bhavarth.map((bhavarthItem, index) => (
                                <div key={index} className="pl-2 border-l-2 border-slate-300">
                                    {bhavarthItem}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default VerseDetails;