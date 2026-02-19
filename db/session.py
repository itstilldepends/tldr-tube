"""
Database session and engine setup for tldr-tube.

Reads DATABASE_URL from environment variables and creates SQLAlchemy engine.
Provides Session factory and init_db() function.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from db.models import Base

# Load environment variables
load_dotenv()

# Get database URL from env, default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/tldr_tube.db")

# Create engine
# For SQLite: enable WAL mode for better concurrency
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False  # Set to True for SQL debugging
    )
    # Enable WAL mode for SQLite
    with engine.connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.commit()
else:
    # For PostgreSQL or other databases
    engine = create_engine(DATABASE_URL, echo=False)

# Session factory
Session = sessionmaker(bind=engine)


def init_db():
    """
    Initialize the database by creating all tables.

    This is idempotent - safe to run multiple times.
    Only creates tables that don't already exist.
    """
    Base.metadata.create_all(engine)
    print(f"✅ Database initialized at: {DATABASE_URL}")


def get_session():
    """
    Get a new database session.

    Usage:
        with get_session() as session:
            # do queries
            session.commit()

    Returns:
        SQLAlchemy Session instance
    """
    return Session()


if __name__ == "__main__":
    # For testing: python -m db.session
    init_db()
    print("Database tables created successfully!")
