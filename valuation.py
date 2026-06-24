import pandas as pd


def safe_number(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_market_cap(profile: dict) -> float:
    return safe_number(profile.get("marketCap")) or safe_number(profile.get("mktCap"))


def calculate_revenue_cagr(income):
    income = income.copy()
    income["date"] = pd.to_datetime(income["date"])
    income = income.sort_values("date")

    revenues = income["revenue"].dropna()
    revenue_cagr = 0.025

    if len(revenues) >= 2:
        first = safe_number(revenues.iloc[0])
        last = safe_number(revenues.iloc[-1])
        periods = len(revenues) - 1

        if first > 0 and last > 0:
            revenue_cagr = (last / first) ** (1 / periods) - 1

    return revenue_cagr


def build_dcf_dataframe(income, balance, cashflow):
    income = income.copy()
    balance = balance.copy()
    cashflow = cashflow.copy()

    for df in [income, balance, cashflow]:
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)

    rows = []
    previous_nwc = None

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

        tax_rate = income_tax / income_before_tax if income_before_tax > 0 else 0.21
        tax_rate = max(0.0, min(0.35, tax_rate))

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


def get_net_debt_and_shares(balance, profile, income=None):
    latest_bs = balance.copy()
    latest_bs["date"] = pd.to_datetime(latest_bs["date"])
    latest_bs = latest_bs.sort_values("date").iloc[-1]

    total_debt = safe_number(latest_bs.get("totalDebt"))
    cash = safe_number(latest_bs.get("cashAndCashEquivalents"))
    net_debt = total_debt - cash

    shares = 0.0

    for key in ["sharesOutstanding", "weightedAverageShsOut", "weightedAverageShsOutDil"]:
        shares = safe_number(profile.get(key))
        if shares > 0:
            return net_debt, shares

    if income is not None and not income.empty:
        latest_income = income.copy()
        latest_income["date"] = pd.to_datetime(latest_income["date"])
        latest_income = latest_income.sort_values("date").iloc[-1]

        for key in ["weightedAverageShsOut", "weightedAverageShsOutDil"]:
            shares = safe_number(latest_income.get(key))
            if shares > 0:
                return net_debt, shares

    price = safe_number(profile.get("price"))
    market_cap = get_market_cap(profile)

    if market_cap > 0 and price > 0:
        shares = market_cap / price

    if shares <= 0:
        raise ValueError("Shares outstanding could not be found.")

    return net_debt, shares


def calculate_wacc(income, balance, profile, risk_free_rate=0.0425):
    latest_income = income.copy()
    latest_balance = balance.copy()

    latest_income["date"] = pd.to_datetime(latest_income["date"])
    latest_balance["date"] = pd.to_datetime(latest_balance["date"])

    latest_income = latest_income.sort_values("date").iloc[-1]
    latest_balance = latest_balance.sort_values("date").iloc[-1]

    market_cap = get_market_cap(profile)
    total_debt = safe_number(latest_balance.get("totalDebt"))

    beta = safe_number(profile.get("beta"), 1.0)
    if beta <= 0:
        beta = 1.0

    equity_risk_premium = 0.045

    size_premium = 0.0
    if market_cap < 2_000_000_000:
        size_premium = 0.03
    elif market_cap < 10_000_000_000:
        size_premium = 0.02
    elif market_cap < 50_000_000_000:
        size_premium = 0.01

    interest_expense = abs(safe_number(latest_income.get("interestExpense")))
    ebit = safe_number(latest_income.get("operatingIncome"))
    income_before_tax = safe_number(latest_income.get("incomeBeforeTax"))
    income_tax = safe_number(latest_income.get("incomeTaxExpense"))

    tax_rate = income_tax / income_before_tax if income_before_tax > 0 else 0.21
    tax_rate = max(0.0, min(0.35, tax_rate))

    cost_of_equity = risk_free_rate + beta * equity_risk_premium + size_premium

    if interest_expense > 0:
        interest_coverage = ebit / interest_expense
    else:
        interest_coverage = 10.0

    if interest_coverage >= 8:
        credit_spread = 0.01
    elif interest_coverage >= 5:
        credit_spread = 0.02
    elif interest_coverage >= 3:
        credit_spread = 0.03
    elif interest_coverage >= 1:
        credit_spread = 0.05
    else:
        credit_spread = 0.08

    pre_tax_cost_of_debt = risk_free_rate + credit_spread
    pre_tax_cost_of_debt = max(0.02, min(0.15, pre_tax_cost_of_debt))

    after_tax_cost_of_debt = pre_tax_cost_of_debt * (1 - tax_rate)

    total_capital = market_cap + total_debt

    if total_capital > 0:
        equity_weight = market_cap / total_capital
        debt_weight = total_debt / total_capital
    else:
        equity_weight = 1.0
        debt_weight = 0.0

    wacc = equity_weight * cost_of_equity + debt_weight * after_tax_cost_of_debt
    wacc = max(0.055, min(0.18, wacc))

    return {
        "wacc": wacc,
        "beta": beta,
        "risk_free_rate": risk_free_rate,
        "equity_risk_premium": equity_risk_premium,
        "size_premium": size_premium,
        "cost_of_equity": cost_of_equity,
        "interest_coverage": interest_coverage,
        "credit_spread": credit_spread,
        "pre_tax_cost_of_debt": pre_tax_cost_of_debt,
        "after_tax_cost_of_debt": after_tax_cost_of_debt,
        "tax_rate": tax_rate,
        "market_cap": market_cap,
        "total_debt": total_debt,
        "equity_weight": equity_weight,
        "debt_weight": debt_weight,
    }


def calculate_terminal_growth(income, min_growth=0.02, max_growth=0.03):
    revenue_cagr = calculate_revenue_cagr(income)

    terminal_growth = revenue_cagr * 0.5
    terminal_growth = max(min_growth, min(max_growth, terminal_growth))

    return {
        "terminal_growth": terminal_growth,
        "revenue_cagr": revenue_cagr,
    }


def calculate_fcff_growth(dcf_table, income=None):
    fcff_series = dcf_table["fcff"].dropna()

    if len(fcff_series) < 2:
        fcff_cagr = 0.05
    else:
        start_fcff = float(fcff_series.iloc[0])
        end_fcff = float(fcff_series.iloc[-1])
        periods = len(fcff_series) - 1

        if start_fcff <= 0 or end_fcff <= 0:
            fcff_cagr = 0.05
        else:
            fcff_cagr = (end_fcff / start_fcff) ** (1 / periods) - 1

    revenue_cagr = calculate_revenue_cagr(income) if income is not None else fcff_cagr

    forecast_growth = min(fcff_cagr, revenue_cagr)
    forecast_growth = max(0.00, min(0.08, forecast_growth))

    return {
        "fcff_cagr": fcff_cagr,
        "revenue_cagr": revenue_cagr,
        "forecast_growth": forecast_growth,
    }


def run_dcf(historical_fcff, net_debt, shares_outstanding, wacc, forecast_growth, terminal_growth, years):
    if shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")

    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth.")

    clean_fcff = historical_fcff.dropna()

    if clean_fcff.empty:
        raise ValueError("FCFF is unavailable.")

    base_fcff = float(clean_fcff.iloc[-1])

    if base_fcff <= 0:
        base_fcff = float(clean_fcff.mean())

    if base_fcff <= 0:
        raise ValueError("FCFF is negative or unavailable.")

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
