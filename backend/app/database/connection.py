import sqlite3
from typing import Optional, List, Dict, Any

class DBConnection:
    _db_path: str = "ripple.db"

    @classmethod
    def set_db_path(cls, path: str):
        cls._db_path = path

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(cls._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # Repositories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                git_status TEXT,
                languages TEXT,
                analysis_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_analyzed_at TEXT
            )
        ''')
        
        # Files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL,
                path TEXT NOT NULL,
                language TEXT,
                size_bytes INTEGER,
                line_count INTEGER,
                FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE
            )
        ''')
        
        # Symbols table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS symbols (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                name TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                type TEXT NOT NULL,
                line_start INTEGER,
                line_end INTEGER,
                signature TEXT,
                docstring TEXT,
                FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE
            )
        ''')
        
        # Relationships table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE
            )
        ''')
        
        # Test results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL,
                framework TEXT,
                exit_code INTEGER,
                passed INTEGER,
                failed INTEGER,
                duration_seconds REAL,
                output TEXT,
                executed_at TEXT NOT NULL,
                FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE
            )
        ''')
        
        # Enable foreign keys
        cursor.execute('PRAGMA foreign_keys = ON;')
        
        conn.commit()
        conn.close()
