import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, corpus, debug, eval, formulations, health, kbs, sources, warehouse
from app.config import get_settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Pharma AI Service",
        version="0.1.0",
        description="RAG pipeline for cosmetic / pharma formulation Q&A.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(debug.router)
    app.include_router(formulations.router)
    app.include_router(kbs.router)
    app.include_router(corpus.router)
    app.include_router(eval.router)
    app.include_router(sources.router)
    app.include_router(warehouse.router)

    logging.getLogger(__name__).info(
        "ai-service booted (qdrant=%s, embed=%s, llm=%s @ %s)",
        settings.qdrant_url,
        settings.embed_model,
        settings.llm_model,
        settings.llm_base_url,
    )
    return app


app = create_app()
