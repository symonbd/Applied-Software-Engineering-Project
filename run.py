import subprocess
import sys
from logger import logger

def run_pipeline():
    logger.info("=== STARTING MASTER QDArchive PIPELINE ===")

    # Phase 1: API Data Acquisition
    logger.info("Executing Phase 1: API Data Acquisition (main.py)...")
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
        logger.info("Phase 1 completed successfully.")
    except subprocess.CalledProcessError:
        logger.error("Phase 1 failed. Halting pipeline.")
        return

    # Phase 2: Authenticated FSD Downloads
    logger.info("Executing Phase 2: Authenticated FSD Downloads (fsd_playwright.py)...")
    try:
        subprocess.run([sys.executable, "fsd_playwright.py"], check=True)
        logger.info("Phase 2 completed successfully.")
    except subprocess.CalledProcessError:
        logger.warning("Phase 2 had errors (some files may remain locked). Continuing pipeline.")

    # Phase 3: Data Ingestion & Metadata Enrichment
    logger.info("Executing Phase 3: Data Ingestion & Metadata Enrichment (populate_from_disk.py)...")
    try:
        subprocess.run([sys.executable, "populate_from_disk.py"], check=True)
        logger.info("Phase 3 completed successfully.")
    except subprocess.CalledProcessError:
        logger.error("Phase 3 failed.")
        return

    # Phase 4: Offline ML Classifier
    logger.info("Executing Phase 4: Offline ML Classifier (classifier.py)...")
    try:
        subprocess.run([sys.executable, "classifier.py"], check=True)
        logger.info("Phase 4 completed successfully.")
    except subprocess.CalledProcessError:
        logger.error("Phase 4 failed.")
        return

    # Phase 5: Export Submission
    logger.info("Executing Phase 5: Exporter (export_submission.py)...")
    try:
        subprocess.run([sys.executable, "export_submission.py"], check=True)
        logger.info("Phase 5 completed successfully.")
    except subprocess.CalledProcessError:
        logger.error("Phase 5 failed.")
        return

    logger.info("=== MASTER PIPELINE COMPLETE! ===")

if __name__ == "__main__":
    run_pipeline()