import sqlite3
import os
from datetime import datetime

from config import DATABASE_NAME
from logger import logger

REPOSITORIES = {
    11: {"name": "finnish-social-science-data-archive"},
    20: {"name": "sikt"},
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
                           CREATE TABLE IF NOT EXISTS REPOSITORIES
                           (
                               id INTEGER PRIMARY KEY,
                               name TEXT UNIQUE NOT NULL
                           )
                           ''')

            # Projects Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS PROJECTS
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               repository_id INTEGER,
                               project_identifier TEXT NOT NULL,
                               title TEXT,
                               description TEXT,
                               project_url TEXT,
                               download_method TEXT CHECK (download_method IN ('API-CALL', 'SCRAPING')),
                               download_date TEXT,
                               repository_url TEXT,
                               download_repository_folder TEXT,
                               download_project_folder TEXT,
                               project_type TEXT,
                               isic_section TEXT,
                               isic_division TEXT,
                               isic_division_code TEXT,
                               classification_tags TEXT,
                               primary_class TEXT,
                               secondary_class TEXT,
                               FOREIGN KEY (repository_id) REFERENCES REPOSITORIES (id),
                               UNIQUE (repository_id, project_identifier)
                           )
                           ''')

            # Files Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS FILES
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               project_id INTEGER,
                               file_name TEXT NOT NULL,
                               file_type TEXT,
                               class TEXT,
                               status TEXT CHECK (status IN ('SUCCEEDED', 'FAILED_SERVER_UNRESPONSIVE', 'FAILED_LOGIN_REQUIRED', 'FAILED_TOO_LARGE')),
                               FOREIGN KEY (project_id) REFERENCES PROJECTS (id)
                           )
                           ''')

            # Keywords Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS KEYWORDS
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               project_id INTEGER,
                               keyword TEXT,
                               FOREIGN KEY (project_id) REFERENCES PROJECTS (id)
                           )
                           ''')

            # Person Role Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS PERSON_ROLE
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               project_id INTEGER,
                               person_name TEXT,
                               role TEXT,
                               FOREIGN KEY (project_id) REFERENCES PROJECTS (id)
                           )
                           ''')

            # Licenses Table
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS LICENSES
                           (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               project_id INTEGER,
                               license_name TEXT,
                               license_url TEXT,
                               FOREIGN KEY (project_id) REFERENCES PROJECTS (id)
                           )
                           ''')

            # Populate Repositories
            for repo_id, repo_data in REPOSITORIES.items():
                cursor.execute('INSERT OR REPLACE INTO REPOSITORIES (id, name) VALUES (?, ?)',
                               (repo_id, repo_data["name"]))
            conn.commit()

    def log_file(self, repo_name, project_id, title, url, filename, status="SUCCEEDED"):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get Repo ID
            cursor.execute('SELECT id FROM REPOSITORIES WHERE name = ?', (repo_name,))
            repo_row = cursor.fetchone()
            if not repo_row:
                return
            repo_id = repo_row[0]

            # Insert or Ignore Project
            cursor.execute('''
                           INSERT OR IGNORE INTO PROJECTS (repository_id, project_identifier, title, project_url, download_method, download_date)
                           VALUES (?, ?, ?, ?, 'API-CALL', ?)
                           ''', (repo_id, project_id, title, url, datetime.utcnow().isoformat()))

            cursor.execute('SELECT id FROM PROJECTS WHERE repository_id = ? AND project_identifier = ?',
                           (repo_id, project_id))
            internal_proj_id = cursor.fetchone()[0]

            # Insert File
            ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
            cursor.execute('''
                           INSERT INTO FILES (project_id, file_name, file_type, status)
                           VALUES (?, ?, ?, ?)
                           ''', (internal_proj_id, filename, ext, status))
            conn.commit()

    def count(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute('SELECT COUNT(*) FROM FILES WHERE status="SUCCEEDED"').fetchone()[0]

    def get_project_identifiers(self, repository_id):
        """Return project_identifier values already discovered for a repository (e.g. FSD study IDs)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT project_identifier FROM PROJECTS WHERE repository_id = ? ORDER BY project_identifier',
                (repository_id,)
            )
            return [row[0] for row in cursor.fetchall()]