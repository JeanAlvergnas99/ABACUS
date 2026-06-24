import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class FMPClient:
    """Small client for Financial Modeling Prep API."""

    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise ValueError("Missing FMP API key. Add it in .env or Streamlit sidebar.")

    def _get(self, endpoint: str, params: dict | None = None) -> list[dict]:
        params = params or {}
        params["apikey"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("Error Message"):
            raise ValueError(data["Error Message"])
        if not data:
            raise ValueError(f"No data returned for endpoint: {endpoint}")
        return data

    def income_statement(self, ticker: str, limit: int = 5) -> pd.DataFrame:
        data = self._get(f"income-statement/{ticker.upper()}", {"limit": limit})
        return pd.DataFrame(data)

    def balance_sheet(self, ticker: str, limit: int = 5) -> pd.DataFrame:
        data = self._get(f"balance-sheet-statement/{ticker.upper()}", {"limit": limit})
        return pd.DataFrame(data)

    def cash_flow(self, ticker: str, limit: int = 5) -> pd.DataFrame:
        data = self._get(f"cash-flow-statement/{ticker.upper()}", {"limit": limit})
        return pd.DataFrame(data)

    def profile(self, ticker: str) -> dict:
        data = self._get(f"profile/{ticker.upper()}")
        return data[0]
