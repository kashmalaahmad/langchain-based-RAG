# Gradio Frontend for RAG Compliance Checker

A user-friendly web interface for the RAG-based compliance checking system.

## Quick Start

### 1. Install Gradio
```sh
pip install gradio
```

Or install all requirements:
```sh
pip install -r requirements.txt
```

### 2. Run the Application
```sh
python app.py
```

The application will start at `http://localhost:7860`

## Features

### System Setup Tab
- **Ingest PDFs**: Load documents from `data/pdfs` into the vector database
- **Initialize System**: Set up the RAG compliance checker
- **Load Rules**: Load compliance rules from `data/rules.yaml`

### Check Single Rule Tab
- Select a specific compliance rule from the dropdown
- Adjust the number of retrieved documents (Top K)
- View detailed results with evidence and recommendations

### Check All Rules Tab
- Run compliance check on all rules at once
- View summary statistics
- Download reports in multiple formats:
  - **CSV**: For spreadsheet analysis
  - **Markdown**: For documentation
  - **JSON**: For programmatic access

### Documentation Tab
- Complete usage guide
- Configuration reference
- Rule format explanation
- System architecture overview

## UI Components

### Rule Selector
- Dropdown list of all loaded rules
- Format: `RULE_ID - Rule Name`
- Automatically updates when rules are loaded

### Top K Slider
- Range: 1-20 documents
- Default: 6
- Controls how many documents are retrieved for each rule check

### Status Indicators
- Real-time feedback for all operations
- Success and error messages

### Download Files
- Reports automatically saved to `reports/` directory
- Direct download links after batch check completes

## Workflow Example

1. **Setup**
   - Click "Ingest PDFs" to load documents
   - Click "Initialize System" to set up the checker
   - Click "Load Rules" to load compliance rules

2. **Single Check**
   - Go to "Check Single Rule" tab
   - Select a rule
   - Click "Check Rule"
   - View results with evidence

3. **Batch Check**
   - Go to "Check All Rules" tab
   - Adjust Top K if needed
   - Click "Run Compliance Check"
   - Download all reports

## Output Files

After running checks, files are saved to `reports/`:

- `compliance_report.csv`: Spreadsheet format
- `compliance_report.md`: Markdown format (great for GitHub)
- `compliance_report.json`: Raw JSON data

## Configuration

Edit `.env` file to customize:

```env
GOOGLE_API_KEY=your_api_key_here
CHROMA_PATH=vector_db
DATA_PATH=data/pdfs
EMBED_MODEL=models/text-embedding-004
LLM_MODEL=gemini-1.5-flash
```

## API Keys

You need a Google Generative AI API key. Get one at:
https://makersuite.google.com/app/apikey

## Troubleshooting

**"Checker not initialized"**
- Click "Initialize System" first

**"Rules not loaded"**
- Click "Load Rules" first

**"No documents ingested"**
- Click "Ingest PDFs" and ensure PDFs are in `data/pdfs/`

**Port already in use**
- Change port: `python app.py --port 7861`

## Advanced Usage

### Custom Port
```sh
python -c "from app import demo; demo.launch(server_port=8000)"
```

### Remote Access
```sh
python -c "from app import demo; demo.launch(server_name='0.0.0.0', share=True)"
```

### Disable Browser Launch
```sh
python -c "from app import demo; demo.launch(share=False)"
```

## Performance Tips

- Start with smaller Top K values (3-6) for faster results
- Use batch checks for comprehensive audits
- Reviews results in JSON for detailed analysis

## Support

For issues or questions, check:
- System logs in terminal
- Error messages in the UI
- Configuration in `.env`
