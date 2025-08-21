import React from 'react';

const About = () => {
    return (
        <div className="max-w-[1080px] mx-auto p-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-6">Aagam Khoj</h1>
            
            <p className="mb-8 text-gray-700 leading-relaxed">
                Aagam Khoj is an AI-powered search platform for thousands of spiritual discourses (Pravachans) delivered by Pujya Gurudev Shri Kanji Swami. It enables users to ask Tattva-related questions in Hindi, Gujarati, or English and receive answers directly from Gurudev's Pravachans.
            </p>
            
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">Background</h2>
            <p className="mb-4 text-gray-700 leading-relaxed">
                Gurudev Shri Kanji Swami delivered tens of thousands of Pravachans throughout his lifetime, with over 9,500 publicly available today on vitragvani.com. Many spiritual seekers (Mumukshus) begin their day by listening to them. Beyond the original scriptures by our Acharyas, Muniraaj, and Gyaani Vidvaan, his Pravachans are a unique source that comprehensively discuss the core spiritual concepts of Jain Philosophy (द्रव्यानुयोग / आध्यात्म).
            </p>
            
            <p className="mb-4 text-gray-700 leading-relaxed">
                His Pravachans are delivered in an accessible language and delve into fundamental topics of Jain Spirituality, such as:
            </p>
            <ul className="mb-4 ml-6 text-gray-700 list-disc">
                <li className="mb-1">Dravya-Gun-Paryay</li>
                <li className="mb-1">Nischay - Vyavhar</li>
                <li className="mb-1">Nimitt - Upadan</li>
                <li className="mb-1">Krambaddh Paryay</li>
                <li className="mb-1">Way to attain self-experience (आत्मानुभूति)</li>
            </ul>
            
            <p className="mb-8 text-gray-700 leading-relaxed">
                The importance of these Pravachans is underscored by the fact that most have been transcribed word-for-word into PDFs in both Gujarati and Hindi. This facilitates understanding for spiritual seekers (मुमुक्षु) who listen to the audio Pravachans. Together with the audio files, these Pravachan Scriptures (प्रवचन शास्त्र) are a vital source of spiritual knowledge.
            </p>
            
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Why Aagam Khoj?</h2>
            <p className="mb-4 text-gray-700 leading-relaxed">
                Aagam Khoj was developed to help spiritual seekers (मुमुक्षु) easily navigate and search through Gurudevshri's vast collection of Pravachans, aiding their spiritual study (स्वाध्याय). It is designed for spiritual seekers, researchers, and Jain Scholars (विद्वान) alike.
            </p>
            
            <ul className="mb-8 ml-6 text-gray-700 list-disc">
                <li className="mb-4">
                    <strong>Spiritual Seekers:</strong> This portal allows spiritual seekers to find answers to common questions by posing them in Hindi, English, or Gujarati. Aagam Khoj uses AI to provide relevant answers directly from Gurudev's Pravachans. For instance, a user can ask, <strong>"दृष्टि के विषय और ज्ञान के विषय में क्या अन्तर है?"</strong> and Aagam Khoj will provide references from Gurudev's entire catalog that address this question. Users can also search using specific keywords, such as <strong>"महात्मा गाँधी"</strong> to find all references where Gurudev mentioned Mahatma Gandhi.
                </li>
                <li className="mb-4">
                    <strong>Jain Scholars and Researchers:</strong> Gurudev's words are considered a definitive authority on Jain Spirituality. Jain Scholars and researchers frequently reference Gurudev's Pravachans to support their arguments. They also study his Pravachan Shastra for research, to learn about events in Gurudev's life, or to understand the examples he used to explain concepts.
                </li>
            </ul>
            
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">How Does Aagam Khoj Work?</h2>
            <p className="mb-4 text-gray-700 leading-relaxed">
                Aagam Khoj employs OCR technology to convert all PDF files into text files. This text is then indexed into a search-engine system (called OpenSearch). When a user enters a query, Aagam Khoj performs two operations:
            </p>
            
            <ul className="mb-8 ml-6 text-gray-700 list-disc">
                <li className="mb-2"><strong>Keyword Search:</strong> Matches all references containing the input keywords.</li>
                <li className="mb-2"><strong>Semantic Search:</strong> Uses AI to find all relevant references that semantically match the answer to the input query.</li>
            </ul>
            
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Why Use Artificial Intelligence?</h2>
            <p className="mb-4 text-gray-700 leading-relaxed">
                A crucial question arises: Should artificial technology be used with such important content? Gurudev's Pravachans are akin to our Teerthankar's Vaani—how can AI be used to interpret their words?
            </p>
            <p className="mb-8 text-gray-700 leading-relaxed">
                The short answer is that AI is not used to interpret Gurudev's words or his intention. Instead, AI serves merely as a tool to identify references that <em>possibly</em> match the input questions, providing direct references from Gurudev's Pravachans. Aagam Khoj does not generate answers; it provides word-for-word references from Gurudev's Pravachans themselves.
            </p>
            
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">User Guide</h2>
            <p className="mb-6 text-gray-700 leading-relaxed">
                Users begin by entering their question or keywords in the search bar and clicking "Search." Aagam Khoj then provides relevant answers. Users should keep the following tips in mind for more effective searches:
            </p>
            
            <h3 className="text-xl font-semibold text-gray-800 mb-4">Tips for Effective Searches</h3>
            <ul className="mb-6 ml-6 text-gray-700 list-disc">
                <li className="mb-2">Write questions in the native language (Hindi or Gujarati).</li>
                <li className="mb-2">
                    When asking a question or searching for a phrase, add a punctuation mark like "?" or "।".
                    <ul className="ml-6 mt-1 list-disc">
                        <li className="mb-1">✅ "कुन्दकुन्दाचार्य विदेह क्षेत्र कब गए थे?"</li>
                        <li className="mb-1">❌ "कुन्दकुन्दाचार्य विदेह क्षेत्र कब गए थे"</li>
                    </ul>
                </li>
                <li className="mb-2">
                    If using English script, type the question in English rather than Hinglish.
                    <ul className="ml-6 mt-1 list-disc">
                        <li className="mb-1">✅ "When did Kundkundacharya write Samaysar?"</li>
                        <li className="mb-1">❌ "Kundkundacharya ne Samaysar kab likha?"</li>
                    </ul>
                </li>
                <li className="mb-2">Use "Filters" to narrow your search by a specific Granth, Anuyog, or Year.</li>
            </ul>
            
            <h3 className="text-xl font-semibold text-gray-800 mb-4">Interacting with Search Results</h3>
            <ul className="mb-8 ml-6 text-gray-700 list-disc">
                <li className="mb-2">Each search result includes a "View PDF" icon, which directly opens the original Pravachan Shastra at the correct page number.</li>
                <li className="mb-2">Click "Expand" to view the text surrounding the search result.</li>
                <li className="mb-2">Click "More like this" to find documents similar in intent to a particular search result.</li>
                <li className="mb-2">
                    For AI-powered (Semantic Search) results, two options are available:
                    <ul className="ml-6 mt-1 list-disc">
                        <li className="mb-1">Faster speed, but lesser relevance</li>
                        <li className="mb-1">Better relevance, but slower speed</li>
                        <li className="mb-1">Choose the option that best suits your needs.</li>
                    </ul>
                </li>
            </ul>
            
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Feedback</h2>
            <p className="mb-8 text-gray-700 leading-relaxed">
                For any issues, bugs, questions, feedback, or suggestions, please use the "Feedback" link.
            </p>
            
            
            <h2 className="text-2xl font-semibold text-gray-800 mb-6">Swa Lakshya (स्व-लक्ष्य)</h2>
            <p className="mb-4 text-gray-700 leading-relaxed">
                The sole purpose of this portal is to assist spiritual seekers (मुमुक्षु) in better understanding Jain Tattva. The author sincerely apologizes for any mistakes or shortcomings in this effort and will strive their best to correct them.
            </p>
            <p className="mb-4 text-gray-700 leading-relaxed">
                May all souls understand the true nature of their soul, achieve completeness within themselves, and attain Moksha.
            </p>
            <p className="text-gray-700 font-semibold">
                Jai Jinendra 🙏
            </p>
        </div>
    );
};

export default About;