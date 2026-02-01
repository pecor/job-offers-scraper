import logging
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database import engine, Base

if Path("/scrapers").exists():
    sys.path.insert(0, "/")
else:
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

from app.routers import offers, config, scrape, technologies

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Job Offers Scraper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(offers.router, prefix="/api", tags=["offers"])
app.include_router(config.router, prefix="/api", tags=["config"])
app.include_router(scrape.router, prefix="/api", tags=["scrape"])
app.include_router(technologies.router, prefix="/api", tags=["technologies"])


@app.get("/")
async def root():
    return {"message": "Job Offers Scraper API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
