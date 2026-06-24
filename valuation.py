import numpy as np
import pandas as pd


def safe_number(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def build_dcf_dataframe(income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame) -> pd.DataFrame:
    """Builds a DCF-ready table from FMP statements.

    FCFF approximation:
    EBIT * (1 - tax rate) + D&A - CapEx - change in NWC
    """
    income = income.copy()
    balance = balance.copy()
    cashflow = cashflow.copy()

    for df in [income, balance, cashflow]:
        if "date" not in df.columns:
            raise ValueError("Financial statements are missing the date column.")
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)

    rows = []
    previous_nwc = None

    for _, inc in income.iterrows():
        date = inc["date"]
        year = date.year

        bs_match = balance[balance["date"].dt.year == year]
        cf_match = cashflow[cashflow["date"].dt.year == year]
        if bs_match.empty or cf_match.empty:
            continue

        bs = bs_match.iloc[0]
        cf = cf_match.iloc[0]

        revenue = safe_number(inc.get("revenue"))
        ebit = safe_number(inc.get("operatingIncome"))
        income_before_tax = safe_number(inc.get("incomeBeforeTax"))
        income_tax = safe_number(inc.get("incomeTaxExpense"))

        if income_before_tax > 0:
            tax_rate = max(0.0, min(0.35, income_tax / income_before_tax))
        else:
            tax_rate = 0.21

        depreciation = safe_number(cf.get("depreciationAndAmortization"))
        capex = abs(safe_number(cf.get("capitalExpenditure")))

        current_assets = safe_number(bs.get("totalCurrentAssets"))
        cash = safe_number(bs.get("cashAndCashEquivalents"))
        current_liabilities = safe_number(bs.get("totalCurrentLiabilities"))
        short_term_debt = safe_number(bs.get("shortTermDebt"))
        nwc = (current_assets - cash) - (current_liabilities - short_term_debt)

        change_nwc = 0.0 if previous_nwc is None else nwc - previous_nwc
        previous_nwc = nwc

        nopat = ebit * (1 - tax_rate)
        fcff = nopat + depreciation - capex - change_nwc

        rows.append({
            "year": year,
            "revenue": revenue,
            "ebit": ebit,
            "tax_rate": tax_rate,
            "nopat": nopat,
            "depreciation_amortization": depreciation,
            "capex": capex,
            "change_nwc": change_nwc,
            "fcff": fcff,
        })

    dcf = pd.DataFrame(rows)
    if dcf.empty:
        raise ValueError("Could not build DCF table from available financial data.")
    return dcf


def run_dcf(
    historical_fcff: pd.Series,
    net_debt: float,
    shares_outstanding: float,
    wacc: float = 0.10,
    forecast_growth: float = 0.05,
    terminal_growth: float = 0.025,
    years: int = 5,
) -> dict:
    """Runs a simple DCF model and returns valuation outputs."""
    if shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")
    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth.")

    base_fcff = float(historical_fcff.dropna().iloc[-1])
    if base_fcff <= 0:
        base_fcff = float(historical_fcff.dropna().mean())
    if base_fcff <= 0:
        raise ValueError("FCFF is negative or unavailable. This simple DCF needs positive FCFF.")

    forecast = []
    for year in range(1, years + 1):
        fcff = base_fcff * ((1 + forecast_growth) ** year)
        discount_factor = (1 + wacc) ** year
        present_value = fcff / discount_factor
        forecast.append({
            "forecast_year": year,
            "fcff": fcff,
            "discount_factor": discount_factor,
            "present_value": present_value,
        })

    forecast_df = pd.DataFrame(forecast)
    final_fcff = forecast_df.iloc[-1]["fcff"]
    terminal_value = final_fcff * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal_value = terminal_value / ((1 + wacc) ** years)

    enterprise_value = forecast_df["present_value"].sum() + pv_terminal_value
    equity_value = enterprise_value - net_debt
    intrinsic_price = equity_value / shares_outstanding

    return {
        "base_fcff": base_fcff,
        "forecast": forecast_df,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "intrinsic_price": intrinsic_price,
    }


def get_net_debt_and_shares(balance: pd.DataFrame, profile: dict) -> tuple[float, float]:
    """Extracts latest net debt and shares outstanding."""
    latest_bs = balance.copy()
    latest_bs["date"] = pd.to_datetime(latest_bs["date"])
    latest_bs = latest_bs.sort_values("date").iloc[-1]

    total_debt = safe_number(latest_bs.get("totalDebt"))
    cash = safe_number(latest_bs.get("cashAndCashEquivalents"))
    net_debt = total_debt - cash

    shares = safe_number(profile.get("mktCap")) / safe_number(profile.get("price"), 1.0)
    if shares <= 0:
        shares = safe_number(profile.get("sharesOutstanding"))

    return net_debt, shares
