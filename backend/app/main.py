from contextlib import asynccontextmanager

from fastapi import FastAPI

from .admin import router as admin_router
from .auth import router as auth_router
from .chat import router as chat_router
from .db import engine
from .errors import install_error_handlers
from .faq_index import faq_index, load_entries
from .stats import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the TF-IDF index from the FAQ table once at startup.
    # If the database is unreachable, startup fails loudly rather than answering from an empty index.
    if engine is not None:
        with engine.connect() as conn:
            faq_index.build(load_entries(conn))
    yield


app = FastAPI(title="Arc Lite API", version="0.1.0", lifespan=lifespan)
install_error_handlers(app)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(stats_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
