import streamlit as st
import os
import tempfile
import shutil
from dotenv import load_dotenv
from engine.utils import load_rules, save_results_csv, save_results_markdown, save_raw_json
from rag.rag_checker import RAGComplianceChecker
from ingestion.create_db import main as ingest_pdfs, split_documents, add_chunks_in_batches
from ingestion.loaders import load_pdfs_from_dir
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import json

load_dotenv()

st.set_page_config(page_title="RAG Compliance Checker", layout="wide")

st.markdown("""
# RAG-Based Compliance Checking System

This application uses Retrieval-Augmented Generation (RAG) to automatically check 
compliance rules against your documents. Powered by Gemini AI and Chroma vector database.
""")

# ========== CACHED FUNCTIONS FOR PERFORMANCE ==========

@st.cache_resource(show_spinner=False)
def initialize_checker():
    """
    Initialize RAG compliance checker (cached once).
    This function runs ONLY ONCE and the result is reused.
    """
    try:
        chroma_dir = os.getenv("CHROMA_PATH", "vector_db")
        checker = RAGComplianceChecker(chroma_dir=chroma_dir)
        return checker
    except Exception as e:
        st.error(f"Error initializing checker: {str(e)}")
        return None

@st.cache_resource(show_spinner=False)
def load_rules_cached():
    """
    Load compliance rules (cached once).
    """
    try:
        rules_path = os.getenv("RULES_PATH", "data/rules.yaml")
        rules = load_rules(rules_path)
        return rules
    except Exception as e:
        st.error(f"Error loading rules: {str(e)}")
        return None

if "checker" not in st.session_state:
    st.session_state.checker = None
if "current_rules" not in st.session_state:
    st.session_state.current_rules = None

def ingest_uploaded_pdfs(uploaded_files, chroma_dir):
    """Ingest uploaded PDF files into the vector database."""
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_core.documents import Document
    
    documents = []
    
    # Temporarily save uploaded files
    with tempfile.TemporaryDirectory() as tmpdir:
        for uploaded_file in uploaded_files:
            file_path = os.path.join(tmpdir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Load PDF
            try:
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                for doc in docs:
                    doc.metadata["source"] = uploaded_file.name
                documents.extend(docs)
            except Exception as e:
                st.error(f"Error loading {uploaded_file.name}: {str(e)}")
    
    if not documents:
        raise ValueError("No documents were loaded from the uploaded files.")
    
    # Split and embed documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200,
        add_start_index=True,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    
    # Create/update vector store
    embeddings = GoogleGenerativeAIEmbeddings(
        model=os.getenv("EMBED_MODEL", "models/text-embedding-004")
    )
    
    db = Chroma(
        persist_directory=chroma_dir,
        embedding_function=embeddings,
        collection_name="documents"
    )
    db.add_documents(chunks)
    
    return len(chunks)

tab1, tab2, tab3, tab4 = st.tabs(["System Setup", "Check Single Rule", "Check All Rules", "Documentation"])

with tab1:
    st.subheader("Initialize and Configure the System")
    
    st.info("""
    **⚡ Performance Tip:** The system is optimized for Streamlit Cloud.
    - First run loads and caches everything (~1-2 minutes)
    - Subsequent runs are instant
    - Vector database is cached in memory for fast access
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Step 1: Load Checker")
        st.markdown("Initialize the compliance checker (auto-cached on first run).")
        if st.button("Initialize Checker", key="init_checker_btn", use_container_width=True):
            with st.spinner("Loading RAG system..."):
                st.session_state.checker = initialize_checker()
            if st.session_state.checker:
                st.success("✓ Checker initialized!")
            else:
                st.error("Failed to initialize checker")
    
    with col2:
        st.markdown("#### Step 2: Load Rules")
        st.markdown("Load compliance rules from configuration.")
        if st.button("Load Rules", key="load_rules_btn", use_container_width=True):
            with st.spinner("Loading rules..."):
                st.session_state.current_rules = load_rules_cached()
            if st.session_state.current_rules:
                st.success(f"✓ Loaded {len(st.session_state.current_rules)} rules!")
            else:
                st.error("Failed to load rules")
    
    with col3:
        st.markdown("#### Step 3: Database Status")
        st.markdown("Check vector database status.")
        if st.button("Check DB Status", key="check_db_btn", use_container_width=True):
            chroma_dir = os.getenv("CHROMA_PATH", "vector_db")
            if os.path.exists(chroma_dir):
                st.success(f"✓ Database exists at: {chroma_dir}")
            else:
                st.warning("Database not found. Ingest documents first.")
    
    st.divider()
    
    # Step 2: Choose PDF source
    st.markdown("#### Document Ingestion (Optional)")
    pdf_source = st.radio(
        "Choose where to load PDFs from:",
        ["Use PDFs from data/pdfs folder", "Upload your own PDF files"],
        horizontal=True
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if pdf_source == "Use PDFs from data/pdfs folder":
            st.markdown("Load PDF documents from `data/pdfs` into the vector database.")
            if st.button("Ingest PDFs from Folder", key="ingest_btn", use_container_width=True):
                try:
                    with st.spinner("Ingesting documents (this may take a while)..."):
                        ingest_pdfs()
                    st.success("Documents ingested successfully!")
                    # Clear checker cache to reload with new documents
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Error ingesting documents: {str(e)}")
        else:
            st.markdown("Upload your PDF files to ingest them into the vector database.")
            uploaded_files = st.file_uploader(
                "Choose PDF files",
                type="pdf",
                accept_multiple_files=True,
                key="pdf_uploader"
            )
            
            if uploaded_files and st.button("Ingest Uploaded PDFs", key="ingest_upload_btn", use_container_width=True):
                try:
                    with st.spinner("Ingesting uploaded documents..."):
                        chroma_dir = os.getenv("CHROMA_PATH", "vector_db")
                        num_chunks = ingest_uploaded_pdfs(uploaded_files, chroma_dir)
                    st.success(f"Successfully ingested {len(uploaded_files)} file(s) ({num_chunks} chunks)!")
                    st.session_state.checker = None
                except Exception as e:
                    st.error(f"Error ingesting uploaded documents: {str(e)}")
                    # Clear checker cache to reload with new documents
                    st.cache_resource.clear()

with tab2:
    st.subheader("Check Individual Compliance Rules")
    
    if st.session_state.checker is None:
        st.warning("Checker not initialized. Click 'Initialize System' in the Setup tab first.")
    elif st.session_state.current_rules is None:
        st.warning("Rules not loaded. Click 'Load Rules' in the Setup tab first.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            rule_options = [f"{r.get('id')} - {r.get('name')}" for r in st.session_state.current_rules]
            rule_selector = st.selectbox("Select Rule", rule_options, key="rule_select")
        
        with col2:
            top_k = st.slider("Top K Documents", min_value=1, max_value=20, value=6, key="top_k_single")
        
        if st.button("Check Rule", key="check_single", use_container_width=True):
            try:
                rule_id = rule_selector.split(" - ")[0]
                rule = next((r for r in st.session_state.current_rules if r.get("id") == rule_id), None)
                
                if not rule:
                    st.error(f"Rule {rule_id} not found")
                else:
                    with st.spinner(f"Checking {rule.get('name')}..."):
                        result = st.session_state.checker.check_rule(rule, top_k=int(top_k))
                    
                    st.markdown("### Result")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Status", result.get("status", "Unknown"))
                    with col2:
                        st.metric("Confidence", f"{result.get('confidence', 0):.1%}")
                    with col3:
                        st.metric("Documents Retrieved", result.get("_retrieval", {}).get("num_retrieved", 0))
                    
                    if result.get("evidence"):
                        st.markdown("#### Evidence")
                        for i, ev in enumerate(result["evidence"], 1):
                            if isinstance(ev, dict):
                                st.markdown(f"**{i}. {ev.get('source')}**")
                                st.text(ev.get('text', '')[:500])
                            else:
                                st.text(ev)
                    
                    if result.get("recommended_corrections"):
                        st.markdown("#### Recommended Corrections")
                        for i, rec in enumerate(result["recommended_corrections"], 1):
                            st.markdown(f"**{i}.** {rec}")
                    
                    with st.expander("View Full Result (JSON)"):
                        st.json(result)
            
            except Exception as e:
                st.error(f"Error checking rule: {str(e)}")

with tab3:
    st.subheader("Run Complete Compliance Check")
    
    if st.session_state.checker is None:
        st.warning("Checker not initialized. Click 'Initialize System' in the Setup tab first.")
    elif st.session_state.current_rules is None:
        st.warning("Rules not loaded. Click 'Load Rules' in the Setup tab first.")
    else:
        top_k_batch = st.slider("Top K Documents per Rule", min_value=1, max_value=20, value=6, key="top_k_batch")
        
        if st.button("Run Compliance Check", key="check_all", use_container_width=True):
            try:
                all_results = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, rule in enumerate(st.session_state.current_rules):
                    status_text.text(f"Checking {rule.get('id')} - {rule.get('name')}...")
                    res = st.session_state.checker.check_rule(rule, top_k=int(top_k_batch))
                    res["rule_id"] = res.get("rule_id") or rule.get("id")
                    res["rule_name"] = rule.get("name")
                    if "evidence" not in res:
                        res["evidence"] = []
                    if "recommended_corrections" not in res:
                        res["recommended_corrections"] = []
                    all_results.append(res)
                    progress_bar.progress((i + 1) / len(st.session_state.current_rules))
                
                outdir = "reports"
                os.makedirs(outdir, exist_ok=True)
                
                csv_path = os.path.join(outdir, "compliance_report.csv")
                md_path = os.path.join(outdir, "compliance_report.md")
                json_path = os.path.join(outdir, "compliance_report.json")
                
                save_results_csv(all_results, outpath=csv_path)
                save_results_markdown(all_results, outpath=md_path)
                save_raw_json(all_results, outpath=json_path)
                
                compliant = sum(1 for r in all_results if r.get("status") == "Compliant")
                non_compliant = sum(1 for r in all_results if r.get("status") == "Non-Compliant")
                not_applicable = sum(1 for r in all_results if r.get("status") == "Not Applicable")
                
                st.success("Compliance check complete!")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Rules", len(all_results))
                with col2:
                    st.metric("Compliant", compliant)
                with col3:
                    st.metric("Non-Compliant", non_compliant)
                with col4:
                    st.metric("Not Applicable", not_applicable)
                
                st.markdown("### Download Reports")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    with open(csv_path, "rb") as f:
                        st.download_button("📊 CSV Report", f, file_name="compliance_report.csv", mime="text/csv")
                with col2:
                    with open(md_path, "rb") as f:
                        st.download_button("📝 Markdown Report", f, file_name="compliance_report.md", mime="text/markdown")
                with col3:
                    with open(json_path, "rb") as f:
                        st.download_button("📋 JSON Report", f, file_name="compliance_report.json", mime="application/json")
                
                with st.expander("View Results Summary"):
                    for r in all_results:
                        st.markdown(f"### {r.get('rule_id')} - {r.get('rule_name')}")
                        st.markdown(f"**Status:** {r.get('status')} | **Confidence:** {r.get('confidence', 0):.1%}")
                        if r.get("evidence"):
                            st.markdown("**Evidence:** " + " | ".join([e.get("source", "") for e in r["evidence"] if isinstance(e, dict)]))
            
            except Exception as e:
                st.error(f"Error running compliance check: {str(e)}")

with tab4:
    st.markdown("""
    ## How to Use
    
    ### 1. System Setup
    - **Ingest PDFs**: Load your compliance documents from `data/pdfs`
    - **Initialize System**: Initialize the RAG checker
    - **Load Rules**: Load compliance rules from `data/rules.yaml`
    
    ### 2. Check Rules
    - **Single Rule**: Select a specific rule and check it
    - **Batch Check**: Run all compliance rules at once
    
    ### 3. Results
    - View results in the UI
    - Download reports in CSV, Markdown, or JSON format
    
    ## Configuration
    
    Edit `.env` file to customize:
    - `GOOGLE_API_KEY`: Your Google Generative AI API key
    - `CHROMA_PATH`: Path to the vector database
    - `DATA_PATH`: Path to PDF documents
    - `EMBED_MODEL`: Embedding model to use
    - `LLM_MODEL`: Language model for compliance checking
    
    ## Rule Format
    
    Rules are defined in `data/rules.yaml` with:
    - `id`: Unique rule identifier
    - `name`: Human-readable rule name
    - `description`: Rule description
    - `keywords`: Search keywords for retrieval
    - `required_phrases`: Phrases that must be present
    - `severity`: Critical, High, Medium, Low
    
    ## System Architecture
    
    1. **Document Ingestion**: PDFs are loaded and split into chunks
    2. **Embedding**: Chunks are embedded using Google's embedding model
    3. **Vector Storage**: Embeddings stored in Chroma vector database
    4. **Rule Checking**: For each rule, retrieve relevant documents and use Gemini AI to assess compliance
    5. **Report Generation**: Results exported as CSV, Markdown, and JSON
    
    ## Getting Started
    
    1. Add your Google API key to `.env`
    2. Place PDF documents in `data/pdfs/`
    3. Ensure `data/rules.yaml` contains your compliance rules
    4. Click the buttons in order: Ingest → Initialize → Load Rules
    5. Start checking rules!
    """)
