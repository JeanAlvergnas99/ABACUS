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
