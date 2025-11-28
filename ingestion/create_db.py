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

def add_chunks_in_batches(db, chunks, batch_size=3):
    total_chunks = len(chunks)
    print(f"Total chunks to process: {total_chunks}")
    
    for i in range(0, total_chunks, batch_size):
        batch = chunks[i : i + batch_size]
        current_batch_num = i // batch_size + 1
        total_batches = (total_chunks + batch_size - 1) // batch_size
        
        print(f"Processing batch {current_batch_num}/{total_batches} ({len(batch)} chunks)...")
        
        try:
            db.add_documents(batch)
            print("  - Success. Sleeping for 10 seconds...")
            time.sleep(10) 
        except Exception as e:
            print(f"  - Error in batch: {e}")
            print("  - Waiting 60 seconds before retrying this batch...")
            time.sleep(60)
            try:
                db.add_documents(batch)
                print("  - Retry successful.")
            except Exception as e2:
                print(f"  - Retry failed: {e2}. Skipping this batch.")

def get_or_create_chroma(chunks, persist_directory=CHROMA_PATH, embedding_model=EMBED_MODEL):
    embedding_fn = GoogleGenerativeAIEmbeddings(model=embedding_model)

    if os.path.exists(persist_directory):
        print(f"Loading existing Chroma DB at: {persist_directory}")
        db = Chroma(persist_directory=persist_directory, embedding_function=embedding_fn)
        
        if chunks:
            print(f"Adding {len(chunks)} new chunks to existing DB...")
            add_chunks_in_batches(db, chunks, batch_size=3)
            
        return db

    print("Creating NEW Chroma DB...")
    db = Chroma(persist_directory=persist_directory, embedding_function=embedding_fn)
    add_chunks_in_batches(db, chunks, batch_size=3)
    
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