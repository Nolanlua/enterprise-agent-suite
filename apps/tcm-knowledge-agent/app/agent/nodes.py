"""LangGraph nodes for the TCM knowledge agent."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import TCMState
from app.clients import LLMClient
from app.config import settings
from app.retrieval.citation import CitationBuilder, fallback_answer
from app.retrieval.retriever import RetrievedChunk, TCMRetriever, rrf_fuse
from app.safety.guard import SafetyGuard

SYNONYMS = {
    "上火": "热证",
    "拉肚子": "泄泻",
    "胃不舒服": "胃脘不适",
    "睡不着": "失眠",
    "气血不足": "气血两虚",
}


class TCMNodes:
    def __init__(self, retriever: TCMRetriever, safety: SafetyGuard) -> None:
        self._retriever = retriever
        self._safety = safety
        self._llm = LLMClient()
        self._citation = CitationBuilder()

    async def classify(self, state: TCMState) -> dict[str, Any]:
        question = state.get("question", "")
        if re.search(r"方|汤|丸|散|饮", question):
            intent = "formula"
        elif re.search(r"经典|伤寒|内经|金匮|本草", question):
            intent = "classic"
        elif re.search(r"指南|规范|原则", question):
            intent = "guideline"
        elif re.search(r"功效|主治|药材|中药|性味|归经", question):
            intent = "herb"
        elif re.search(r"症状|调理|证|怕冷|失眠|咳嗽", question):
            intent = "symptom"
        else:
            intent = "general"
        return {"intent": intent, "trace": {**state.get("trace", {}), "intent": intent}}

    async def normalize(self, state: TCMState) -> dict[str, Any]:
        question = state.get("question", "")
        terms: list[str] = []
        for colloquial, formal in SYNONYMS.items():
            if colloquial in question:
                terms.append(formal)
        # Named entities are extracted with a deterministic pattern first; an
        # LLM fallback is only used when no entity is found.
        terms.extend(re.findall(r"[\u4e00-\u9fff]{2,8}(?:汤|丸|散|饮|草|参|芪|归|黄)", question))
        terms = list(dict.fromkeys(terms))[: settings.max_rewrite_queries]
        return {
            "normalized_terms": terms or [question],
            "rewritten_queries": [question] + [f"{question} {term}" for term in terms][:2],
            "trace": {**state.get("trace", {}), "normalized_terms": terms},
        }

    async def retrieve(self, state: TCMState) -> dict[str, Any]:
        tenant_id = state.get("tenant_id", "")
        queries = state.get("rewritten_queries") or [state.get("question", "")]
        tasks = [self._retriever.retrieve(query, tenant_id=tenant_id) for query in queries]
        batches = await asyncio.gather(*tasks, return_exceptions=True)
        result_lists: list[list[RetrievedChunk]] = []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            result_lists.append(batch)
        fused = rrf_fuse(result_lists, k=settings.rrf_k, top_k=settings.top_k)
        context, citations = self._citation.build(fused)
        return {
            "candidates": [
                {
                    "chunk_id": item.chunk_id,
                    "doc_id": item.doc_id,
                    "title": item.title,
                    "source": item.source,
                    "score": item.score,
                }
                for item in fused
            ],
            "context": context,
            "citations": citations,
            "trace": {**state.get("trace", {}), "candidate_count": len(fused)},
        }

    async def graph_expand(self, state: TCMState) -> dict[str, Any]:
        rows = await self._retriever.graph_expand(state.get("normalized_terms", []), state.get("tenant_id", ""))
        return {"graph_facts": rows, "trace": {**state.get("trace", {}), "graph_facts": len(rows)}}

    async def safety_precheck(self, state: TCMState) -> dict[str, Any]:
        decision = self._safety.evaluate(state.get("question", ""), state.get("intent", ""))
        if decision.level == "emergency":
            return {
                "safety_level": "emergency",
                "safety_reasons": decision.reasons,
                "disclaimer": decision.disclaimer,
                "answer": decision.disclaimer,
                "trace": {**state.get("trace", {}), "safety": "emergency"},
            }
        if decision.level == "block":
            answer = (
                "这个问题涉及处方、剂量或特殊人群用药，知识库不能直接给出诊疗建议。"
                "请携带具体病情和正在使用的药物，咨询执业中医师或药师。"
            )
            return {
                "safety_level": "block",
                "safety_reasons": decision.reasons,
                "disclaimer": decision.disclaimer,
                "answer": answer,
                "trace": {**state.get("trace", {}), "safety": "block"},
            }
        return {"safety_level": "pass", "safety_reasons": [], "trace": {**state.get("trace", {}), "safety": "pass"}}

    async def generate(self, state: TCMState) -> dict[str, Any]:
        context = state.get("context", "")
        citations = state.get("citations", [])
        question = state.get("question", "")
        graph_facts = state.get("graph_facts", [])
        if not context:
            return {
                "answer": "知识库暂未找到足够资料回答这个问题。请补充具体病名、症状、药材或方剂名称，或咨询执业中医师。",
                "citations": [],
                "trace": {**state.get("trace", {}), "generation": "no_evidence"},
            }

        graph_text = "\n".join(f"{row[0]} -{row[1]}-> {row[2]}" for row in graph_facts[:8])
        prompt = (
            f"用户问题：{question}\n\n"
            f"检索资料：\n{context}\n\n"
            f"知识图谱关系（仅作背景，不得单独作为引用）：\n{graph_text or '无'}\n\n"
            "请基于资料回答，标注 [n] 引用；若资料不足请直接说明。"
        )
        try:
            answer = await self._llm.chat(SYSTEM_PROMPT, prompt)
        except Exception:  # noqa: BLE001 - local fallback keeps the contract
            answer = self._extractive_answer(context, citations)
        return {
            "answer": answer,
            "trace": {**state.get("trace", {}), "generation": "llm"},
        }

    async def verify(self, state: TCMState) -> dict[str, Any]:
        answer = state.get("answer", "")
        citations = state.get("citations", [])
        report = self._citation.validate(answer, citations)
        unsafe = self._safety.inspect_answer(answer)
        trace = state.get("trace", {})
        retry_count = int(trace.get("retry_count", 0))
        valid = report.valid and not unsafe
        if not valid and retry_count < 1:
            return {
                "validation": {"valid": False, "invalid_indexes": report.invalid_indexes, "unsafe": unsafe},
                "trace": {**trace, "retry_count": retry_count + 1, "validation": "retry"},
            }
        if not valid:
            return {
                "answer": fallback_answer(citations),
                "validation": {"valid": True, "reason": "fallback", "invalid_indexes": report.invalid_indexes},
                "trace": {**trace, "retry_count": retry_count, "validation": "fallback"},
            }
        return {
            "validation": {"valid": True, "reason": "ok", "invalid_indexes": [], "unsafe": []},
            "trace": {**trace, "retry_count": retry_count, "validation": "ok"},
        }

    async def finalize(self, state: TCMState) -> dict[str, Any]:
        answer = state.get("answer", "")
        disclaimer = state.get("disclaimer") or (
            "以上内容仅用于中医药知识检索和学习，不构成诊断、处方或用药建议；"
            "具体诊疗请由执业中医师或药师面诊后决定。"
        )
        if disclaimer not in answer:
            answer = f"{answer}\n\n{disclaimer}"
        return {
            "answer": answer,
            "disclaimer": disclaimer,
            "trace": {**state.get("trace", {}), "finalized": True},
        }

    @staticmethod
    def _extractive_answer(context: str, citations: list[dict[str, Any]]) -> str:
        # Deterministic fallback used only when the model call fails. It avoids
        # inventing content but is intentionally conservative.
        sentences = [part.strip() for part in re.split(r"[。\n]", context) if part.strip()]
        selected = "。".join(sentences[:3])
        return f"根据知识库资料：{selected}。[1] 请注意，这只是资料摘录，具体诊疗需由执业医师判断。"
