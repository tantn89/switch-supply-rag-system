"""FastAPI entrypoint for the Switch Supply Procurement RAG backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.lifespan import lifespan
from app.routes import chat as chat_route
from app.routes import health as health_route
from app.routes import upload as upload_route
from app.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Switch Supply Procurement RAG",
    version="0.1.0",
    description="Multi-source RAG assistant for procurement queries.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_route.router, tags=["meta"])
app.include_router(chat_route.router, prefix="/chat", tags=["chat"])
app.include_router(upload_route.router, prefix="/upload", tags=["upload"])
