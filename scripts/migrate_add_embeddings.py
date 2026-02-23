"""
Add embedding column to videos table for semantic search.

This migration is SAFE:
- Only adds new column (embedding)
- Does not delete or modify existing data
- Existing videos will have embedding = NULL
- New videos will automatically get embeddings
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import engine, get_session
from db.models import Base, Video
from sqlalchemy import inspect, text

def check_column_exists():
    """Check if embedding column already exists."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('videos')]
    return 'embedding' in columns

def migrate():
    """Add embedding column to videos table."""

    print("="*60)
    print("Migration: Add embedding column for semantic search")
    print("="*60)
    print()

    # Check if already migrated
    if check_column_exists():
        print("✅ Migration already applied!")
        print("   'embedding' column already exists in videos table")

        # Show stats
        print()
        print("📊 Current state:")
        with get_session() as session:
            video_count = session.query(Video).count()
            videos_with_embeddings = session.query(Video).filter(
                Video.embedding.isnot(None)
            ).count()
            print(f"   Videos in database: {video_count}")
            print(f"   Videos with embeddings: {videos_with_embeddings}")
            print(f"   Videos without embeddings: {video_count - videos_with_embeddings}")
        return

    print("📊 Current state:")
    # Use raw SQL to count before migration
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM videos"))
        video_count = result.fetchone()[0]
        print(f"   Videos in database: {video_count}")
    print()

    print("🔧 Applying migration...")
    print("   Adding 'embedding' column to 'videos' table...")

    try:
        # For existing tables, we need to ALTER TABLE directly
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE videos ADD COLUMN embedding BLOB"))
            conn.commit()

        print("✅ Migration successful!")
        print()

        # Verify
        if check_column_exists():
            print("✅ Verification passed!")
            print("   'embedding' column added successfully")
            print()
            print("📊 Post-migration state:")
            with get_session() as session:
                video_count = session.query(Video).count()
                videos_with_embeddings = session.query(Video).filter(
                    Video.embedding.isnot(None)
                ).count()
                print(f"   Videos in database: {video_count}")
                print(f"   Videos with embeddings: {videos_with_embeddings}")
                print(f"   Videos without embeddings: {video_count - videos_with_embeddings}")
            print()
            print("💡 Notes:")
            print("   - Existing videos have embedding = NULL (safe)")
            print("   - New videos will automatically get embeddings")
            print("   - Run 'python scripts/backfill_embeddings.py' to generate")
            print("     embeddings for existing videos (optional)")
        else:
            print("⚠️  Verification failed - column not found")
            return False

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

    print()
    print("="*60)
    print("Migration completed successfully!")
    print("="*60)
    return True

if __name__ == "__main__":
    migrate()
