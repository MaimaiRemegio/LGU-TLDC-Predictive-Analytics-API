"""
Read-only MySQL database connection for the LGU-TLDC Predictive Analytics API.

The connection settings come from environment variables.

"""

import os
from pathlib import Path

import pandas as pd
import pymysql
from dotenv import load_dotenv


# Load .env from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _get_required_env(name: str) -> str:
    """Return a required environment variable."""
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Add it to the project's .env file."
        )

    return value


def get_connection():
    """
    Open a read-only application connection to MySQL.

    The database credentials are never hard-coded in source code.
    """
    host = _get_required_env("DB_HOST")
    database = _get_required_env("DB_NAME")
    username = _get_required_env("DB_USER")
    password = _get_required_env("DB_PASSWORD")

    port = int(os.getenv("DB_PORT", "3306"))

    return pymysql.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )


def read_sql(query: str, params=None) -> pd.DataFrame:
    """
    Execute a read-only SQL query and return the result as a DataFrame.

    Only SELECT statements are accepted.
    """

    normalized = query.strip().lower()

    if not normalized.startswith("select"):
        raise ValueError(
            "read_sql() only permits SELECT queries. "
            "Database modification queries are blocked."
        )

    connection = get_connection()

    try:
        return pd.read_sql_query(
            query,
            connection,
            params=params,
        )
    finally:
        connection.close()