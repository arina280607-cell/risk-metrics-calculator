import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import Connection
from psycopg.rows import dict_row


PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")


def get_connection() -> Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "risk_metrics"),
        user=os.getenv("POSTGRES_USER", "risk_user"),
        password=os.getenv("POSTGRES_PASSWORD", "risk_password"),
        row_factory=dict_row,
        connect_timeout=5,
    )
