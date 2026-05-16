import requests
import time


class SiktClient:
    # SIKT uses the Dataverse framework for their open data repository
    BASE_URL = "https://dataverse.no/api/search"

    def search(self, query):
        tasks = []
        start = 0
        rows = 100  # Maximize items per request
        max_results = 2000  # High limit to ensure deep extraction without infinite loops

        print(f"Starting SIKT search for: {query}")

        while start < max_results:
            try:
                params = {
                    "q": query,
                    "type": "file",  # Targeting files directly
                    "start": start,
                    "per_page": rows
                }

                # Robust timeout to prevent pipeline hanging
                r = requests.get(self.BASE_URL, params=params, timeout=20)

                if r.status_code != 200:
                    print(f"SIKT API returned status {r.status_code}. Stopping pagination.")
                    break

                data = r.json()
                items = data.get("data", {}).get("items", [])

                if not items:
                    break  # Break the loop if we've reached the end of the results

                for item in items:
                    file_url = item.get("url")
                    file_name = item.get("name")
                    # Extracting dataset description for Part 2 Classification
                    description = item.get("description", "")

                    if file_url and file_name:
                        tasks.append({
                            "url": file_url,
                            "filename": file_name,
                            "repository": "sikt_dataverse",
                            "metadata": description
                        })

                start += rows
                time.sleep(0.5)  # Be polite to the SIKT servers to avoid rate limiting

            except requests.exceptions.RequestException as e:
                print(f"SIKT connection error at offset {start}: {e}")
                break
            except Exception as e:
                print(f"SIKT unexpected error: {e}")
                break

        # Deduplicate tasks based on URL to avoid redundant downloads
        unique_tasks = {t['url']: t for t in tasks}.values()
        return list(unique_tasks)
