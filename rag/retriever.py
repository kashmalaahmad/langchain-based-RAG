import os
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader

def load_pdfs_from_dir(directory: str):
    documents = []

    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return []

    for filename in os.listdir(directory):
        if filename.lower().endswith(".pdf"):
            file_path = os.path.join(directory, filename)

            loader = PyPDFLoader(file_path)

            docs = loader.load()

            for d in docs:
                d.metadata["source"] = filename

            documents.extend(docs)

    return documents
