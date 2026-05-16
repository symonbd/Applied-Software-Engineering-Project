import os
import requests
import time
from config import BASE_DOWNLOAD_DIR
from logger import logger


class Downloader:
    def __init__(self, db):
        self.db = db
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

    def download(self, task):
        # THE FIX: Use .get() so it never crashes if a key is missing!
        url = task.get('url')
        filename = task.get('filename', 'unknown_file.zip')
        repo = task.get('repository', 'unknown_repo')

        # Safely grab 'metadata', fallback to 'title', fallback to a generic name
        title = task.get('metadata', task.get('title', f"Project {filename.split('_')[0]}"))

        # Extract a clean project ID from the filename
        project_id = filename.split('_')[0]

        folder_path = os.path.join(BASE_DOWNLOAD_DIR, repo, project_id)
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, filename)

        # Skip if already downloaded!
        if os.path.exists(file_path):
            logger.info(f"Skipping {filename} (Already exists)")
            self.db.log_file(repo, project_id, title, url, filename, "SUCCEEDED")
            return

        try:
            r = requests.get(url, headers=self.headers, stream=True, timeout=20)

            # If FSD blocks us with a 401 Unauthorized or login page, flag it!
            if r.status_code in [401, 403] or 'Shibboleth.sso' in r.url:
                logger.warning(f"Login required for {filename}")
                self.db.log_file(repo, project_id, title, url, filename, "FAILED_LOGIN_REQUIRED")
                return

            if r.status_code == 200:
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Successfully downloaded: {filename}")
                self.db.log_file(repo, project_id, title, url, filename, "SUCCEEDED")
            else:
                self.db.log_file(repo, project_id, title, url, filename, "FAILED_SERVER_UNRESPONSIVE")

        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            self.db.log_file(repo, project_id, title, url, filename, "FAILED_SERVER_UNRESPONSIVE")