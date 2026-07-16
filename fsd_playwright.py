# fsd_playwright.py
# ---------------------------------------------------------------
# Authenticated FSD downloader using Playwright (sync API).
# Rescues files flagged as FAILED_LOGIN_REQUIRED in the seeding DB.
#
# The login/discovery/consent flow below (handle_discovery_page,
# handle_login, handle_consent_page) is verified working end-to-end against
# a real FSD account. But logging in is necessary, not sufficient: every
# restricted FSD study sampled from this project's discovery run is
# "Condition B" -- FSD requires submitting a real per-dataset application
# (intended_usage, project_name, project_description) before the actual
# file is released, not just an authenticated session. This script
# deliberately does NOT fill and submit that application form -- doing so
# automatically would mean fabricating a research justification under a
# real FSD account for hundreds of datasets, which is a misuse of the
# account and almost certainly against FSD's terms of use. Condition-A
# (truly open) studies would download automatically via download_file()
# once logged in; none were found in this project's discovered study set.
# ---------------------------------------------------------------
import os
import sys
import sqlite3
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright is not installed.")
    print("Run:  pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv is not installed. Run: pip install python-dotenv")
    sys.exit(1)

from logger import logger
from config import BASE_DOWNLOAD_DIR

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------
ENV_FILE = "access.env"
SEEDING_DB = "23088045-seeding.db"
FSD_LOGIN_URL = "https://services.fsd.tuni.fi/catalogue"
# FSD has no separate "/download" endpoint (that 404s). The real download
# link/button lives inside the study's own tab=download page and only
# renders as an active link once the Shibboleth session is authenticated --
# anonymously it shows an inactive "Download data" placeholder instead.
FSD_DOWNLOAD_TEMPLATE = (
    "https://services.fsd.tuni.fi/catalogue/{study_id}"
    "?tab=download&lang=en&study_language=en"
)
REPO_FOLDER = "finnish-social-science-data-archive"


def load_credentials():
    """Load FSD credentials from access.env file."""
    load_dotenv(ENV_FILE)
    username = os.getenv("FSD_USERNAME")
    password = os.getenv("FSD_PASSWORD")
    if not username or not password:
        logger.error("FSD_USERNAME or FSD_PASSWORD not set in access.env")
        sys.exit(1)
    return username, password


def get_locked_files(db_path):
    """Fetch FSD files with status FAILED_LOGIN_REQUIRED from the seeding DB.
    Scoped to repository_id 11 (FSD) -- this downloader only knows how to
    drive FSD's Shibboleth login, so a locked Sikt (or any other repo) file
    would just fail here, or worse, get misclassified as it's routed through
    FSD's URL template."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.id, p.project_identifier, f.file_name, p.project_url
        FROM FILES f
        JOIN PROJECTS p ON f.project_id = p.id
        WHERE f.status = 'FAILED_LOGIN_REQUIRED' AND p.repository_id = 11
    """)
    rows = cursor.fetchall()
    conn.close()
    logger.info(f"Found {len(rows)} FSD files requiring login.")
    return rows  # [(file_id, project_identifier, file_name, project_url), ...]


def update_file_status(db_path, file_id, status):
    """Update the status of a file in the seeding DB."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("UPDATE FILES SET status = ? WHERE id = ?", (status, file_id))
    conn.commit()
    conn.close()


def handle_discovery_page(page):
    """FSD's Shibboleth flow routes through a WAYF discovery page ('Kirjautuminen
    | Aila') offering HAKA (institutional) or a direct FSD account. These
    credentials are a direct FSD account, so pick that option -- its link
    text is 'Kirjaudu tästä (Click to login)' and its href selects
    accounts.fsd.uta.fi as the chosen identity provider."""
    if "disco" not in page.url and "Kirjautuminen" not in page.title():
        return True  # not a discovery page, nothing to do
    logger.info(f"Discovery page: {page.title()}")
    for sel in ["a[href*='accounts.fsd.uta.fi']", "text=Kirjaudu tästä", "text=Click to login"]:
        try:
            link = page.locator(sel).first
            if link.is_visible(timeout=3000):
                logger.info(f"Selecting direct FSD account login ({sel})")
                link.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                return True
        except Exception:
            continue
    logger.warning("Could not find the direct FSD account option on the discovery page")
    return False


def handle_login(page, username, password):
    """
    Attempt to log in through the FSD / Shibboleth / HAKA SSO flow.
    This handles the standard redirect chain:
      FSD → Shibboleth discovery → HAKA IdP → credentials → redirect back.
    """
    logger.info("Attempting FSD/Shibboleth login...")

    # Wait for the page to settle after any redirects
    page.wait_for_load_state("networkidle", timeout=15000)

    # -- Strategy 1: Direct username/password fields on the page --
    # Try common Shibboleth / HAKA login field selectors
    username_selectors = [
        'input[name="j_username"]',
        'input[name="username"]',
        'input[id="username"]',
        'input[type="text"][name*="user"]',
        'input[type="email"]',
    ]
    password_selectors = [
        'input[name="j_password"]',
        'input[name="password"]',
        'input[id="password"]',
        'input[type="password"]',
    ]

    username_field = None
    for sel in username_selectors:
        try:
            field = page.locator(sel).first
            if field.is_visible(timeout=2000):
                username_field = field
                break
        except Exception:
            continue

    password_field = None
    for sel in password_selectors:
        try:
            field = page.locator(sel).first
            if field.is_visible(timeout=2000):
                password_field = field
                break
        except Exception:
            continue

    if username_field and password_field:
        logger.info("Found login form — entering credentials...")
        username_field.fill(username)
        password_field.fill(password)

        # Look for submit button
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button[name="_eventId_proceed"]',
            'button:has-text("Login")',
            'button:has-text("Log in")',
            'button:has-text("Sign in")',
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_load_state("networkidle", timeout=20000)
                    logger.info("Login form submitted.")
                    handle_consent_page(page)
                    return True
            except Exception:
                continue

        # Fallback: press Enter on password field
        password_field.press("Enter")
        page.wait_for_load_state("networkidle", timeout=20000)
        logger.info("Login submitted via Enter key.")
        handle_consent_page(page)
        return True

    logger.warning("Could not find login form fields on the page.")
    return False


def handle_consent_page(page):
    """After credentials are accepted, Shibboleth shows an 'Information
    Release' attribute-consent page before completing the SSO handshake.
    Without accepting it, the session never actually authenticates."""
    if "Information Release" not in page.title():
        return
    logger.info("Consent page: Information Release — accepting...")
    try:
        btn = page.locator("input[name='_eventId_proceed']").first
        if btn.is_visible(timeout=3000):
            btn.click()
            page.wait_for_load_state("networkidle", timeout=20000)
            logger.info("Accepted attribute release.")
    except Exception as e:
        logger.warning(f"Could not accept the consent page: {e}")


def accept_terms(page):
    """
    Check for and accept any Terms of Use / conditions checkboxes/buttons
    that FSD may present before allowing a download.
    """
    # Try checkboxes first
    checkbox_selectors = [
        'input[type="checkbox"][name*="terms"]',
        'input[type="checkbox"][name*="accept"]',
        'input[type="checkbox"][name*="agree"]',
        'input[type="checkbox"][id*="terms"]',
        'input[type="checkbox"][id*="accept"]',
        'input[type="checkbox"]',
    ]
    for sel in checkbox_selectors:
        try:
            cb = page.locator(sel).first
            if cb.is_visible(timeout=2000) and not cb.is_checked():
                cb.check()
                logger.info(f"Checked terms checkbox: {sel}")
                time.sleep(0.5)
        except Exception:
            continue

    # Try accept/consent buttons. Deliberately NOT matching "Download" here --
    # FSD's download-tab page has a "Download data" *tab* link earlier in the
    # DOM than the real download trigger inside #download-button, and both
    # carry that exact text, so a generic "has-text(Download)" match here
    # would click the tab (a harmless-looking but wrong reload) rather than
    # a genuine consent step. The real download click is download_file()'s job.
    button_selectors = [
        'button:has-text("Accept")',
        'button:has-text("I accept")',
        'button:has-text("Agree")',
        'a:has-text("Accept")',
        'a:has-text("I accept")',
        'input[type="submit"][value*="Accept"]',
    ]
    for sel in button_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                logger.info(f"Clicked accept/download button: {sel}")
                page.wait_for_load_state("networkidle", timeout=10000)
                return True
        except Exception:
            continue

    return False


def download_file(page, study_id, file_name, download_dir):
    """
    Navigate to the FSD download page for a study and save the file.
    Returns True on success, False on failure.
    """
    download_url = FSD_DOWNLOAD_TEMPLATE.format(study_id=study_id)
    dest_dir = os.path.join(download_dir, REPO_FOLDER, study_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, file_name)

    if os.path.exists(dest_path):
        logger.info(f"  Already on disk: {file_name}")
        return True

    try:
        # Start waiting for download BEFORE triggering it
        page.goto(download_url, wait_until="networkidle", timeout=30000)
        time.sleep(1)

        # Check if we hit a terms/conditions page
        accept_terms(page)

        # Try to trigger the download via the download event.
        # #download-button is the specific container FSD renders the real,
        # authenticated download link into -- there's also a "Download data"
        # *tab* link elsewhere on the page with identical visible text, so a
        # generic text/href match risks clicking that instead (see
        # accept_terms()'s comment for the same trap).
        with page.expect_download(timeout=60000) as download_info:
            dl_selectors = [
                '#download-button a',
                'a[href*="/catalogue/download"]',
                'a:has-text("Download")',
                'button:has-text("Download")',
            ]
            clicked = False
            for sel in dl_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                # Maybe the navigation itself triggered the download
                pass

        download = download_info.value
        download.save_as(dest_path)
        logger.info(f"  Downloaded: {file_name} -> {dest_path}")
        return True

    except Exception as e:
        logger.error(f"  Failed to download {study_id}/{file_name}: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("FSD Authenticated Downloader (Playwright)")
    logger.info("=" * 60)

    if not os.path.exists(SEEDING_DB):
        logger.error(f"Seeding database not found: {SEEDING_DB}")
        sys.exit(1)

    username, password = load_credentials()
    locked_files = get_locked_files(SEEDING_DB)

    if not locked_files:
        logger.info("No FAILED_LOGIN_REQUIRED files to process. Exiting.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        context = browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # -- Step 1: Log in --
        # FSD does NOT auto-redirect an anonymous visitor to Shibboleth; the
        # download-tab page renders fine (HTTP 200) with an inactive
        # "Download data" placeholder and a separate "Login" link that has
        # to be clicked to actually start the SSO flow. Just visiting the
        # page and checking for a redirect (the previous approach) never
        # triggers a login at all.
        logger.info("Navigating to FSD to start the login flow...")
        first_study_id = locked_files[0][1]  # project_identifier
        first_download_url = FSD_DOWNLOAD_TEMPLATE.format(study_id=first_study_id)

        try:
            page.goto(first_download_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            logger.warning(f"Initial navigation issue: {e}")

        login_success = False
        try:
            login_link = page.locator("a[href*='Shibboleth.sso/Login']").first
            if login_link.is_visible(timeout=5000):
                logger.info("Clicking FSD login link to start Shibboleth SSO...")
                login_link.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                if handle_discovery_page(page):
                    login_success = handle_login(page, username, password)
            else:
                logger.info("No login link found — session may already be active.")
                login_success = True
        except Exception as e:
            logger.warning(f"Could not locate/click the login link: {e}")

        if not login_success:
            logger.error("Login failed — cannot proceed with authenticated downloads.")
            browser.close()
            return

        # Re-visit the first study's page now that the session is authenticated
        try:
            page.goto(first_download_url, wait_until="networkidle", timeout=30000)
        except Exception:
            pass
        authenticated = any(kw in page.content().lower() for kw in ["log out", "logout", "kirjaudu ulos"])
        logger.info(f"Login flow complete — {'authenticated' if authenticated else 'status unclear'}.")

        # -- Step 2: Download each locked file --
        succeeded = 0
        failed = 0

        for file_id, project_id, file_name, project_url in locked_files:
            logger.info(f"Processing: {project_id}/{file_name} (file_id={file_id})")

            success = download_file(page, project_id, file_name, BASE_DOWNLOAD_DIR)

            if success:
                update_file_status(SEEDING_DB, file_id, "SUCCEEDED")
                succeeded += 1
            else:
                failed += 1
                logger.warning(f"  Kept as FAILED_LOGIN_REQUIRED: {file_name}")

            time.sleep(1)  # Polite delay between downloads

        browser.close()

    logger.info("=" * 60)
    logger.info(f"Authenticated download complete: {succeeded} succeeded, {failed} failed.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
