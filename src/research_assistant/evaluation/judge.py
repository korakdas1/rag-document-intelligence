"""Optional LLM-as-judge. Separate evaluator_id from generation llm_id.

Not ground truth. Deterministic tests should stub the client.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from research_assistant.generation.identity import LLMIdentity
from research_assistant.generation.models import ChatMessage, LLMRequest
from research_assistant.generation.protocol import LLMClient

JUDGE_RUBRIC_VERSION = "judge.v1"

SYSTEM = """You are an evaluator, not the answering assistant.
Score the model answer using ONLY the provided evidence.
Return JSON:
{"relevance": 0|1|2, "faithfulness": "unsupported"|"partial"|"full", "notes": "short"}
relevance: 0 does not address the question, 1 partial, 2 directly answers.
faithfulness: whether claims are supported by the evidence text.
Do not treat citation IDs as proof of support."""


def evaluator_id(identity: LLMIdentity) -> str:
    payload = json.dumps(
        {
            "role": "evaluator",
            "rubric": JUDGE_RUBRIC_VERSION,
            "llm_id": identity.llm_id,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"eval-{identity.model_name.rsplit('/', 1)[-1]}:{digest}"


def judge_answer(
    client: LLMClient,
    *,
    question: str,
    answer_text: str,
    evidence_text: str,
) -> dict[str, Any]:
    request = LLMRequest(
        messages=(
            ChatMessage(role="system", content=SYSTEM),
            ChatMessage(
                role="user",
                content=(
                    f"<question>\n{question}\n</question>\n"
                    f"<answer>\n{answer_text}\n</answer>\n"
                    f"<evidence>\n{evidence_text}\n</evidence>"
                ),
            ),
        ),
        identity=client.identity,
        allowed_citation_ids=(),
    )
    response = client.generate(request)
    parsed = _parse(response.text)
    parsed["evaluator_id"] = evaluator_id(client.identity)
    parsed["rubric"] = JUDGE_RUBRIC_VERSION
    parsed["raw"] = response.text
    return parsed


def _parse(raw: str) -> dict[str, Any]:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    payload: dict[str, Any] = {}
    if start >= 0 and end > start:
        try:
            loaded = json.loads(text[start : end + 1])
            if isinstance(loaded, dict):
                payload = loaded
        except json.JSONDecodeError:
            payload = {}
    relevance = payload.get("relevance")
    faithfulness = payload.get("faithfulness")
    return {
        "relevance": relevance if relevance in {0, 1, 2} else None,
        "faithfulness": faithfulness
        if faithfulness in {"unsupported", "partial", "full"}
        else None,
        "notes": payload.get("notes") if isinstance(payload.get("notes"), str) else "",
    }
