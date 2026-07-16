import os
import requests
import time
from config import BASE_DOWNLOAD_DIR, MAX_FILE_SIZE_BYTES, BANNED_EXTENSIONS
from logger import logger


class Downloader:
    def __init__(self, db):
        self.db = db
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

    def download(self, task):
        url = task.get('url')
        filename = task.get('filename', 'unknown_file.zip')
        repo = task.get('repository', 'unknown_repo')

        title = task.get('metadata', task.get('title', f"Project {filename.split('_')[0]}"))
        project_id = filename.split('_')[0]

        folder_path = os.path.join(BASE_DOWNLOAD_DIR, repo, project_id)
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, filename)

        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.info(f"Skipping {filename} (already on disk, resuming)")
            self.db.log_file(repo, project_id, title, url, filename, "SUCCEEDED")
            return

        try:
            # Defensive Pre-Download Size Check
            head_req = requests.head(url, headers=self.headers, timeout=15, allow_redirects=True)
            content_length = head_req.headers.get('Content-Length')
            
            # Check for excessive size or binary keyword bloat
            if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
                too_large = True
            elif any(sub in filename.lower() for sub in BANNED_EXTENSIONS + ["fields-"]):
                too_large = True
            else:
                too_large = False

            if too_large:
                logger.warning(f"File {filename} blocked (Size/Bloat protection)")
                self.db.log_file(repo, project_id, title, url, filename, "FAILED_TOO_LARGE")
                return

            # Actually download
            r = requests.get(url, headers=self.headers, stream=True, timeout=20)

            if r.status_code in [401, 403] or 'Shibboleth.sso' in r.url:
                logger.warning(f"Login required for {filename}")
                self.db.log_file(repo, project_id, title, url, filename, "FAILED_LOGIN_REQUIRED")
                return

            # Some login walls (e.g. FSD's Shibboleth flow) don't redirect or
            # 401/403 an anonymous request at all -- they answer 200 with an
            # HTML page containing an inactive "Download data" placeholder.
            # Anything we asked for that isn't itself an .html/.htm file but
            # comes back as text/html is that placeholder, not real data.
            content_type = r.headers.get('Content-Type', '')
            expects_html = filename.lower().endswith(('.html', '.htm'))
            if r.status_code == 200 and 'text/html' in content_type.lower() and not expects_html:
                logger.warning(f"Login wall page returned instead of a file for {filename}")
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