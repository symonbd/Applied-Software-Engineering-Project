import requests
import time
import re
from bs4 import BeautifulSoup
from logger import logger


class FSDClient:
    BASE_URL = "https://services.fsd.tuni.fi/catalogue/index"
    OAI_URL  = "https://services.fsd.tuni.fi/v0/oai"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def _check_open_access(self, study_id: str) -> bool:
        """
        Query the OAI-PMH record and look for <dataAccs> = 'A' (openly downloadable).
        Condition A = freely downloadable without login.
        Conditions B/C/D = login or restricted.
        """
        try:
            params = {
                "verb": "GetRecord",
                "identifier": f"oai:fsd.uta.fi:{study_id}",
                "metadataPrefix": "oai_ddi25",
            }
            r = requests.get(
                self.OAI_URL, params=params,
                headers=self.HEADERS, timeout=15
            )
            if r.status_code != 200:
                return False
            # Look for condition A access marker in the XML
            # FSD marks open datasets with dataAccs="A" or accConstr containing "A"
            text = r.text
            if 'dataAccs="A"' in text or ">A<" in text or "Freely available" in text:
                return True
            return False
        except Exception:
            return False

    def _is_real_file(self, url: str) -> bool:
        """
        HEAD probe: returns True only if the server sends a non-HTML content type.
        Prevents saving login redirect pages as fake ZIP files.
        """
        try:
            r = requests.head(
                url, headers=self.HEADERS,
                timeout=10, allow_redirects=True
            )
            if r.status_code != 200:
                return False
            ct = r.headers.get("Content-Type", "")
            return "text/html" not in ct
        except Exception:
            return False

    def search(self, query: str) -> list:
        tasks = []
        page = 1
        logger.info(f"FSD search: '{query}'")

        while page <= 10:
            try:
                params = {
                    "lang": "en",
                    "q": query,
                    "data_kind_string_facet": "Qualitative",
                    "study_language": "en",
                    "limit": 50,
                    "page": page,
                }
                r = requests.get(
                    self.BASE_URL, params=params,
                    headers=self.HEADERS, timeout=15
                )
                if r.status_code != 200:
                    logger.warning(f"FSD HTTP {r.status_code} on page {page}")
                    break

                soup = BeautifulSoup(r.text, "html.parser")
                study_links = soup.find_all("a", href=re.compile(r"/catalogue/FSD\d+"))

                if not study_links:
                    logger.info(f"FSD: no more results on page {page}")
                    break

                for a in study_links:
                    href = a.get("href", "")
                    match = re.search(r"(FSD\d+)", href)
                    if not match:
                        continue
                    study_id = match.group(1)
                    title = a.text.strip() or f"Project {study_id}"
                    if len(title) < 3:
                        title = f"Project {study_id}"

                    # Always queue the OAI-PMH XML — always public
                    xml_url = (
                        f"{self.OAI_URL}?verb=GetRecord"
                        f"&identifier=oai:fsd.uta.fi:{study_id}"
                        f"&metadataPrefix=oai_ddi25"
                    )
                    tasks.append({
                        "url": xml_url,
                        "filename": f"{study_id}_metadata.xml",
                        "repository": "FSD",
                        "description": title,
                        "license": "",
                        "uploader": "",
                    })

                    # Only queue data ZIP if OAI confirms open access (Condition A)
                    if self._check_open_access(study_id):
                        zip_url = (
                            f"https://services.fsd.tuni.fi/catalogue"
                            f"/{study_id}/download?lang=en&study_language=en"
                        )
                        # Double-check with HEAD probe to avoid saving HTML pages
                        if self._is_real_file(zip_url):
                            logger.info(f"  [OPEN] {study_id} queued for download")
                            tasks.append({
                                "url": zip_url,
                                "filename": f"{study_id}_data.zip",
                                "repository": "FSD",
                                "description": title,
                                "license": "open",
                                "uploader": "",
                            })
                        else:
                            logger.info(f"  [RESTRICTED] {study_id} — HEAD probe blocked")
                    else:
                        logger.info(f"  [RESTRICTED] {study_id} — login required")

                    time.sleep(0.3)  # Small delay per study to be polite

                page += 1
                time.sleep(1.5)

            except Exception as e:
                logger.error(f"FSD error page {page}: {e}")
                break

        unique_tasks = list({t["url"]: t for t in tasks}.values())
        logger.info(f"FSD: {len(unique_tasks)} unique tasks for '{query}'")
        return unique_tasks