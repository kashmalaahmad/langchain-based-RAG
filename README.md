# RAG-Based Compliance Checking System

A production-ready Retrieval-Augmented Generation (RAG) system for automated compliance checking using LangChain, Chroma vector database, and Google's Generative AI (Gemini).

## Overview

This system automatically checks compliance rules against documents using:
- **RAG Pipeline**: Retrieves relevant documents and uses LLMs for intelligent analysis
- **Vector Database**: Chroma for efficient document embedding and retrieval
- **LLM**: Google Gemini 1.5 Flash for compliance rule assessment
- **Web Interface**: Gradio for user-friendly interaction

## Features

- **Document Ingestion**: Automatic PDF loading and chunking
- **Vector Embeddings**: Google's text-embedding model for semantic search
- **Rule-Based Compliance Checking**: Assess multiple compliance rules against documents
- **Batch Processing**: Check all rules at once or individually
- **Multiple Report Formats**: CSV, Markdown, and JSON exports
- **Web UI**: Interactive Gradio interface for easy access
- **Configurable Parameters**: Top-K retrieval, thresholds, and batch sizes

## Project Structure

```
RAG-Gemini/
├── app.py                      # Gradio web interface
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
├── GRADIO_README.md           # UI documentation
│
├── data/
│   ├── rules.yaml             # Compliance rules definition
│   └── pdfs/                  # Input PDF documents
│
├── engine/
│   ├── run_compliance_agent.py # CLI compliance checker
│   └── utils.py               # Utility functions for reporting
│
├── ingestion/
│   ├── create_db.py           # Vector database creation
│   └── loaders.py             # PDF loading utilities
│
├── rag/
│   ├── rag_checker.py         # RAG compliance checker logic
│   └── retriever.py           # Chroma retriever wrapper
│
└── vector_db/                 # Chroma database storage
```

## Installation

### Prerequisites
- Python 3.10+
- Google Generative AI API key
- pip or conda

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/kashmalaahmad/langchain-based-RAG.git
cd langchain-based-RAG
```

2. **Create virtual environment**
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # macOS/Linux
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

## Configuration

Edit `.env` file with your settings:

```env
GOOGLE_API_KEY=your_api_key_here
CHROMA_PATH=vector_db
DATA_PATH=data/pdfs
EMBED_MODEL=models/text-embedding-004
LLM_MODEL=gemini-1.5-flash
TOP_K=6
FALLBACK_K=12
SIM_THRESHOLD=0.65
CONF_THRESHOLD=0.6
```

Get your API key at: https://makersuite.google.com/app/apikey

## Usage

### Web Interface (Recommended)

```bash
python app.py
```

Visit `http://localhost:7860` in your browser.

**Workflow:**
1. Click "Ingest PDFs" to load documents from `data/pdfs`
2. Click "Initialize System" to set up the checker
3. Click "Load Rules" to load compliance rules
4. Check single rules or run batch compliance checks
5. Download reports in CSV, Markdown, or JSON format

### Command Line

```bash
python -m engine.run_compliance_agent \
  --chroma_dir vector_db \
  --top_k 6 \
  --rules_path data/rules.yaml \
  --outdir reports
```

## Rule Format

Rules are defined in YAML format (`data/rules.yaml`):

```yaml
- id: RULE_001
  name: Identification of Parties
  description: The contract must explicitly name all parties
  severity: Critical
  obligation_type: Mandatory
  required_phrases:
    - "by and between"
    - "party"
  keywords:
    - "parties"
    - "agreement"
  notes: "Ensure party legal names appear"
```

## Output Files

After running checks, reports are saved to the `reports/` directory:

- **compliance_report.csv** - Spreadsheet format with all details
- **compliance_report.md** - Markdown format for documentation
- **compliance_report.json** - Raw JSON for programmatic access

## System Architecture

```
PDF Documents
    ↓
[PDF Loader] → Document Chunks
    ↓
[Text Splitter] (800 chars, 200 overlap)
    ↓
[Google Embeddings] → Vector Embeddings
    ↓
[Chroma Vector DB] ← Storage
    ↓
[Retriever] (Top-K retrieval with fallback)
    ↓
[Compliance Rules] + [Context] → [Gemini LLM]
    ↓
[JSON Parser] → Compliance Results
    ↓
[Report Generator] → CSV/MD/JSON Reports
```

## Key Components

### RAGComplianceChecker (`rag/rag_checker.py`)
- Retrieves relevant documents using semantic search
- Builds prompts with rule details and context
- Parses LLM output to extract compliance verdicts
- Returns detailed evidence and recommendations

### Chroma Retriever (`rag/retriever.py`)
- Loads PDFs from `data/pdfs`
- Integrates with Google Embeddings API
- Provides top-K similarity search

### Document Ingestion (`ingestion/create_db.py`)
- Loads all PDFs from specified directory
- Splits documents into chunks
- Batch processing with retry logic
- Persists to Chroma vector database

### Utilities (`engine/utils.py`)
- Load compliance rules from YAML
- Export results to CSV, Markdown, JSON formats

## Performance Tuning

- **Chunk Size**: Default 800 characters with 200 overlap
- **Top-K**: Number of documents to retrieve (default 6, fallback 12)
- **Batch Size**: Document batches during ingestion (default 3 for stability)
- **Similarity Threshold**: Minimum score to consider evidence (default 0.65)
- **Confidence Threshold**: Minimum confidence for verdicts (default 0.6)

## Troubleshooting

**"Checker not initialized"**
- Click "Initialize System" in the UI first

**"No documents ingested"**
- Add PDF files to `data/pdfs/` directory
- Click "Ingest PDFs" button

**API Rate Limits**
- Adjust batch size and sleep timers in `create_db.py`
- Consider using a paid Google API tier

**Slow Retrieval**
- Increase `TOP_K` parameter for broader search
- Check Chroma database size

## API Keys & Security

- **NEVER commit `.env` file** to version control
- Use `.env.example` as a template
- `.gitignore` automatically excludes `.env`
- For CI/CD, use environment variables or secrets management

## Dependencies

- **langchain** - LLM orchestration
- **langchain-community** - Document loaders and utilities
- **langchain-google-genai** - Google AI integration
- **chromadb** - Vector database
- **google-generativeai** - Gemini API access
- **gradio** - Web interface
- **pandas** - CSV reporting
- **pyyaml** - Rule configuration
- **python-dotenv** - Environment management

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Commit with clear messages
5. Push and create a Pull Request

## License

This project is provided as-is for educational and compliance checking purposes.

## Support

For issues or questions:
- Check the GRADIO_README.md for UI documentation
- Review configuration in `.env.example`
- Check system logs for error details
- Verify PDF files exist in `data/pdfs/`

## Future Enhancements

- [ ] Support for multiple LLM providers
- [ ] Caching layer for repeated queries
- [ ] Advanced rule templates and wizards
- [ ] Multi-language document support
- [ ] Real-time compliance monitoring
- [ ] Integration with compliance frameworks (ISO, SOC2, GDPR)
- [ ] Custom embedding models
- [ ] Database optimization and scaling

---

**Built with:** LangChain | Chroma | Google Gemini | Gradio
