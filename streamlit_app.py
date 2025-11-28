import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from engine.utils import load_rules, save_results_csv, save_results_markdown, save_raw_json
from rag.rag_checker import RAGComplianceChecker
from ingestion.create_db import main as ingest_pdfs
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

st.set_page_config(page_title="Compliance Checker", layout="wide")

st.title("Compliance Checker")
st.text("RAG-based compliance analysis using Gemini AI")

# ========== CACHED FUNCTIONS ==========

@st.cache_resource(show_spinner=False)
def initialize_checker():
    """Initialize RAG compliance checker (cached once)."""
    try:
        chroma_dir = os.getenv("CHROMA_PATH", "vector_db")
        checker = RAGComplianceChecker(chroma_dir=chroma_dir)
        return checker
    except Exception as e:
        st.error(f"Error initializing checker: {str(e)}")
        return None

@st.cache_resource(show_spinner=False)
def load_rules_cached():
    """Load compliance rules (cached once)."""
    try:
        rules_path = os.getenv("RULES_PATH", "data/rules.yaml")
        rules = load_rules(rules_path)
        return rules
    except Exception as e:
        st.error(f"Error loading rules: {str(e)}")
        return None

# Session state
if "checker" not in st.session_state:
    st.session_state.checker = None
if "current_rules" not in st.session_state:
    st.session_state.current_rules = None

def ingest_uploaded_pdfs(uploaded_files, chroma_dir):
    """Ingest uploaded PDF files into the vector database."""
    from langchain_community.document_loaders import PyPDFLoader
    
    documents = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for uploaded_file in uploaded_files:
            file_path = os.path.join(tmpdir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
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
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200,
        add_start_index=True,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    
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

# ========== STEP 1: DOCUMENT INGESTION ==========
st.header("Step 1: Select Document Source")

pdf_source = st.radio(
    "Choose where to load PDFs from:",
    ["Use PDFs from data/pdfs folder", "Upload PDF files"],
    horizontal=True,
    key="pdf_source_choice"
)

if pdf_source == "Use PDFs from data/pdfs folder":
    if st.button("Ingest PDFs from Folder", key="btn_ingest_folder", use_container_width=True):
        try:
            with st.spinner("Processing documents..."):
                ingest_pdfs()
            st.success("Documents ingested successfully")
            st.cache_resource.clear()
        except Exception as e:
            st.error(f"Error: {str(e)}")
else:
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type="pdf",
        accept_multiple_files=True,
        key="pdf_uploader"
    )
    
    if uploaded_files:
        if st.button("Ingest Uploaded PDFs", key="btn_ingest_upload", use_container_width=True):
            try:
                with st.spinner("Processing documents..."):
                    chroma_dir = os.getenv("CHROMA_PATH", "vector_db")
                    num_chunks = ingest_uploaded_pdfs(uploaded_files, chroma_dir)
                st.success(f"Ingested {len(uploaded_files)} file(s) - {num_chunks} chunks")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Error: {str(e)}")

st.divider()

# ========== STEP 2: INITIALIZE SYSTEM ==========
st.header("Step 2: Initialize System")

col1, col2 = st.columns(2)

with col1:
    if st.button("Initialize Checker", key="btn_init_checker", use_container_width=True):
        with st.spinner("Loading system..."):
            st.session_state.checker = initialize_checker()
        if st.session_state.checker:
            st.success("System ready")
        else:
            st.error("Failed to initialize")

with col2:
    if st.button("Load Rules", key="btn_load_rules", use_container_width=True):
        with st.spinner("Loading rules..."):
            st.session_state.current_rules = load_rules_cached()
        if st.session_state.current_rules:
            st.success(f"Loaded {len(st.session_state.current_rules)} rules")
        else:
            st.error("Failed to load rules")

st.divider()

# ========== STEP 3: CHECK COMPLIANCE ==========
st.header("Step 3: Check Compliance")

tab1, tab2 = st.tabs(["Check Single Rule", "Check All Rules"])

with tab1:
    st.subheader("Check Individual Rule")
    
    if st.session_state.checker is None:
        st.warning("System not initialized. Click 'Initialize Checker' first.")
    elif st.session_state.current_rules is None:
        st.warning("Rules not loaded. Click 'Load Rules' first.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            rule_options = [f"{r.get('id')} - {r.get('name')}" for r in st.session_state.current_rules]
            selected_rule = st.selectbox(
                "Select rule to check:",
                rule_options,
                key="rule_selectbox"
            )
        
        with col2:
            top_k = st.slider(
                "Context documents:",
                min_value=1,
                max_value=12,
                value=6,
                key="top_k_single"
            )
        
        if st.button("Check Rule", key="btn_check_single", use_container_width=True):
            rule_id = selected_rule.split(" - ")[0]
            rule = next((r for r in st.session_state.current_rules if r.get("id") == rule_id), None)
            
            if not rule:
                st.error(f"Rule {rule_id} not found")
            else:
                with st.spinner(f"Analyzing {rule.get('name')}..."):
                    result = st.session_state.checker.check_rule(rule, top_k=int(top_k))
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Status", result.get("status", "Unknown"))
                with col2:
                    conf = result.get('confidence', 0)
                    st.metric("Confidence", f"{conf*100:.0f}%")
                with col3:
                    num_docs = result.get("_retrieval", {}).get("num_retrieved", 0)
                    st.metric("Documents", num_docs)
                
                st.divider()
                
                if result.get("evidence"):
                    st.subheader("Evidence")
                    for i, ev in enumerate(result["evidence"], 1):
                        if isinstance(ev, dict):
                            st.write(f"**Source {i}:** {ev.get('source', 'Unknown')}")
                            st.text_area(
                                "Content",
                                value=ev.get('text', '')[:300],
                                height=80,
                                disabled=True,
                                key=f"evidence_{i}"
                            )
                
                if result.get("recommended_corrections"):
                    st.subheader("Recommendations")
                    for i, rec in enumerate(result["recommended_corrections"], 1):
                        st.write(f"- {rec}")
                
                with st.expander("View full result"):
                    st.json(result)

with tab2:
    st.subheader("Run Complete Compliance Check")
    
    if st.session_state.checker is None:
        st.warning("System not initialized. Click 'Initialize Checker' first.")
    elif st.session_state.current_rules is None:
        st.warning("Rules not loaded. Click 'Load Rules' first.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("Run compliance checks for all rules")
        
        with col2:
            top_k_batch = st.slider(
                "Context documents:",
                min_value=1,
                max_value=12,
                value=6,
                key="top_k_batch"
            )
        
        if st.button("Run Batch Check", key="btn_check_batch", use_container_width=True):
            all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, rule in enumerate(st.session_state.current_rules):
                status_text.text(f"Checking {i+1}/{len(st.session_state.current_rules)}: {rule.get('id')}")
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
            
            status_text.text("Check complete")
            st.divider()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Rules", len(all_results))
            with col2:
                st.metric("Compliant", compliant)
            with col3:
                st.metric("Non-Compliant", non_compliant)
            with col4:
                st.metric("Not Applicable", not_applicable)
            
            st.divider()
            
            st.subheader("Download Reports")
            col1, col2, col3 = st.columns(3)
            with col1:
                with open(csv_path, "rb") as f:
                    st.download_button(
                        "CSV",
                        f,
                        file_name="compliance_report.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="btn_download_csv"
                    )
            with col2:
                with open(md_path, "rb") as f:
                    st.download_button(
                        "Markdown",
                        f,
                        file_name="compliance_report.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key="btn_download_md"
                    )
            with col3:
                with open(json_path, "rb") as f:
                    st.download_button(
                        "JSON",
                        f,
                        file_name="compliance_report.json",
                        mime="application/json",
                        use_container_width=True,
                        key="btn_download_json"
                    )
            
            with st.expander("View detailed results"):
                for r in all_results:
                    st.write(f"**{r.get('rule_id')} - {r.get('rule_name')}**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"Status: {r.get('status')}")
                    with col2:
                        st.write(f"Confidence: {r.get('confidence', 0):.1%}")

st.divider()

st.header("How to Use")
st.write("""
**Step 1:** Select your PDF source (folder or upload) and ingest documents

**Step 2:** Click Initialize Checker and Load Rules to set up the system

**Step 3:** Check individual rules or run batch check for all rules

**Performance Tips:**
- Lower context documents slider for faster results
- Single rule checks are faster than batch checks
- Results are saved in reports/ folder
""")
