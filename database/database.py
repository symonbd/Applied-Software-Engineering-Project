import sqlite3
import os
from datetime import datetime

# FIXED: Removed REPOSITORIES from the config import
from config import DATABASE_NAME
from logger import logger

# Hardcoding the required repository IDs here so it doesn't crash looking for them
REPOSITORIES = {
    11: {"name": "finnish-social-science-data-archive"},
    12: {"name": "sikt"}
}


class MetadataDatabase:
    def __init__(self):
        self.db_path = DATABASE_NAME
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Repositories Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS repositories
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY,
                               name
                               TEXT
                               UNIQUE
                               NOT
                               NULL
                           )
                           ''')

            # Projects Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS projects
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               repository_id
                               INTEGER,
                               project_identifier
                               TEXT
                               NOT
                               NULL,
                               title
                               TEXT,
                               description
                               TEXT,
                               project_url
                               TEXT,
                               download_method
                               TEXT
                               CHECK (
                               download_method
                               IN
                           (
                               'API-CALL',
                               'SCRAPING'
                           )),
                               download_date TEXT,
                               FOREIGN KEY
                           (
                               repository_id
                           ) REFERENCES repositories
                           (
                               id
                           ),
                               UNIQUE
                           (
                               repository_id,
                               project_identifier
                           )
                               )
                           ''')

            # Files Table (Strict Enums!)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS files
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               project_id
                               INTEGER,
                               file_name
                               TEXT
                               NOT
                               NULL,
                               file_type
                               TEXT,
                               status
                               TEXT
                               CHECK (
                               status
                               IN
                           (
                               'SUCCEEDED',
                               'FAILED_SERVER_UNRESPONSIVE',
                               'FAILED_LOGIN_REQUIRED',
                               'FAILED_TOO_LARGE'
                           )),
                               FOREIGN KEY
                           (
                               project_id
                           ) REFERENCES projects
                           (
                               id
                           )
                               )
                           ''')

            # Populate Repositories from the dictionary above
            for repo_id, repo_data in REPOSITORIES.items():
                cursor.execute('INSERT OR IGNORE INTO repositories (id, name) VALUES (?, ?)',
                               (repo_id, repo_data["name"]))
            conn.commit()

    def log_file(self, repo_name, project_id, title, url, filename, status="SUCCEEDED"):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get Repo ID
            cursor.execute('SELECT id FROM repositories WHERE name = ?', (repo_name,))
            repo_row = cursor.fetchone()
            if not repo_row:
                return
            repo_id = repo_row[0]

            # Insert or Ignore Project
            cursor.execute('''
                           INSERT
                           OR IGNORE INTO projects (repository_id, project_identifier, title, project_url, download_method, download_date)
                VALUES (?, ?, ?, ?, 'API-CALL', ?)
                           ''', (repo_id, project_id, title, url, datetime.utcnow().isoformat()))

            cursor.execute('SELECT id FROM projects WHERE repository_id = ? AND project_identifier = ?',
                           (repo_id, project_id))
            internal_proj_id = cursor.fetchone()[0]

            # Insert File
            ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
            cursor.execute('''
                           INSERT INTO files (project_id, file_name, file_type, status)
                           VALUES (?, ?, ?, ?)
                           ''', (internal_proj_id, filename, ext, status))
            conn.commit()

    def count(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute('SELECT COUNT(*) FROM files WHERE status="SUCCEEDED"').fetchone()[0]