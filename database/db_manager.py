import sqlite3
import logging
from pathlib import Path
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: str = "data/job_offers.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    description TEXT,
                    technologies TEXT,
                    salary_min REAL,
                    salary_max REAL,
                    salary_period TEXT,
                    work_type TEXT,
                    contract_type TEXT,
                    employment_type TEXT,
                    valid_until DATE,
                    source TEXT NOT NULL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def offer_exists(self, url: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM job_offers WHERE url = ?", (url,))
            return cursor.fetchone() is not None

    def insert_offer(self, offer_data: dict[str, Any]) -> bool:
        url = offer_data.get('url')
        if not url:
            logger.error("Cannot insert offer without URL")
            return False

        if self.offer_exists(url):
            logger.debug(f"Offer already exists: {url}")
            return False

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO job_offers (
                        url, title, company, location, description,
                        technologies, salary_min, salary_max, salary_period,
                        work_type, contract_type, employment_type, valid_until, source, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    offer_data.get('url'),
                    offer_data.get('title', ''),
                    offer_data.get('company'),
                    offer_data.get('location'),
                    offer_data.get('description'),
                    offer_data.get('technologies'),
                    offer_data.get('salary_min'),
                    offer_data.get('salary_max'),
                    offer_data.get('salary_period'),
                    offer_data.get('work_type'),
                    offer_data.get('contract_type'),
                    offer_data.get('employment_type'),
                    offer_data.get('valid_until'),
                    offer_data.get('source'),
                    datetime.now().isoformat()
                ))
                conn.commit()
                logger.info(f"Inserted offer: {offer_data.get('title', url)}")
                return True
        except sqlite3.IntegrityError:
            logger.debug(f"Duplicate offer: {url}")
            return False
        except Exception as e:
            logger.error(f"Error inserting offer: {e}")
            return False

    def get_offers(self, limit: int | None = None, source: str | None = None) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM job_offers"
            params = []

            if source:
                query += " WHERE source = ?"
                params.append(source)

            query += " ORDER BY scraped_at DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]