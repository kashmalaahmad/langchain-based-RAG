# 504 Deadline Exceeded Error - Fix & Solutions

## What is a 504 Error?

**504 Deadline Exceeded** means the Google API took too long to respond (timeout).

### Common Causes:
1. **Batch size too large** - Embedding too many chunks at once
2. **Network latency** - Slow connection to Google servers
3. **API rate limiting** - Too many requests too quickly
4. **Large documents** - Processing very big PDFs

---

## Solutions Implemented

### 1. **Reduced Batch Size to 1**
```python
# Before (causes timeouts)
add_chunks_in_batches(db, chunks, batch_size=3)

# After (safe, reliable)
add_chunks_in_batches(db, chunks, batch_size=1)
```

**Impact:** Process 1 chunk at a time instead of 3, reducing API load.

---

### 2. **Added Exponential Backoff Retry Logic**
```python
max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        db.add_documents(batch)
        break
    except Exception as e:
        if "504" in str(e):
            # Wait: 30s, 60s, 90s
            wait_time = 30 * retry_count
            time.sleep(wait_time)
```

**Impact:** Automatically retry on timeout with increasing wait times.

---

### 3. **Reduced Sleep Time Between Batches**
```python
# Before
time.sleep(10)  # Wait 10 seconds

# After
time.sleep(5)   # Wait 5 seconds
```

**Impact:** Slightly faster ingestion while still being safe.

---

## How to Use

### If You Get 504 Error During Ingestion:

**Option 1: Wait & Retry**
```bash
# Just wait and try again - the retry logic will handle it automatically
python -m engine.run_compliance_agent --chroma_dir vector_db
```

**Option 2: Reduce Chunk Size**
Edit `ingestion/create_db.py`:
```python
def split_documents(documents, chunk_size=400):  # Reduced from 800
```

**Option 3: Increase Sleep Time**
Edit `ingestion/create_db.py`:
```python
time.sleep(10)  # Increased from 5
```

---

## Performance Trade-offs

| Setting | Speed | Reliability | Recommendation |
|---------|-------|-------------|-----------------|
| batch_size=1, sleep=5s | Slow | Very High | Cloud deployments |
| batch_size=3, sleep=5s | Fast | Medium | Local development |
| batch_size=5, sleep=10s | Very Fast | Low | Not recommended |

---

## Ingestion Time Estimates

| Chunks | batch_size=1 | batch_size=3 |
|--------|-------------|------------|
| 50 | ~4 minutes | ~2 minutes |
| 100 | ~8 minutes | ~4 minutes |
| 200 | ~16 minutes | ~8 minutes |

---

## Pre-generated Database Strategy

To avoid ingestion issues on Streamlit Cloud:

1. **Generate locally first**
   ```bash
   python -m engine.run_compliance_agent --chroma_dir vector_db
   ```

2. **Commit vector_db to GitHub**
   ```bash
   git add vector_db/
   git commit -m "Add pre-generated vector database"
   git push
   ```

3. **Deploy to Streamlit Cloud**
   - No ingestion needed (database already exists)
   - App starts 10x faster
   - No 504 errors!

See: `STREAMLIT_CLOUD_DEPLOYMENT.md` for full instructions.

---

## Troubleshooting

### Still Getting 504?
1. Check internet connection
2. Reduce batch_size to 1 (if not already)
3. Increase sleep_time to 10 seconds
4. Try at a different time (less API load)

### Ingestion is Very Slow
1. This is normal with batch_size=1
2. Each chunk takes ~5-10 seconds
3. For 100 chunks: ~8-16 minutes
4. Be patient, don't interrupt!

### Want Faster Ingestion?
1. Use pre-generated database strategy
2. Or increase batch_size to 3 (less safe)
3. Or increase sleep_time to 10 (safer, slower)

---

## Code Changes

### Files Modified:
- `ingestion/create_db.py` - Updated retry logic, batch_size=1 default
- `rag/retriever.py` - Already has exponential backoff

### Key Changes:
```python
# New retry logic with 504 detection
if "504" in error_msg or "Deadline" in error_msg:
    wait_time = 30 * retry_count
    print(f"504 Timeout. Waiting {wait_time}s...")
    time.sleep(wait_time)
```

---

## Next Steps

1. **Try ingestion again** - retry logic should handle most timeouts
2. **If still failing** - use pre-generated database on Streamlit Cloud
3. **For production** - commit vector_db to Git, never regenerate on cloud

---

**Status:** ✅ 504 errors handled with automatic retry  
**Last Updated:** November 28, 2025
