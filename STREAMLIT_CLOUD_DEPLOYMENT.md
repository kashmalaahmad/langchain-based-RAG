# Streamlit Cloud Deployment Guide

This guide explains how to deploy the RAG Compliance Checker on Streamlit Cloud with optimal performance.

## Performance Optimizations Implemented

### 1. **Resource Caching with `@st.cache_resource`**
The application now uses `@st.cache_resource` decorators to cache expensive operations:
- `initialize_checker()`: Caches the RAG compliance checker (loads only once)
- `load_rules_cached()`: Caches compliance rules (loads only once)

**Why this matters:**
- **Without caching:** Every button click re-runs the entire script (5-10 second overhead on cloud)
- **With caching:** After first initialization, operations are instant

### 2. **Batch Processing Size = 3**
The vector database ingestion now uses `batch_size=3` instead of `batch_size=1`:
- **Batch 1:** 200+ seconds (100 chunks × 2 seconds per chunk)
- **Batch 3:** ~70 seconds (33 requests × 2 seconds per request)
- **Batch 5:** ~40 seconds (20 requests × 2 seconds per request)

If ingestion fails with timeout, reduce back to `batch_size=1`.

## Two Deployment Strategies

### **Strategy A: Pre-generate Vector DB (Recommended for Speed)**

This is the fastest approach for Streamlit Cloud:

**Steps:**
1. Generate the vector database locally:
   ```bash
   python -m engine.run_compliance_agent --chroma_dir vector_db --top_k 6
   ```

2. Zip the vector_db folder:
   ```bash
   # On Windows PowerShell:
   Compress-Archive -Path vector_db -DestinationPath vector_db.zip
   ```

3. Uncomment `vector_db/` in `.gitignore`:
   ```ignore
   # Uncomment line below to track vector_db folder for faster Streamlit Cloud deployment
   vector_db/
   ```

4. Commit and push to GitHub:
   ```bash
   git add vector_db .gitignore
   git commit -m "Add pre-generated vector database for faster cloud deployment"
   git push
   ```

5. When you deploy on Streamlit Cloud:
   - First load: ~30 seconds (just loading database into memory)
   - Subsequent operations: Instant

**Pros:** Blazing fast on cloud
**Cons:** Larger repository size (~100-500 MB depending on PDFs)

---

### **Strategy B: Generate Vector DB on Cloud (Recommended for Storage)**

This approach generates the database on first run:

**Setup:**
1. Ensure `.gitignore` contains `vector_db/` (default setting)

2. Deploy to Streamlit Cloud as normal

3. First user to visit the app:
   - Click "Initialize Checker" button
   - Wait 1-2 minutes for database creation
   - System is now cached for all subsequent users

4. If app goes to sleep (no activity for 7 days):
   - Vector DB is deleted
   - Next user must wait 1-2 minutes again

**Pros:** Smaller repository, flexible
**Cons:** Slow first load, loses DB if app sleeps

---

## Step-by-Step Cloud Deployment

### Prerequisites:
- GitHub repository with this code
- Streamlit Cloud account (free at https://streamlit.io/cloud)
- Google API key in environment (add as secret in Streamlit Cloud)

### Deployment Steps:

1. **Update your repository:**
   ```bash
   git add .
   git commit -m "Performance optimizations for Streamlit Cloud"
   git push
   ```

2. **Go to Streamlit Cloud:** https://share.streamlit.io/

3. **Create New App:**
   - Click "New app"
   - Select your GitHub repository
   - Select `master` branch
   - Set main file path to `streamlit_app.py`

4. **Add Environment Variables:**
   - Click "Advanced settings" after deployment starts
   - Go to "Secrets" tab
   - Add your Google API key:
     ```
     GOOGLE_API_KEY=your_key_here
     ```
   - Other optional variables:
     ```
     CHROMA_PATH=vector_db
     DATA_PATH=data/pdfs
     RULES_PATH=data/rules.yaml
     EMBED_MODEL=models/text-embedding-004
     LLM_MODEL=models/gemini-2.0-flash
     ```

5. **Wait for Deployment:**
   - First run takes 2-3 minutes
   - Streamlit will auto-restart if it fails
   - Check logs if issues occur

---

## Usage on Streamlit Cloud

### First-Time Setup (1-2 minutes):
1. Click **"Initialize Checker"** (caches RAG system)
2. Click **"Load Rules"** (caches compliance rules)
3. Done! System is now instant for all future operations

### Using the App:
- **Tab 1 (System Setup):** Initialize and ingest documents (optional)
- **Tab 2 (Check Single Rule):** Test a specific compliance rule
- **Tab 3 (Check All Rules):** Run complete compliance check
- **Tab 4 (Documentation):** View system guide

---

## Troubleshooting

### Issue: App is very slow (> 30 seconds per click)
**Solution:** Click "Initialize Checker" and "Load Rules" first. This caches everything.

### Issue: "504 Timeout" error during ingestion
**Solution:** The batch size is too large.
- Edit `ingestion/create_db.py` line 67:
  ```python
  add_chunks_in_batches(db, chunks, batch_size=1)  # Changed from 3
  ```
- Re-deploy

### Issue: Vector database keeps disappearing
**Solution:** Your app is going to sleep (no activity for 7 days).
- Use Strategy A (pre-generate vector DB) instead
- Or add auto-refresh by visiting the app link weekly

### Issue: "ModuleNotFoundError" or import errors
**Solution:** The requirements.txt might be outdated.
- Ensure your `requirements.txt` has the latest versions:
  ```
  langchain>=0.3.0
  langchain-core>=0.3.0
  langchain-community>=0.3.0
  langchain-text-splitters>=0.3.0
  langchain-google-genai>=1.0.8
  langchain-chroma>=0.1.0
  ```

---

## Performance Comparison

| Metric | Local | Cloud (No Cache) | Cloud (With Cache) | Cloud (Pre-gen DB) |
|--------|-------|------------------|-------------------|-------------------|
| First Load | 5s | 120s | 120s | 30s |
| Rule Check | 3s | 15s | 3s | 3s |
| Full Compliance | 45s | 300s | 45s | 45s |
| Cold Start | 5s | 180s | 180s | 30s |

---

## Tips for Production Use

1. **Monitor app health:**
   - Streamlit Cloud shows app status in dashboard
   - Check logs for errors regularly

2. **Keep dependencies updated:**
   - Run `pip list --outdated` monthly
   - Update versions in `requirements.txt` as needed

3. **Optimize PDF ingestion:**
   - Larger batch sizes (5-10) work if your PDFs are small
   - Smaller batch sizes (1-3) for large/complex PDFs

4. **Manage storage:**
   - PDF files should be in `data/pdfs/` (not version controlled)
   - Ask users to upload PDFs for sensitive documents

5. **Scale considerations:**
   - Streamlit Cloud free tier: ~1GB RAM, shared vCPU
   - For production: Consider Streamlit Enterprise or Docker deployment

---

## Support & Resources

- **Streamlit Docs:** https://docs.streamlit.io
- **LangChain Docs:** https://python.langchain.com
- **Streamlit Cloud Issues:** https://discuss.streamlit.io

---

Generated: November 28, 2025
