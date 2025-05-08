import os
from dotenv import load_dotenv
from fastapi import FastAPI
from modules import dev_router
from modules import famous_router
from logs.logs import configure_logging, LogLevels

load_dotenv()

prod = int(os.getenv("PROD", "0"))

configure_logging(log_level=LogLevels.debug if (prod == 0) else LogLevels.info)

PREFIX = os.getenv("PREFIX", "/relation_finder")

app = FastAPI(
    title="Famous Relationship Finder",
    description="Find famous people related to each other.",
    version="0.0.0",
    docs_url= f"{PREFIX}/docs",
    redoc_url= f"{PREFIX}/redoc",
    openapi_url= f"{PREFIX}/openapi.json",
)

app.include_router(dev_router, prefix=f"{PREFIX}/dev", tags=["dev"])
app.include_router(famous_router, prefix=f"{PREFIX}/famous", tags=["famous"])
