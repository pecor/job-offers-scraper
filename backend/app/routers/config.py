import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.schemas import Config

logger = logging.getLogger(__name__)
router = APIRouter()

# Config path - in Docker it's /config, locally it's in project root
if Path("/config").exists():
    CONFIG_PATH = Path("/config/config.json")
else:
    CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "search_keyword": "junior",
    "max_pages": 5,
    "delay": 1.0,
    "pracuj_pl_domain": "it",
    "excluded_keywords": [],
    "schedule": "daily",
    "sources": ["pracuj_pl"],
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(config)
            return merged
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Configuration saved to {CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving config: {e}")


@router.get("/config", response_model=Config)
async def get_config():
    return load_config()


@router.put("/config", response_model=Config)
async def update_config(config: Config):
    config_dict = config.model_dump()
    save_config(config_dict)
    return config_dict
