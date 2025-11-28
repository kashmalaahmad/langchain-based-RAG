import os
import time
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from ingestion.loaders import load_pdfs_from_dir

load_dotenv(override=True)

CHROMA_PATH = os.getenv("CHROMA_PATH", "vector_db/chroma")
DATA_PATH = os.getenv("DATA_PATH", "data/pdfs")
EMBED_MODEL = os.getenv("EMBED_MODEL", "models/text-embedding-004")

def split_documents(documents: list[Document], chunk_size: int = 800, chunk_overlap: int = 200):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    for c in chunks:
        meta = c.metadata or {}
        if "source" not in meta and "source" in c.metadata:
            meta["source"] = c.metadata["source"]
        c.metadata = meta
    return chunks

def add_chunks_in_batches(db, chunks, batch_size=1):
    """Add chunks to database with retry logic for 504 errors."""
    total_chunks = len(chunks)
    print(f"Total chunks to process: {total_chunks}")
    
    for i in range(0, total_chunks, batch_size):
        batch = chunks[i : i + batch_size]
        current_batch_num = i // batch_size + 1
        total_batches = (total_chunks + batch_size - 1) // batch_size
        
        print(f"Processing batch {current_batch_num}/{total_batches} ({len(batch)} chunks)...")
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                db.add_documents(batch)
                print("  - Success. Sleeping for 5 seconds...")
                time.sleep(5) 
                break
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                
                if "504" in error_msg or "Deadline" in error_msg:
                    wait_time = 30 * retry_count  # 30s, 60s, 90s
                    print(f"  - 504 Timeout error (attempt {retry_count}/{max_retries})")
                    print(f"  - Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"  - Error: {error_msg}")
                    print(f"  - Retry {retry_count}/{max_retries} in 60 seconds...")
                    time.sleep(60)
        
        if retry_count >= max_retries:
            print(f"  - Failed after {max_retries} retries. Skipping batch.")

def get_or_create_chroma(chunks, persist_directory=CHROMA_PATH, embedding_model=EMBED_MODEL):
    embedding_fn = GoogleGenerativeAIEmbeddings(model=embedding_model)

    if os.path.exists(persist_directory):
        print(f"Loading existing Chroma DB at: {persist_directory}")
        db = Chroma(persist_directory=persist_directory, embedding_function=embedding_fn)
        
        if chunks:
            print(f"Adding {len(chunks)} new chunks to existing DB...")
            add_chunks_in_batches(db, chunks, batch_size=1)
            
        return db

    print("Creating NEW Chroma DB...")
    db = Chroma(persist_directory=persist_directory, embedding_function=embedding_fn)
    add_chunks_in_batches(db, chunks, batch_size=1)
    
    try:
        db.persist()
    except:
        pass
        
    print(f"Saved chunks to new Chroma at {persist_directory}")
    return db

def main():
    docs = load_pdfs_from_dir(DATA_PATH)
    if not docs:
        print(f"No PDFs found in {DATA_PATH}.")
        return
    
    chunks = split_documents(docs, chunk_size=800, chunk_overlap=200)
    get_or_create_chroma(chunks)

if __name__ == "__main__":
    main()