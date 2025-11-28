import re
import json
from typing import Dict, Any, List
from rag.retriever import ChromaRetriever
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
load_dotenv()

TOP_K = int(os.getenv("TOP_K", 6))
FALLBACK_K = int(os.getenv("FALLBACK_K", 8))  # Reduced from 12
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.65))
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", 0.6))
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")  # Changed to faster model

PROMPT_TEMPLATE = """You are a compliance auditor. Analyze the rule against the provided context ONLY.
Return EXACTLY one valid JSON object with no other text.

Rule ID: {rule_id}
Rule: {rule_name}
Description: {rule_description}

Context:
{context_block}

Respond with this JSON structure (no markdown, no explanation):
{{
  "rule_id": "{rule_id}",
  "status": "Compliant",
  "evidence": [{{"text": "relevant excerpt", "source": "document name"}}],
  "confidence": 0.85,
  "recommended_corrections": ["action item if needed"]
}}
"""

class RAGComplianceChecker:
    def __init__(self, chroma_dir: str = "vector_db/chroma", embed_model: str = "models/text-embedding-004", llm_model: str = LLM_MODEL):
        self.retriever = ChromaRetriever(chroma_dir=chroma_dir, embed_model=embed_model)
        self.model = ChatGoogleGenerativeAI(model=llm_model, temperature=0.1)

    def _format_context(self, results) -> str:
        pieces = []
        for doc, score in results:
            meta = doc.metadata or {}
            source = meta.get("source", meta.get("source_file", "unknown"))
            excerpt = doc.page_content.strip().replace("\n", " ")[:500]  # Shorter excerpts
            pieces.append(f"[{source}] {excerpt}")
        return "\n".join(pieces) if pieces else "No passages found."

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            json_text = re.search(r"\{.*\}", text, flags=re.DOTALL).group(0)
            parsed = json.loads(json_text)
            return parsed
        except Exception:
            return None

    def check_rule(self, rule: Dict[str, Any], top_k: int = TOP_K) -> Dict[str, Any]:
        # Build query
        query_terms = []
        if rule.get("keywords"):
            query_terms += rule.get("keywords", [])[:5]  # Fewer keywords
        if rule.get("required_phrases"):
            query_terms += rule.get("required_phrases", [])[:5]
        query = " ".join(query_terms) if query_terms else rule.get("name", "")

        # Retrieve documents
        results = self.retriever.retrieve(query, k=top_k)
        top_score = results[0][1] if results else 0.0
        evidence_low = (top_score < SIM_THRESHOLD)

        # Fallback only if needed
        if evidence_low and len(results) < top_k:
            fallback_results = self.retriever.retrieve(query, k=FALLBACK_K)
            if fallback_results:
                results = fallback_results

        context_block = self._format_context(results)
        prompt = PROMPT_TEMPLATE.format(
            rule_id=rule.get("id"),
            rule_name=rule.get("name"),
            rule_description=rule.get("description", ""),
            context_block=context_block
        )

        # Call LLM
        model_output = self.model.invoke(prompt)
        model_output_str = str(model_output.content) if hasattr(model_output, 'content') else str(model_output)
        parsed = self._extract_json(model_output_str)

        # Fallback if parsing fails
        if not parsed:
            parsed = {
                "rule_id": rule.get("id"),
                "status": "Not Applicable",
                "evidence": [],
                "confidence": 0.0,
                "recommended_corrections": []
            }

        # Add metadata
        parsed["_retrieval"] = {
            "query": query,
            "top_score": float(top_score),
            "num_retrieved": len(results),
        }
        return parsed
