import re
import json
from typing import Dict, Any, List
from rag.retriever import ChromaRetriever
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
load_dotenv()

TOP_K = int(os.getenv("TOP_K", 6))
FALLBACK_K = int(os.getenv("FALLBACK_K", 12))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.65))
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", 0.6))
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5")

PROMPT_TEMPLATE = """
SYSTEM: You are a compliance auditor. Use ONLY the context passages below to decide if the rule is satisfied.
Return EXACTLY one JSON object and NOTHING else.

INPUT:
Rule ID: {rule_id}
Rule Name: {rule_name}
Description: {rule_description}
Obligation: {obligation_type}
Severity: {severity}

Context Passages:
{context_block}

INSTRUCTIONS:
- Based ONLY on the context, set "status" to exactly one of: "Compliant", "Non-Compliant", or "Not Applicable".
- Provide an array "evidence" of objects with keys "text" (short excerpt) and "source" (filename:page:start_index or available metadata).
- Provide "confidence" as a float between 0.0 and 1.0.
- If Non-Compliant, include up to 3 actionable "recommended_corrections".
- If context does not contain relevant text, say "no evidence" inside evidence (and set confidence low).
- Do NOT hallucinate facts.

Return JSON like:
{{
  "rule_id": "<RULE_XXX>",
  "status": "Compliant" | "Non-Compliant" | "Not Applicable",
  "evidence": [{{"text":"...", "source":"..."}}],
  "confidence": 0.00,
  "recommended_corrections": ["..."]
}}
"""

class RAGComplianceChecker:
    def __init__(self, chroma_dir: str = "vector_db/chroma", embed_model: str = "models/text-embedding-004", llm_model: str = LLM_MODEL):
        self.retriever = ChromaRetriever(chroma_dir=chroma_dir, embed_model=embed_model)
        self.model = ChatGoogleGenerativeAI(model=llm_model)

    def _format_context(self, results) -> str:
        pieces = []
        for doc, score in results:
            meta = doc.metadata or {}
            source = meta.get("source", meta.get("source_file", "unknown"))
            page = meta.get("page", meta.get("page_number", ""))
            start = meta.get("start_index", "")
            src_id = f"{source}:{page}:{start}"
            excerpt = doc.page_content.strip().replace("\n", " ")
            excerpt_short = excerpt[:1000]
            pieces.append(f"[DOC: {src_id} | score:{score:.3f}]\n\"{excerpt_short}\"")
        return "\n\n".join(pieces) if pieces else "No retrieved passages."

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            json_text = re.search(r"\{.*\}", text, flags=re.DOTALL).group(0)
            parsed = json.loads(json_text)
            return parsed
        except Exception:
            return None

    def check_rule(self, rule: Dict[str, Any], top_k: int = TOP_K) -> Dict[str, Any]:
        query_terms = []
        if rule.get("keywords"):
            query_terms += rule.get("keywords", [])[:10]
        if rule.get("required_phrases"):
            query_terms += rule.get("required_phrases", [])[:10]
        if not query_terms:
            query = rule.get("name", "")
        else:
            query = " ".join(query_terms)

        results = self.retriever.retrieve(query, k=top_k)
        top_score = results[0][1] if results else 0.0
        evidence_low = (top_score < SIM_THRESHOLD)

        if evidence_low:
            results = self.retriever.retrieve(query, k=FALLBACK_K)

        context_block = self._format_context(results)
        prompt = PROMPT_TEMPLATE.format(
            rule_id=rule.get("id"),
            rule_name=rule.get("name"),
            rule_description=rule.get("description", ""),
            obligation_type=rule.get("obligation_type", ""),
            severity=rule.get("severity", ""),
            context_block=context_block
        )

        model_output = self.model.invoke(prompt)
        model_output_str = str(model_output.content) if hasattr(model_output, 'content') else str(model_output)
        parsed = self._extract_json(model_output_str)

        if not parsed:
            parsed = {
                "rule_id": rule.get("id"),
                "status": "Non-Compliant",
                "evidence": [{"text": "No reliable evidence found in retrieved passages", "source": ""}],
                "confidence": 0.15,
                "recommended_corrections": [f"Add explicit clause for: {rule.get('name')}"]
            }

        parsed["_retrieval"] = {
            "query": query,
            "top_score": float(top_score),
            "num_retrieved": len(results),
            "evidence_low": evidence_low,
        }
        parsed["_raw_model_output"] = model_output_str
        parsed["_retrieved_docs"] = [
            {"source": (d.metadata.get("source") or ""), "page": d.metadata.get("page", ""), "score": s}
            for d, s in results
        ]
        return parsed
