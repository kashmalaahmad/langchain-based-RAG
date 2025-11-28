import os
import time
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

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


class ChromaRetriever:
    def __init__(self, chroma_dir: str = "vector_db", embed_model: str = "models/text-embedding-004"):
        self.chroma_dir = chroma_dir
        self.embed_model = embed_model
        self.embedding_fn = GoogleGenerativeAIEmbeddings(model=embed_model)
        
        if not os.path.exists(chroma_dir):
            raise ValueError(f"Chroma database not found at {chroma_dir}. Please run ingestion first.")
        
        self.db = Chroma(
            persist_directory=chroma_dir,
            embedding_function=self.embedding_fn
        )

    def retrieve(self, query: str, k: int = 6):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                results = self.db.similarity_search_with_score(query, k=k)
                time.sleep(2)
                return results
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise e
                wait_time = 60 * retry_count
                print(f"Rate limit hit. Waiting {wait_time} seconds before retry {retry_count}/{max_retries}...")
                time.sleep(wait_time)

