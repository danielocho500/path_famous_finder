import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from modules import dev_router
from modules import famous_router
from logs.logs import configure_logging, LogLevels
from database.neo4j_service import driver
from modules.graph.routes import router as graph_router, repo as graph_repo

prod = int(os.getenv("PROD", "0"))

configure_logging(log_level=LogLevels.debug if (prod == 0) else LogLevels.info)

PREFIX = os.getenv("PREFIX", "/relation_finder")
PREFIX = "/" + PREFIX.strip("/") if PREFIX.strip("/") else ""
WEB_DIR = Path(__file__).parent / "web"

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        driver.verify_connectivity()
        graph_repo.ensure_schema()
        yield
    finally:
        driver.close()

app = FastAPI(
    title="Famous Relationship Finder",
    description="Find famous people related to each other.",
    version="0.5.0",
    docs_url= f"{PREFIX}/docs",
    redoc_url= f"{PREFIX}/redoc",
    openapi_url= f"{PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.include_router(dev_router, prefix=f"{PREFIX}/dev", tags=["dev"])
app.include_router(famous_router, prefix=f"{PREFIX}/famous", tags=["famous"])
app.include_router(graph_router, prefix=f"{PREFIX}/api/v1", tags=["graph editor"])
app.mount(f"{PREFIX}/static", StaticFiles(directory=WEB_DIR), name="editor-static")


NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


@app.get(f"{PREFIX}/editor", include_in_schema=False)
def editor():
    return FileResponse(WEB_DIR / "editor.html", headers=NO_CACHE_HEADERS)


@app.get(f"{PREFIX}/finder", include_in_schema=False)
def finder_page():
    return FileResponse(WEB_DIR / "finder.html", headers=NO_CACHE_HEADERS)


@app.get(f"{PREFIX}/", include_in_schema=False)
def finder_home():
    return FileResponse(WEB_DIR / "finder.html", headers=NO_CACHE_HEADERS)


if PREFIX:
    @app.get("/", include_in_schema=False)
    def root_redirect():
        return RedirectResponse(f"{PREFIX}/", headers=NO_CACHE_HEADERS)


