from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .errors import register_handlers
from .routes import analyze, me


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VietCalorie API",
        description="Estimate nutrition from food images using GPT-4o Vision.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_handlers(app)
    app.include_router(analyze.router)
    app.include_router(me.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
