import os
import gradio as gr
import json
from dotenv import load_dotenv
from engine.utils import load_rules, save_results_csv, save_results_markdown, save_raw_json
from rag.rag_checker import RAGComplianceChecker
from ingestion.create_db import main as ingest_pdfs

load_dotenv()

checker = None
current_rules = None

def initialize_checker():
    global checker
    try:
        chroma_dir = os.getenv("CHROMA_PATH", "vector_db")
        checker = RAGComplianceChecker(chroma_dir=chroma_dir)
        return "Compliance checker initialized successfully"
    except Exception as e:
        return f"Error initializing checker: {str(e)}"

def load_rules_ui():
    global current_rules
    try:
        rules_path = os.getenv("RULES_PATH", "data/rules.yaml")
        current_rules = load_rules(rules_path)
        return f"Loaded {len(current_rules)} compliance rules"
    except Exception as e:
        return f"Error loading rules: {str(e)}"

def get_rules_list():
    if current_rules is None:
        return ["No rules loaded"]
    return [f"{r.get('id')} - {r.get('name')}" for r in current_rules]

def check_single_rule(rule_selector, top_k):
    if checker is None:
        return None, "Checker not initialized. Click 'Initialize System' first."
    
    if current_rules is None:
        return None, "Rules not loaded. Click 'Load Rules' first."
    
    try:
        rule_id = rule_selector.split(" - ")[0]
        
        rule = next((r for r in current_rules if r.get("id") == rule_id), None)
        if not rule:
            return None, f"Rule {rule_id} not found"
        
        result = checker.check_rule(rule, top_k=int(top_k))
        result["rule_id"] = rule_id
        result["rule_name"] = rule.get("name", "")
        
        if "evidence" not in result:
            result["evidence"] = []
        if "recommended_corrections" not in result:
            result["recommended_corrections"] = []
        
        output_text = format_result(result)
        
        return result, output_text
        
    except Exception as e:
        return None, f"Error checking rule: {str(e)}"

def format_result(result):
    lines = []
    lines.append(f"**Rule ID:** {result.get('rule_id', 'N/A')}")
    lines.append(f"**Rule Name:** {result.get('rule_name', 'N/A')}")
    lines.append(f"**Status:** {result.get('status', 'Unknown')}")
    lines.append(f"**Confidence:** {result.get('confidence', 0):.2%}")
    
    if result.get("evidence"):
        lines.append("\n**Evidence:**")
        for i, ev in enumerate(result["evidence"], 1):
            if isinstance(ev, dict):
                text = ev.get("text", "")[:200]
                source = ev.get("source", "Unknown")
                lines.append(f"  {i}. {text}... ({source})")
            else:
                lines.append(f"  {i}. {str(ev)[:200]}")
    
    if result.get("recommended_corrections"):
        lines.append("\n**Recommended Corrections:**")
        for i, rec in enumerate(result["recommended_corrections"], 1):
            lines.append(f"  {i}. {rec}")
    
    if result.get("_retrieval"):
        lines.append(f"\n**Retrieval Info:** {result['_retrieval'].get('num_retrieved', 0)} docs retrieved (top score: {result['_retrieval'].get('top_score', 0):.3f})")
    
    return "\n".join(lines)

def check_all_rules(top_k, progress=gr.Progress()):
    if checker is None:
        return "Checker not initialized", None, None, None
    
    if current_rules is None:
        return "Rules not loaded", None, None, None
    
    try:
        all_results = []
        progress(0, desc="Starting compliance check...")
        
        for rule in progress.track(current_rules):
            result = checker.check_rule(rule, top_k=int(top_k))
            result["rule_id"] = result.get("rule_id") or rule.get("id")
            result["rule_name"] = rule.get("name", "")
            if "evidence" not in result:
                result["evidence"] = []
            if "recommended_corrections" not in result:
                result["recommended_corrections"] = []
            all_results.append(result)
        
        outdir = "reports"
        os.makedirs(outdir, exist_ok=True)
        
        csv_path = os.path.join(outdir, "compliance_report.csv")
        md_path = os.path.join(outdir, "compliance_report.md")
        json_path = os.path.join(outdir, "compliance_report.json")
        
        save_results_csv(all_results, outpath=csv_path)
        save_results_markdown(all_results, outpath=md_path)
        save_raw_json(all_results, outpath=json_path)
        
        compliant_count = sum(1 for r in all_results if r.get("status") == "Compliant")
        non_compliant_count = sum(1 for r in all_results if r.get("status") == "Non-Compliant")
        not_applicable_count = sum(1 for r in all_results if r.get("status") == "Not Applicable")
        
        summary = f"""
## Compliance Check Complete

**Summary:**
- Total Rules: {len(all_results)}
- Compliant: {compliant_count}
- Non-Compliant: {non_compliant_count}
- Not Applicable: {not_applicable_count}

**Reports Generated:**
- CSV Report: compliance_report.csv
- Markdown Report: compliance_report.md
- JSON Report: compliance_report.json

All reports saved to `{outdir}/` directory.
        """
        
        return summary, csv_path, md_path, json_path
        
    except Exception as e:
        return f"Error checking rules: {str(e)}", None, None, None

def ingest_documents(progress=gr.Progress()):
    try:
        progress(0, desc="Starting document ingestion...")
        ingest_pdfs()
        global checker
        checker = None
        return "Documents ingested successfully. Click 'Initialize System' to reload."
    except Exception as e:
        return f"Error ingesting documents: {str(e)}"

with gr.Blocks(title="RAG Compliance Checker", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # RAG-Based Compliance Checking System
    
    This application uses Retrieval-Augmented Generation (RAG) to automatically check 
    compliance rules against your documents. Powered by Gemini AI and Chroma vector database.
    """)
    
    with gr.Tabs():
        with gr.Tab("System Setup"):
            gr.Markdown("### Initialize and Configure the System")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Step 1: Ingest Documents")
                    gr.Markdown("Load PDF documents from `data/pdfs` into the vector database.")
                    ingest_btn = gr.Button("Ingest PDFs", scale=2, variant="primary")
                    ingest_status = gr.Textbox(label="Status", interactive=False, lines=2)
                    
                with gr.Column():
                    gr.Markdown("#### Step 2: Initialize Checker")
                    gr.Markdown("Initialize the compliance checker with the vector database.")
                    init_btn = gr.Button("Initialize System", scale=2, variant="primary")
                    init_status = gr.Textbox(label="Status", interactive=False, lines=2)
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Step 3: Load Rules")
                    gr.Markdown("Load compliance rules from YAML configuration.")
                    load_btn = gr.Button("Load Rules", scale=2, variant="primary")
                    load_status = gr.Textbox(label="Status", interactive=False, lines=2)
            ingest_btn.click(ingest_documents, outputs=ingest_status)
            init_btn.click(initialize_checker, outputs=init_status)
            load_btn.click(load_rules_ui, outputs=load_status)
        
        with gr.Tab("Check Single Rule"):
            gr.Markdown("### Check Individual Compliance Rules")
            
            with gr.Row():
                with gr.Column(scale=2):
                    rule_selector = gr.Dropdown(
                        choices=get_rules_list(),
                        label="Select Rule",
                        interactive=True
                    )
                    rule_selector.change(fn=lambda: get_rules_list(), outputs=rule_selector)
                
                with gr.Column(scale=1):
                    top_k_single = gr.Slider(
                        minimum=1,
                        maximum=20,
                        value=6,
                        step=1,
                        label="Top K Documents"
                    )
            
            check_single_btn = gr.Button("Check Rule", scale=1, variant="primary")
            
            with gr.Row():
                result_display = gr.Markdown(label="Result")
            
            check_single_btn.click(
                check_single_rule,
                inputs=[rule_selector, top_k_single],
                outputs=[None, result_display]
            )
        
        with gr.Tab("Check All Rules"):
            gr.Markdown("### Run Complete Compliance Check")
            
            with gr.Row():
                with gr.Column():
                    top_k_batch = gr.Slider(
                        minimum=1,
                        maximum=20,
                        value=6,
                        step=1,
                        label="Top K Documents per Rule"
                    )
                    check_all_btn = gr.Button("Run Compliance Check", scale=2, variant="primary")
            
            summary_display = gr.Markdown(label="Summary")
            
            with gr.Row():
                csv_file = gr.File(label="Download CSV", type="filepath")
                md_file = gr.File(label="Download Markdown", type="filepath")
                json_file = gr.File(label="Download JSON", type="filepath")
            
            check_all_btn.click(
                check_all_rules,
                inputs=[top_k_batch],
                outputs=[summary_display, csv_file, md_file, json_file]
            )
        
        with gr.Tab("Documentation"):
            gr.Markdown("""
            ## How to Use
            
            ### 1. System Setup
            - **Ingest PDFs**: Upload your compliance documents from `data/pdfs`
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
            """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
