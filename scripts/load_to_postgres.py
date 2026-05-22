"""
load_to_postgres.py
-------------------
Loads the processed telematics dataset into PostgreSQL.
Credentials are read from environment variables (never hardcoded).

Usage:
    export DB_USER=postgres
    export DB_PASSWORD=yourpassword
    export DB_HOST=localhost
    export DB_PORT=5432
    export DB_NAME=fleetdb
    python scripts/load_to_postgres.py
"""

import os
import pandas as pd
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

# --------------------------------------------------
# CONFIG FROM ENVIRONMENT
# --------------------------------------------------

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fleetdb")

TABLE_NAME = "fleet_telematics"
DATA_PATH  = "data/processed/processed_telematics.csv"
CHUNK_SIZE = 10_000

# --------------------------------------------------
# CONNECT
# --------------------------------------------------

conn_str = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
log.info(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}...")

try:
    engine = create_engine(conn_str, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("Database connection OK.")
except Exception as e:
    log.error(f"Cannot connect to database: {e}")
    raise SystemExit(1)

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

log.info(f"Reading {DATA_PATH}...")
df = pd.read_csv(DATA_PATH)
log.info(f"Loaded {len(df):,} rows × {df.shape[1]} columns")

# --------------------------------------------------
# PUSH IN CHUNKS (avoids memory issues on large files)
# --------------------------------------------------

total_chunks = (len(df) // CHUNK_SIZE) + 1
log.info(f"Writing to PostgreSQL table '{TABLE_NAME}' in {total_chunks} chunks...")

for i, chunk_start in enumerate(range(0, len(df), CHUNK_SIZE)):
    chunk = df.iloc[chunk_start : chunk_start + CHUNK_SIZE]
    if_exists = "replace" if i == 0 else "append"
    chunk.to_sql(
        TABLE_NAME,
        engine,
        if_exists=if_exists,
        index=False,
        method="multi"
    )
    log.info(f"  Chunk {i+1}/{total_chunks} written ({len(chunk):,} rows)")

log.info(f"All data loaded into '{TABLE_NAME}' successfully.")

# --------------------------------------------------
# VERIFY
# --------------------------------------------------

with engine.connect() as conn:
    result = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}"))
    count = result.scalar()
    log.info(f"Verification: {count:,} rows in '{TABLE_NAME}'")
