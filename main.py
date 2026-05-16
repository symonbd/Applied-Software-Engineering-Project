import os
import time

# FIXED: Now strictly using the exact variable names from your config.py!
from config import BASE_DOWNLOAD_DIR, SEARCH_QUERIES
from logger import logger
from database.database import MetadataDatabase
from downloader.downloader import Downloader
from repositories.fsd_client import FSDClient
from repositories.sikt_client import SiktClient

def main():
    logger.info("Starting QDArchive Acquisition Pipeline")

    # Ensure your clean archive folder exists using the correct config variable
    os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)

    db = MetadataDatabase()
    downloader = Downloader(db)

    fsd = FSDClient()
    sikt = SiktClient()

    tasks = []

    logger.info("Searching targeted repositories...")

    # Iterate through the strict queries defined in config.py
    for q in SEARCH_QUERIES:
        logger.info(f"Running query: {q}")

        # SIKT Search
        try:
            sikt_tasks = sikt.search(q)
            for t in sikt_tasks:
                t['query'] = q
                t['repository'] = "sikt" # Enforcing clean folder name
            tasks.extend(sikt_tasks[:100])
        except Exception as e:
            logger.error(f"SIKT error for query '{q}': {e}")

        # FSD Search
        try:
            fsd_tasks = fsd.search(q)
            for t in fsd_tasks:
                t['query'] = q
                t['repository'] = "finnish-social-science-data-archive" # Enforcing exact config.py name for validator
            tasks.extend(fsd_tasks[:100])
        except Exception as e:
            logger.error(f"FSD error for query '{q}': {e}")

    logger.info(f"Total files discovered and queued: {len(tasks)}")

    if len(tasks) == 0:
        logger.warning("No files discovered. Check your internet connection or API status.")
        return

    logger.info("Starting targeted downloads (Single-threaded for Mac stability)...")

    # Execute downloads ONE by ONE safely to prevent SQLite Segfaults
    for i, task in enumerate(tasks, 1):
        logger.info(f"Processing task {i}/{len(tasks)}...")
        downloader.download(task)
        time.sleep(0.5) # Give the Mac network card and SQLite a tiny moment to breathe

    logger.info("Download phase completed.")

    try:
        total = db.count()
        logger.info(f"Total files successfully stored in database: {total}")
    except Exception as e:
        logger.error(f"Failed to count database files: {e}")

    logger.info("Phase 1 finished successfully! Now run fsd_playwright.py for locked data.")

if __name__ == "__main__":
    main()