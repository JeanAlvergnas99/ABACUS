import pandas as pd

from valuation import safe_number


def latest_historical_year(income):
    income = income.copy()
    income["date"] = pd.to_datetime(income["date"])
    return int(income["date"].dt.year.max())


def calculate_historical_assumptions(income, balance, cashflow):
    income = income.copy()
    balance = balance.copy()
    cashflow = cashflow.copy()

    for df in [income, balance, cashflow]:
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)

    rows = []

    for _, inc in income.iterrows():
        year = inc["date"].year

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

        depreciation = safe_number(cf.get("depreciationAndAmortization"))
        capex = abs(safe_number(cf.get("capitalExpenditure")))

        current_assets = safe_number(bs.get("totalCurrentAssets"))
        cash = safe_number(bs.get("cashAndCashEquivalents"))
        current_liabilities = safe_number(bs.get("totalCurrentLiabilities"))
        short_term_debt = safe_number(bs.get("shortTermDebt"))

        nwc = (current_assets - cash) - (current_liabilities - short_term_debt)

        if revenue > 0:
            rows.append({
                "year": year,
                "revenue": revenue,
                "ebit_margin": ebit / revenue,
                "tax_rate": income_tax / income_before_tax if income_before_tax > 0 else 0.21,
                "depreciation_pct": depreciation / revenue,
                "capex_pct": capex / revenue,
                "nwc_pct": nwc / revenue,
                "nwc": nwc,
            })

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("Could not calculate operating assumptions.")

    return {
        "ebit_margin": df["ebit_margin"].tail(3).mean(),
        "tax_rate": max(0.0, min(0.35, df["tax_rate"].tail(3).mean())),
        "depreciation_pct": df["depreciation_pct"].tail(3).mean(),
        "capex_pct": df["capex_pct"].tail(3).mean(),
        "nwc_pct": df["nwc_pct"].tail(3).mean(),
        "latest_nwc": df["nwc"].iloc[-1],
    }


def build_analyst_forecast(analyst_estimates, income, balance, cashflow, years=5):
    latest_year = latest_historical_year(income)
    assumptions = calculate_historical_assumptions(income, balance, cashflow)

    estimates = pd.DataFrame(analyst_estimates)

    if estimates.empty:
        raise ValueError("No analyst estimates available.")

    estimates["date"] = pd.to_datetime(estimates["date"])
    estimates["year"] = estimates["date"].dt.year

    estimates = estimates[estimates["year"] > latest_year]
    estimates = estimates.sort_values("year").head(years)

    if estimates.empty:
        raise ValueError("No future analyst estimates available.")

    rows = []
    previous_nwc = assumptions["latest_nwc"]

    for _, row in estimates.iterrows():
        year = int(row["year"])

        revenue = safe_number(row.get("revenueAvg"))
        ebit = safe_number(row.get("ebitAvg"))

        if revenue <= 0:
            continue

        if ebit <= 0:
            ebit = revenue * assumptions["ebit_margin"]

        tax_rate = assumptions["tax_rate"]
        nopat = ebit * (1 - tax_rate)

        depreciation = revenue * assumptions["depreciation_pct"]
        capex = revenue * assumptions["capex_pct"]

        nwc = revenue * assumptions["nwc_pct"]
        change_nwc = nwc - previous_nwc
        previous_nwc = nwc

        fcff = nopat + depreciation - capex - change_nwc

        rows.append({
            "forecast_year": len(rows) + 1,
            "year": year,
            "revenue": revenue,
            "ebit": ebit,
            "ebit_margin": ebit / revenue,
            "tax_rate": tax_rate,
            "nopat": nopat,
            "depreciation": depreciation,
            "capex": capex,
            "change_nwc": change_nwc,
            "fcff": fcff,
            "num_analysts_revenue": safe_number(row.get("numAnalystsRevenue")),
            "num_analysts_eps": safe_number(row.get("numAnalystsEps")),
        })

    forecast_df = pd.DataFrame(rows)

    if forecast_df.empty:
        raise ValueError("Could not build analyst operating forecast.")

    return forecast_df, assumptions


def run_dcf_from_forecast(forecast_df, net_debt, shares_outstanding, wacc, terminal_growth):
    if shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")

    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth.")

    forecast = forecast_df.copy()

    forecast["discount_factor"] = (1 + wacc) ** forecast["forecast_year"]
    forecast["present_value"] = forecast["fcff"] / forecast["discount_factor"]

    final_fcff = forecast.iloc[-1]["fcff"]

    if final_fcff <= 0:
        raise ValueError("Analyst forecast FCFF is negative or unavailable.")

    years = int(forecast["forecast_year"].max())

    terminal_value = final_fcff * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal_value = terminal_value / ((1 + wacc) ** years)

    enterprise_value = forecast["present_value"].sum() + pv_terminal_value
    equity_value = enterprise_value - net_debt
    intrinsic_price = equity_value / shares_outstanding

    return {
        "base_fcff": forecast.iloc[0]["fcff"],
        "forecast": forecast,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "intrinsic_price": intrinsic_price,
        "fcff_warning": None,
    }
