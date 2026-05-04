"""LLM-powered claim extraction + RAG verification over retrieved KB context."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

try:
    from litellm import completion
except Exception:  # pragma: no cover
    completion = None

from .truth_service import verify_claims

DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


def _fallback_extract_claims(text: str, max_claims: int = 8) -> List[str]:
    chunks = [c.strip() for c in re.split(r"[.!?]\s+", text) if c.strip()]
    return chunks[:max_claims]


def _llm_json(messages: List[Dict[str, str]], model: str) -> Dict[str, Any] | None:
    if completion is None:
        return None

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    response = completion(
        model=model,
        api_key=api_key,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
        timeout=30,
    )
    content = (response.choices[0].message.content or "").strip()
    return json.loads(content) if content else None


def extract_verifiable_claims(text: str, model: str = DEFAULT_LLM_MODEL, max_claims: int = 8) -> List[str]:
    prompt = [
        {
            "role": "system",
            "content": (
                "Extract distinct, factual, verifiable claims from the user text. "
                "Return strict JSON: {\"claims\": [\"...\"]}. "
                "Do not include opinions, instructions, or duplicate claims."
            ),
        },
        {"role": "user", "content": text},
    ]
    parsed = _llm_json(prompt, model=model)
    if not parsed or not isinstance(parsed.get("claims"), list):
        return _fallback_extract_claims(text, max_claims=max_claims)

    claims = [str(c).strip() for c in parsed["claims"] if str(c).strip()]
    if not claims:
        return _fallback_extract_claims(text, max_claims=max_claims)
    return claims[:max_claims]


def _verify_claim_with_context(
    claim: str,
    contexts: List[Dict[str, Any]],
    model: str = DEFAULT_LLM_MODEL,
) -> Dict[str, Any]:
    if not contexts:
        return {
            "claim": claim,
            "verdict": "Unverifiable",
            "reasoning": "No supporting context was retrieved from the knowledge base.",
            "source_text": "",
            "source_title": None,
            "source": None,
            "similarity": 0.0,
        }

    context_block = []
    for idx, item in enumerate(contexts, start=1):
        context_block.append(
            f"[DOC {idx}] title={item.get('title')} source={item.get('source')} "
            f"similarity={item.get('similarity')}\n{item.get('content', '')}"
        )
    context_text = "\n\n".join(context_block)

    prompt = [
        {
            "role": "system",
            "content": (
                "You are a strict fact-checker. Use ONLY the provided context. "
                "Never use outside knowledge. "
                "Return strict JSON with keys: "
                "{\"verdict\":\"Supported|Contradicted|Unverifiable\","
                "\"reasoning\":\"...\","
                "\"source_doc\":1,"
                "\"source_text\":\"exact supporting or contradicting quote\"}."
            ),
        },
        {
            "role": "user",
            "content": f"Claim:\n{claim}\n\nContext documents:\n{context_text}",
        },
    ]
    parsed = _llm_json(prompt, model=model)

    if not parsed:
        top = contexts[0]
        # deterministic fallback when LLM isn't configured
        return {
            "claim": claim,
            "verdict": "Unverifiable",
            "reasoning": "LLM verification unavailable; similarity-only fallback applied.",
            "source_text": (top.get("content") or "")[:220],
            "source_title": top.get("title"),
            "source": top.get("source"),
            "similarity": float(top.get("similarity", 0.0)),
        }

    verdict = str(parsed.get("verdict", "Unverifiable")).strip().title()
    if verdict not in {"Supported", "Contradicted", "Unverifiable"}:
        verdict = "Unverifiable"

    src_idx = parsed.get("source_doc", 1)
    try:
        src_idx_int = int(src_idx)
    except Exception:
        src_idx_int = 1
    src_idx_int = min(max(src_idx_int, 1), len(contexts))
    src = contexts[src_idx_int - 1]

    return {
        "claim": claim,
        "verdict": verdict,
        "reasoning": str(parsed.get("reasoning", "")).strip() or "No reasoning provided.",
        "source_text": str(parsed.get("source_text", "")).strip() or (src.get("content", "")[:220]),
        "source_title": src.get("title"),
        "source": src.get("source"),
        "similarity": float(src.get("similarity", 0.0)),
    }


async def verify_text_with_llm_rag(text: str, top_k: int = 3, model: str = DEFAULT_LLM_MODEL) -> Dict[str, Any]:
    claims = extract_verifiable_claims(text, model=model)
    if not claims:
        return await verify_claims(text, top_k=top_k)

    claim_citations: List[Dict[str, Any]] = []
    groundedness_values: List[float] = []
    verdict_values: List[float] = []
    flat_citations: List[Dict[str, Any]] = []

    verdict_score = {"Supported": 1.0, "Contradicted": 0.0, "Unverifiable": 0.4}

    for claim in claims:
        retrieval = await verify_claims(claim, top_k=top_k)
        contexts = retrieval.get("retrieved_context", [])
        groundedness = float(retrieval.get("groundedness", 0.0))
        groundedness_values.append(groundedness)

        decision = _verify_claim_with_context(claim, contexts, model=model)
        decision["retrieved_context"] = contexts
        decision["groundedness"] = round(groundedness, 4)
        claim_citations.append(decision)
        verdict_values.append(verdict_score.get(decision["verdict"], 0.4))

        flat_citations.append(
            {
                "title": decision.get("source_title"),
                "source": decision.get("source"),
                "snippet": decision.get("source_text", "")[:220],
                "similarity": round(float(decision.get("similarity", 0.0)), 4),
                "claim": claim,
                "verdict": decision.get("verdict"),
                "reasoning": decision.get("reasoning"),
                "source_text": decision.get("source_text"),
            }
        )

    avg_groundedness = sum(groundedness_values) / len(groundedness_values) if groundedness_values else 0.0
    avg_verdict = sum(verdict_values) / len(verdict_values) if verdict_values else 0.4
    truth_score = min(max((0.4 * avg_groundedness) + (0.6 * avg_verdict), 0.0), 1.0)

    return {
        "truth_score": round(truth_score, 4),
        "groundedness": round(avg_groundedness, 4),
        "citations": flat_citations[:20],
        "claim_citations": claim_citations,
        "retrieved_context": [cc.get("retrieved_context", []) for cc in claim_citations],
        "claims": claims,
        "verification_mode": "llm_rag",
        "llm_model": model,
    }


async def verify_single_claim_with_llm_rag(claim: str, top_k: int = 3, model: str = DEFAULT_LLM_MODEL) -> Dict[str, Any]:
    """Verify one claim with retrieval + LLM verdict."""
    retrieval = await verify_claims(claim, top_k=top_k)
    contexts = retrieval.get("retrieved_context", [])
    groundedness = float(retrieval.get("groundedness", 0.0))
    decision = _verify_claim_with_context(claim, contexts, model=model)
    decision["retrieved_context"] = contexts
    decision["groundedness"] = round(groundedness, 4)

    verdict_score = {"Supported": 1.0, "Contradicted": 0.0, "Unverifiable": 0.4}
    truth_score = min(max((0.4 * groundedness) + (0.6 * verdict_score.get(decision["verdict"], 0.4)), 0.0), 1.0)

    return {
        "truth_score": round(truth_score, 4),
        "groundedness": round(groundedness, 4),
        "citations": [
            {
                "title": decision.get("source_title"),
                "source": decision.get("source"),
                "snippet": decision.get("source_text", "")[:220],
                "similarity": round(float(decision.get("similarity", 0.0)), 4),
                "claim": claim,
                "verdict": decision.get("verdict"),
                "reasoning": decision.get("reasoning"),
                "source_text": decision.get("source_text"),
            }
        ],
        "claim_citations": [decision],
        "claims": [claim],
        "verification_mode": "llm_rag",
        "llm_model": model,
    }
