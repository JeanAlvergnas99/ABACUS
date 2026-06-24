import streamlit as st
import pandas as pd

from fmp_client import FMPClient
from valuation import build_dcf_dataframe, run_dcf, get_net_debt_and_shares


st.set_page_config(page_title="Abacus", page_icon="📊", layout="wide")

st.title("Abacus")
st.subheader("Simple intrinsic value calculator using a DCF model")

with st.sidebar:
    st.header("Inputs")
    api_key = st.text_input("FMP API Key", type="password")
    ticker = st.text_input("Ticker", value="AAPL").upper().strip()

    st.header("DCF Assumptions")
    wacc = st.slider("WACC", 0.05, 0.20, 0.10, 0.005)
    forecast_growth = st.slider("Annual FCFF Growth", -0.05, 0.20, 0.05, 0.005)
    terminal_growth = st.slider("Terminal Growth", 0.00, 0.05, 0.025, 0.0025)
    years = st.slider("Forecast Years", 3, 10, 5, 1)

    run_button = st.button("Run valuation")


if not run_button:
    st.info("Enter a ticker and click Run valuation.")
    st.stop()

try:
    client = FMPClient(api_key=st.secrets["FMP_API_KEY"])

    with st.spinner("Fetching financial statements..."):
        income = client.income_statement(ticker, limit=6)
        balance = client.balance_sheet(ticker, limit=6)
        cashflow = client.cash_flow(ticker, limit=6)
        profile = client.profile(ticker)

    dcf_df = build_dcf_dataframe(income, balance, cashflow)
    net_debt, shares = get_net_debt_and_shares(balance, profile)

    result = run_dcf(
        historical_fcff=dcf_df["fcff"],
        net_debt=net_debt,
        shares_outstanding=shares,
        wacc=wacc,
        forecast_growth=forecast_growth,
        terminal_growth=terminal_growth,
        years=years,
    )

    current_price = profile.get("price")
    company_name = profile.get("companyName", ticker)

    st.success(f"Valuation complete for {company_name} ({ticker})")

    col1, col2, col3 = st.columns(3)
    col1.metric("Intrinsic Price / Share", f"${result['intrinsic_price']:,.2f}")
    if current_price:
        col2.metric("Current Price", f"${float(current_price):,.2f}")
        upside = (result["intrinsic_price"] / float(current_price) - 1) * 100
        col3.metric("Implied Upside / Downside", f"{upside:,.1f}%")
    else:
        col2.metric("Enterprise Value", f"${result['enterprise_value']:,.0f}")
        col3.metric("Equity Value", f"${result['equity_value']:,.0f}")

    st.divider()

    st.header("DCF Output")
    output = pd.DataFrame({
        "Metric": [
            "Base FCFF",
            "PV of Forecast FCFF",
            "Terminal Value",
            "PV of Terminal Value",
            "Enterprise Value",
            "Net Debt",
            "Equity Value",
            "Shares Outstanding",
            "Intrinsic Price / Share",
        ],
        "Value": [
            result["base_fcff"],
            result["forecast"]["present_value"].sum(),
            result["terminal_value"],
            result["pv_terminal_value"],
            result["enterprise_value"],
            net_debt,
            result["equity_value"],
            shares,
            result["intrinsic_price"],
        ],
    })
    st.dataframe(output, use_container_width=True)

    st.header("Forecast")
    st.dataframe(result["forecast"], use_container_width=True)

    st.header("Historical DCF Inputs")
    st.dataframe(dcf_df, use_container_width=True)

    st.caption("Educational tool only. This is not investment advice.")

except Exception as e:
    st.error(f"Could not run valuation: {e}")
