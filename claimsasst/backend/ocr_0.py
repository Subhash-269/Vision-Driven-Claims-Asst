from PyPDF2 import PdfReader
import os

def extract_text_pypdf2(pdf_path):
    reader = PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n" # Add newline for page separation
    return full_text

# Example usage:

policy_docs = 'PolicyDocs'
for doc in os.listdir(policy_docs):
    if doc.endswith(".pdf"):
        pdf_file = os.path.join(policy_docs, doc)
        doc_name = pdf_file.split("/")[-1].replace(".pdf", "")
        extracted_content = extract_text_pypdf2(pdf_file)
        print("Processed", doc_name)

    # To save to a text file:
    with open(f"{doc_name}.txt", "w", encoding="utf-8") as f:
        f.write(extracted_content)  