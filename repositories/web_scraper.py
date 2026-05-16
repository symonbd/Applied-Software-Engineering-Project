import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class WebScraper:

    def search(self, url):

        results = []

        r = requests.get(url)

        soup = BeautifulSoup(r.text,"html.parser")

        for a in soup.find_all("a",href=True):

            full = urljoin(url,a["href"])

            results.append({
                "repository":"WebRepo",
                "url":full,
                "filename":a.text,
                "license":"",
                "uploader":""
            })

        return results