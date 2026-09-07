# FastAPI application entrypoint: sets CORS and security headers and mounts the versioned API routers.

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import auth, meetings, chat, workspaces

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if settings.ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(auth.router, prefix="/api/v1")
app.include_router(meetings.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
