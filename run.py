import subprocess
from logger import logger


def run_pipeline():
    logger.info("=== STARTING MASTER QDArchive PIPELINE ===")

    # Phase 1: Safe API Scraping & Schema Building
    logger.info("Executing Phase 1: API Scraping (main.py)...")
    try:
        subprocess.run(["python", "main.py"], check=True)
    except subprocess.CalledProcessError:
        logger.error("Phase 1 failed. Halting pipeline.")
        return

    # Phase 2: Playwright Shibboleth Login
    logger.info("Executing Phase 2: Secure FSD Download (fsd_playwright.py)...")
    try:
        subprocess.run(["python", "fsd_playwright.py"], check=True)
    except subprocess.CalledProcessError:
        logger.error("Phase 2 failed.")
        return

    logger.info("=== MASTER PIPELINE COMPLETE! RUN YOUR VALIDATOR NOW. ===")


if __name__ == "__main__":
    run_pipeline()