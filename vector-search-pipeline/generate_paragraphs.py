import os
import re

from backend.utils import json_dumps


def get_paragraphs(files_path):
    # get all the '.txt' files in the directory
    text_files = [f for f in os.listdir(files_path) if f.endswith('.txt')]
    text_files = sorted(text_files)

    # pass 1: read text of all files in utf-8 format, split by '---'
    paragraphs = []
    for file in text_files:
        print(f"file {file}")
        file_path = os.path.join(files_path, file)
        raw_text = ""
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
        if raw_text:
            # split by '---' and strip whitespace
            file_paragraphs = [p.strip() for p in raw_text.split('---') if p.strip()]
            for para in file_paragraphs:
                para = normalize_hindi_text(para)
                if para:  # ensure non-empty paragraphs
                    paragraphs.append(para)
    for para in paragraphs:
        print(para + "\n\n")
    print("\n\n#########\n\n")
    return combine_paragraphs(paragraphs)


def combine_paragraphs(paragraphs):
    """Conditions:
        - for every paragraph, check if it ends with a punctuation mark
        - if it does, do nothing
        - if it does not, combine it with the next paragraph
        - if next para starts with "श्रोता:" then do not combine
        - if current para starts with "श्रोता:" and next with "पूज्य गुरुदेवश्री:" then combine
        - final pass: if any para contains "(श्रोता: " then split the rest of it into two paragraphs
    """
    combined_paragraphs = []
    i = 0
    while i < len(paragraphs):
        para = paragraphs[i].strip()
        print(para + "\n\n")

        # para starting with "श्रोता:" or "मुमुक्षु:" should always be treated as a separate paragraph
        if para.startswith(("श्रोता:", "मुमुक्षु:")):
            if i + 1 < len(paragraphs):
                next_para = paragraphs[i + 1].strip()
                if next_para.startswith("पूज्य गुरुदेवश्री:"):
                    print("para starts with मुमुक्षु/श्रोता, next starts with पूज्य गुरुदेवश्री, combining")
                    combined_paragraphs.append(para + "\n" + next_para)
                    i += 2
                else:
                    print("para starts with मुमुक्षु/श्रोता, next does not start with पूज्य गुरुदेवश्री, keeping separate")
                    combined_paragraphs.append(para)
                    i += 1
            else:
                print("para starts with मुमुक्षु/श्रोता, no next para, keeping separate")
                combined_paragraphs.append(para)
                i += 1
            print("------")
            continue

        # Check if the paragraph ends with a punctuation mark
        if para.endswith(('।', '?', '!', ':', ';', ')', ']', '}')):
            print("current para ends with punctuation, keeping separate")
            combined_paragraphs.append(para)
            i += 1
        else:
            j = i + 1
            while j < len(paragraphs):
                next_para = paragraphs[j].strip()
                if next_para.startswith(("श्रोता:", "मुमुक्षु:")):
                    print("next para starts with श्रोता/mumukshu, keeping separate")
                    break
                elif next_para.endswith(('।', '?', '!', ':', ';', ')', ']', '}')):
                    # next para ends with punctuation, combine with current
                    para += " " + next_para
                    print("next para ends with punctuation, combining")
                    j += 1
                    break
                else:
                    # next para does not end with punctuation, keep combining
                    para += " " + next_para
                    print("next para does not end with punctuation, combining")
                    j += 1

            i = j
            combined_paragraphs.append(para)

        print("------")

    # Final pass to split any paragraph containing "(श्रोता: " or "(मुमुक्षु: "
    final_paragraphs = []
    for para in combined_paragraphs:
        current_para = para
        for prefix in ["(श्रोता: ", "(मुमुक्षु: "]:
            if prefix in current_para:
                # Split only on the first occurrence
                parts = current_para.split(prefix, 1)
                # The part before the prefix
                if parts[0].strip():
                    final_paragraphs.append(parts[0].strip())
                # The part from the prefix onwards
                current_para = prefix + parts[1].strip()
                break
        final_paragraphs.append(current_para.strip())

    return final_paragraphs

def normalize_hindi_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    #1. Join multiple lines into a single line with spaces
    #   BUT do not join lines that start with "श्रोता:" or "पूज्य गुरुदेवश्री:" or "मुमुक्षु:"
    cleaned_text = re.sub(r'\n(?!श्रोता:|पूज्य गुरुदेवश्री:|मुमुक्षु:)', ' ', text)

    # 2. Normalize common OCR misclassifications for the purn viram (।)
    # The purn viram is often misread as |, I, l, or 1.
    purn_viram_errors = ['|', 'I', 'l', '1']
    for error_char in purn_viram_errors:
        cleaned_text = cleaned_text.replace(error_char, '।')

    # 3. Remove whitespace before closing punctuation marks.
    # This finds a space before a closing punctuation mark and removes the space.
    closing_punctuation = r'[।,?!:;)\]}\'"]'
    cleaned_text = re.sub(r'\s+(' + closing_punctuation + r')', r'\1', cleaned_text)

    # 5. Normalize spacing around ellipses (two or more dots).
    # This removes any space before an ellipsis.
    cleaned_text = re.sub(r'\s+(\.{2,})', r'\1', cleaned_text)

    # 4. Remove whitespace after opening punctuation marks.
    # This finds an opening punctuation mark followed by a space and removes the space.
    opening_punctuation = r'[(\[{\'"]'
    cleaned_text = re.sub(r'(' + opening_punctuation + r')\s+', r'\1', cleaned_text)

    # 5. Clean up any potential multiple spaces that might have been created
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    cleaned_text = cleaned_text.replace("गुरुदेव श्री", "गुरुदेवश्री")

    return cleaned_text

if __name__ == "__main__":
    path = "/Users/r0j08wt/cataloguesearch/documentai_output/SS01"
    paras = get_paragraphs(path)

    output_file = path + ".txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        for para in paras:
            f.write(para + "\n---\n")