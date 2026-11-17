"""HTTP API for the TCM knowledge agent."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from agent_common.context import Principal
from agent_common.security import get_principal
from app.schemas import ChatRequest, ChatResponse, CitationOut, SearchHit, SearchRequest
from app.services.chat import ChatService

router = APIRouter()


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "tcm-knowledge-agent"}


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    result = await service.ask(
        question=payload.question,
        tenant_id=principal.tenant_id,
        conversation_id=payload.conversation_id,
        history=payload.history,
    )
    return ChatResponse(
        conversation_id=payload.conversation_id or result.trace.get("thread_id", ""),
        answer=result.answer,
        citations=[CitationOut.model_validate(item) for item in result.citations],
        intent=result.intent,
        safety=result.safety,
        latency_ms=result.latency_ms,
        trace=result.trace,
    )


@router.post("/v1/tcm/search", response_model=list[SearchHit])
async def search(
    payload: SearchRequest,
    principal: Annotated[Principal, Depends(get_principal)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> list[SearchHit]:
    chunks = await service._retriever.retrieve(payload.query, tenant_id=principal.tenant_id, top_k=payload.top_k)
    return [
        SearchHit(
            chunk_id=item.chunk_id,
            doc_id=item.doc_id,
            title=item.title,
            source=item.source,
            text=item.text,
            score=item.score,
        )
        for item in chunks
    ]
