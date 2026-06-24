import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class FMPClient:
    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise ValueError("Missing FMP API key.")

    def _get(self, endpoint, params=None):
        params = params or {}
        params["apikey"] = self.api_key

        response = requests.get(
            f"{self.BASE_URL}/{endpoint}",
            params=params,
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and data.get("Error Message"):
            raise ValueError(data["Error Message"])

        if not data:
            raise ValueError(f"No data returned for endpoint: {endpoint}")

        return data

    def income_statement(self, ticker, limit=5):
        data = self._get(
            "income-statement",
            {"symbol": ticker.upper(), "limit": min(limit, 5)},
        )
        return pd.DataFrame(data)

    def balance_sheet(self, ticker, limit=5):
        data = self._get(
            "balance-sheet-statement",
            {"symbol": ticker.upper(), "limit": min(limit, 5)},
        )
        return pd.DataFrame(data)

    def cash_flow(self, ticker, limit=5):
        data = self._get(
            "cash-flow-statement",
            {"symbol": ticker.upper(), "limit": min(limit, 5)},
        )
        return pd.DataFrame(data)

    def profile(self, ticker):
        data = self._get(
            "profile",
            {"symbol": ticker.upper()},
        )
        return data[0]

    def treasury_rates(self):
        return self._get("treasury-rates")

    def risk_free_rate_10y(self, fallback=0.0425):
        try:
            data = self.treasury_rates()
            latest = data[0]
            return float(latest.get("year10")) / 100
        except Exception:
            return fallback

    def analyst_estimates(self, ticker, period="annual"):
        return self._get(
            "analyst-estimates",
            {
                "symbol": ticker.upper(),
                "period": period,
            },
        )
