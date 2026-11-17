"""TCM knowledge agent FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from agent_common.errors import AppError, app_error_handler, unhandled_error_handler
from agent_common.logging import configure_logging
from app.api import router
from app.config import settings
from app.services.chat import ChatService


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.app_env, settings.log_level)
    app.state.chat_service = ChatService()
    yield


app = FastAPI(
    title="岐黄智库 · TCM Knowledge Agent",
    version="1.0.0",
    description="Enterprise TCM knowledge agent with hybrid retrieval, graph expansion, citations and safety guardrails.",
    lifespan=lifespan,
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(router)
app.mount("/metrics", make_asgi_app())
