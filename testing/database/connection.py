"""
Database Connection Manager
===========================
Handles PostgreSQL connections to nuahchain-backend database.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config

logger = logging.getLogger(__name__)


def get_connection():
    """Get a new database connection"""
    return psycopg2.connect(
        host=config.database.host,
        port=config.database.port,
        database=config.database.database,
        user=config.database.user,
        password=config.database.password
    )


class DatabaseManager:
    """
    Database manager for handling PostgreSQL operations.
    Supports connection pooling and context management.
    """
    
    def __init__(self):
        self.config = config.database
        self._connection: Optional[psycopg2.extensions.connection] = None
    
    def connect(self) -> psycopg2.extensions.connection:
        """Establish database connection"""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password
            )
            logger.info(f"Connected to PostgreSQL: {self.config.host}:{self.config.port}/{self.config.database}")
        return self._connection
    
    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()
            logger.info("Database connection closed")
    
    @contextmanager
    def cursor(self, dict_cursor: bool = True) -> Generator:
        """
        Context manager for database cursor.
        
        Args:
            dict_cursor: If True, returns rows as dictionaries
        """
        conn = self.connect()
        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
    
    @contextmanager
    def transaction(self) -> Generator:
        """Context manager for database transactions"""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction error: {e}")
            raise
    
    def execute(self, query: str, params: tuple = None) -> int:
        """Execute a query and return affected row count"""
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount
    
    def execute_many(self, query: str, params_list: list) -> int:
        """Execute a query with multiple parameter sets"""
        with self.cursor() as cur:
            cur.executemany(query, params_list)
            return cur.rowcount
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[dict]:
        """Fetch a single row"""
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()
    
    def fetch_all(self, query: str, params: tuple = None) -> list:
        """Fetch all rows"""
        with self.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """
        result = self.fetch_one(query, (table_name,))
        return result['exists'] if result else False
    
    def get_table_count(self, table_name: str) -> int:
        """Get row count for a table"""
        with self.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            result = cur.fetchone()
            return result['count'] if result else 0
    
    def truncate_table(self, table_name: str, cascade: bool = False):
        """Truncate a table"""
        cascade_str = "CASCADE" if cascade else ""
        with self.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {table_name} {cascade_str} RESTART IDENTITY")
            logger.info(f"Truncated table: {table_name}")
    
    def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            result = self.fetch_one("SELECT 1 as health")
            return result['health'] == 1 if result else False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Global database manager instance
db = DatabaseManager()

