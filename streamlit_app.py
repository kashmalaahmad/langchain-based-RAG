import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from engine.utils import load_rules, save_results_csv, save_results_markdown, save_raw_json
from rag.rag_checker import RAGComplianceChecker
from ingestion.create_db import main as ingest_pdfs
from ingestion.loaders import load_pdfs_from_dir
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import json

load_dotenv()

# Page config
st.set_page_config(
    page_title="⚖️ Compliance Checker",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .section-header {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 5px;
        margin: 1.5rem 0 1rem 0;
        border-left: 4px solid #667eea;
    }
    .metric-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 5px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Custom header
st.markdown("""
<div class="main-header">
    <h1>⚖️ RAG Compliance Checker</h1>
    <p>Powered by Gemini AI & Vector Search</p>
</div>
""", unsafe_allow_html=True)

# ========== CACHED FUNCTIONS FOR PERFORMANCE ==========

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
if "system_ready" not in st.session_state:
    st.session_state.system_ready = False

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

# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("## ⚙️ System Setup")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔧 Initialize", key="init_checker_btn", use_container_width=True):
            with st.spinner("Loading system..."):
                st.session_state.checker = initialize_checker()
            if st.session_state.checker:
                st.success("✓ System Ready!")
                st.session_state.system_ready = True
            else:
                st.error("Failed to initialize")
    
    with col2:
        if st.button("📋 Load Rules", key="load_rules_btn", use_container_width=True):
            with st.spinner("Loading rules..."):
                st.session_state.current_rules = load_rules_cached()
            if st.session_state.current_rules:
                st.success(f"✓ {len(st.session_state.current_rules)} rules")
    
    st.divider()
    
    st.markdown("## 📄 Document Management")
    pdf_source = st.radio("Data Source:", ["📁 Folder", "📤 Upload"], horizontal=True)
    
    if pdf_source == "📁 Folder":
        if st.button("📥 Ingest from Folder", use_container_width=True):
            try:
                with st.spinner("Processing..."):
                    ingest_pdfs()
                st.success("✓ Documents ingested!")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        uploaded_files = st.file_uploader("Choose PDFs", type="pdf", accept_multiple_files=True)
        if uploaded_files and st.button("📥 Ingest PDFs", use_container_width=True):
            try:
                with st.spinner("Processing..."):
                    chroma_dir = os.getenv("CHROMA_PATH", "vector_db")
                    num_chunks = ingest_uploaded_pdfs(uploaded_files, chroma_dir)
                st.success(f"✓ {len(uploaded_files)} file(s) ingested!")
                st.cache_resource.clear()
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    st.divider()
    st.markdown("## ℹ️ About")
    st.caption("RAG-based compliance checking using Gemini 2.0 Flash & Vector DB")

# ========== MAIN CONTENT ==========

# Quick status bar
col1, col2, col3 = st.columns(3)
with col1:
    status = "✅ Ready" if st.session_state.system_ready else "⏳ Not Ready"
    st.metric("System", status)
with col2:
    rules_count = len(st.session_state.current_rules) if st.session_state.current_rules else 0
    st.metric("Rules Loaded", rules_count)
with col3:
    db_exists = "✅ Active" if os.path.exists(os.getenv("CHROMA_PATH", "vector_db")) else "❌ Not Found"
    st.metric("Database", db_exists)

st.divider()

# Tabs for main functionality
tab1, tab2, tab3 = st.tabs(["🔍 Check Rule", "📊 Batch Check", "📚 Docs"])

with tab1:
    st.markdown("### Check Single Compliance Rule")
    
    if st.session_state.checker is None:
        st.warning("⚠️ System not initialized. Click **🔧 Initialize** in the sidebar first.")
    elif st.session_state.current_rules is None:
        st.warning("⚠️ Rules not loaded. Click **📋 Load Rules** in the sidebar first.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            rule_options = [f"{r.get('id')} - {r.get('name')}" for r in st.session_state.current_rules]
            rule_selector = st.selectbox("Select a rule to check:", rule_options, key="rule_select")
        
        with col2:
            top_k = st.slider("Context Documents", min_value=1, max_value=12, value=6, key="top_k_single")
        
        if st.button("🔍 Check Rule", use_container_width=True, type="primary"):
            rule_id = rule_selector.split(" - ")[0]
            rule = next((r for r in st.session_state.current_rules if r.get("id") == rule_id), None)
            
            if not rule:
                st.error(f"Rule {rule_id} not found")
            else:
                with st.spinner(f"Analyzing {rule.get('name')}... This may take a minute."):
                    result = st.session_state.checker.check_rule(rule, top_k=int(top_k))
                
                # Display result
                col1, col2, col3 = st.columns(3)
                
                status_color = {"Compliant": "🟢", "Non-Compliant": "🔴", "Not Applicable": "🟡"}
                status_icon = status_color.get(result.get("status"), "⚪")
                
                with col1:
                    st.metric("Status", f"{status_icon} {result.get('status', 'Unknown')}")
                with col2:
                    conf = result.get('confidence', 0)
                    st.metric("Confidence", f"{conf*100:.0f}%")
                with col3:
                    num_docs = result.get("_retrieval", {}).get("num_retrieved", 0)
                    st.metric("Sources", f"{num_docs} docs")
                
                # Evidence section
                if result.get("evidence"):
                    with st.expander("📖 Evidence", expanded=True):
                        for i, ev in enumerate(result["evidence"], 1):
                            if isinstance(ev, dict):
                                st.write(f"**Source {i}:** {ev.get('source', 'Unknown')}")
                                st.text_area("", value=ev.get('text', '')[:300], height=80, disabled=True, key=f"ev_{i}")
                            else:
                                st.write(f"**Source {i}:** {ev}")
                
                # Recommendations
                if result.get("recommended_corrections"):
                    with st.expander("💡 Recommendations", expanded=True):
                        for i, rec in enumerate(result["recommended_corrections"], 1):
                            st.write(f"{i}. {rec}")
                
                # Full details
                with st.expander("📋 Full Result (JSON)"):
                    st.json(result)

with tab2:
    st.markdown("### Run Complete Compliance Check")
    
    if st.session_state.checker is None:
        st.warning("⚠️ System not initialized. Click **🔧 Initialize** in the sidebar first.")
    elif st.session_state.current_rules is None:
        st.warning("⚠️ Rules not loaded. Click **📋 Load Rules** in the sidebar first.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("Run compliance checks for all rules. This will take several minutes.")
        
        with col2:
            top_k_batch = st.slider("Context Documents", min_value=1, max_value=12, value=6, key="top_k_batch")
        
        if st.button("▶️ Run Batch Check", use_container_width=True, type="primary"):
            all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, rule in enumerate(st.session_state.current_rules):
                status_text.text(f"Checking {i+1}/{len(st.session_state.current_rules)}: {rule.get('id')}...")
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
            
            status_text.text("✅ Compliance check complete!")
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Rules", len(all_results))
            with col2:
                st.metric("✅ Compliant", compliant)
            with col3:
                st.metric("🔴 Non-Compliant", non_compliant)
            with col4:
                st.metric("🟡 Not Applicable", not_applicable)
            
            st.divider()
            
            # Download buttons
            st.markdown("### 📥 Download Reports")
            col1, col2, col3 = st.columns(3)
            with col1:
                with open(csv_path, "rb") as f:
                    st.download_button("📊 CSV", f, file_name="compliance_report.csv", mime="text/csv", use_container_width=True)
            with col2:
                with open(md_path, "rb") as f:
                    st.download_button("📝 Markdown", f, file_name="compliance_report.md", mime="text/markdown", use_container_width=True)
            with col3:
                with open(json_path, "rb") as f:
                    st.download_button("📋 JSON", f, file_name="compliance_report.json", mime="application/json", use_container_width=True)
            
            # Results summary
            with st.expander("📊 View Detailed Results"):
                for r in all_results:
                    st.markdown(f"### {r.get('rule_id')} - {r.get('rule_name')}")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Status:** {r.get('status')}")
                    with col2:
                        st.write(f"**Confidence:** {r.get('confidence', 0):.1%}")
                    with col3:
                        sources = ", ".join([e.get("source", "") for e in r.get("evidence", []) if isinstance(e, dict)])
                        st.write(f"**Sources:** {sources}")

with tab3:
    st.markdown("""
    ### 📚 How to Use This System
    
    #### Step 1: Initialize System (Sidebar)
    - Click **🔧 Initialize** to load the RAG system
    - Click **📋 Load Rules** to import compliance rules
    
    #### Step 2: Manage Documents (Sidebar)
    - Choose data source: 📁 Folder or 📤 Upload
    - Click **📥 Ingest** to process PDFs
    
    #### Step 3: Check Compliance
    - **🔍 Check Rule Tab:** Test individual rules quickly
    - **📊 Batch Check Tab:** Run all rules at once
    
    #### Understanding Results
    - **Status:** Compliant / Non-Compliant / Not Applicable
    - **Confidence:** How sure the AI is (0-100%)
    - **Evidence:** Source documents supporting the decision
    - **Recommendations:** Actions to improve compliance
    
    ---
    
    ### ⚡ Performance Tips
    - ✅ System is cached after first initialization (instant afterwards)
    - ✅ Reduce "Context Documents" slider for faster results (min speed: top_k=3)
    - ✅ Single rule checks are faster than batch checks
    - ✅ Results are saved in `reports/` folder
    
    ---
    
    ### 📖 Configuration
    
    Rules are defined in `data/rules.yaml` with:
    - `id`: Unique identifier
    - `name`: Rule description
    - `description`: Detailed explanation
    - `keywords`: Search terms
    - `required_phrases`: Must-have text
    - `severity`: Critical / High / Medium / Low
    
    ---
    
    ### 🔧 Customization
    
    Edit `.env` to customize:
    ```
    GOOGLE_API_KEY=your-key
    CHROMA_PATH=vector_db
    DATA_PATH=data/pdfs
    LLM_MODEL=gemini-2.0-flash
    TOP_K=6
    ```
    
    ---
    
    ### 🎯 Architecture
    
    1. **PDF Ingestion:** Documents → Chunks
    2. **Embeddings:** Chunks → Vector embeddings (Google)
    3. **Storage:** Vectors → Chroma DB
    4. **Retrieval:** Query → Top-K similar chunks
    5. **Analysis:** Context → Gemini LLM
    6. **Output:** Decision + Evidence + Recommendations
    """)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #888; font-size: 0.9em;'>
    Made with ❤️ | Powered by LangChain, Chroma & Gemini
</div>
""", unsafe_allow_html=True)

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
