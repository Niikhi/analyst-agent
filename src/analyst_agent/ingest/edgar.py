import time
from typing import Any

import httpx

from analyst_agent.ingest.config import sec_user_agent

TICKER_INDEX_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
REQUEST_INTERVAL = 0.15


class EdgarClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            headers={
                "User-Agent": sec_user_agent(),
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self._ticker_index: dict[str, dict[str, Any]] | None = None
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "EdgarClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, url: str) -> dict[str, Any]:
        elapsed = time.monotonic() - self._last_request
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)
        response = self._client.get(url)
        self._last_request = time.monotonic()
        response.raise_for_status()
        return response.json()

    def _load_ticker_index(self) -> dict[str, dict[str, Any]]:
        if self._ticker_index is None:
            raw = self._get(TICKER_INDEX_URL)
            self._ticker_index = {
                entry["ticker"].upper(): {
                    "cik": f"{int(entry['cik_str']):010d}",
                    "title": entry["title"],
                }
                for entry in raw.values()
            }
        return self._ticker_index

    def resolve_ticker(self, ticker: str) -> dict[str, Any]:
        index = self._load_ticker_index()
        entry = index.get(ticker.upper())
        if entry is None:
            raise LookupError(f"{ticker} is not in the SEC ticker index")
        return entry

    def company_facts(self, cik: str) -> dict[str, Any]:
        return self._get(COMPANY_FACTS_URL.format(cik=cik))

    def submissions(self, cik: str) -> dict[str, Any]:
        return self._get(SUBMISSIONS_URL.format(cik=cik))
