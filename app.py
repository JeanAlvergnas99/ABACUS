import streamlit as st

from fmp_client import FMPClient
from valuation import (
    build_dcf_dataframe,
    calculate_wacc,
    get_net_debt_and_shares,
    run_dcf,
)


st.set_page_config(page_title="Abacus", layout="wide")

st.title("Abacus")
st.subheader("Simple intrinsic value calculator using a DCF model")

with st.sidebar:
    st.header("Inputs")

    api_key = st.text_input("FMP API Key", type="password")
    ticker = st.text_input("Ticker", value="AAPL").upper().strip()

    st.header("DCF Assumptions")

    use_auto_wacc = st.checkbox("Use automatic WACC", value=True)

    manual_wacc = st.slider("Manual WACC", 0.05, 0.20, 0.10, 0.01)
    forecast_growth = st.slider("Annual FCFF Growth", -0.05, 0.15, 0.05, 0.01)
    terminal_growth = st.slider("Terminal Growth", 0.00, 0.05, 0.025, 0.005)
    years = st.slider("Forecast Years", 3, 10, 5, 1)

    run_button = st.button("Run valuation")


if run_button:
    if not api_key:
        st.error("Please enter your FMP API key.")
    elif not ticker:
        st.error("Please enter a ticker.")
    else:
        try:
            client = FMPClient(api_key=api_key)

            income = client.income_statement(ticker, limit=5)
            balance = client.balance_sheet(ticker, limit=5)
            cashflow = client.cash_flow(ticker, limit=5)
            profile = client.profile(ticker)

            dcf_table = build_dcf_dataframe(income, balance, cashflow)

            net_debt, shares = get_net_debt_and_shares(
                balance=balance,
                profile=profile,
                income=income,
            )

            wacc_details = calculate_wacc(
                income=income,
                balance=balance,
                profile=profile,
            )

            selected_wacc = wacc_details["wacc"] if use_auto_wacc else manual_wacc

            results = run_dcf(
                historical_fcff=dcf_table["fcff"],
                net_debt=net_debt,
                shares_outstanding=shares,
                wacc=selected_wacc,
                forecast_growth=forecast_growth,
                terminal_growth=terminal_growth,
                years=years,
            )

            st.success("Valuation completed successfully.")

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Intrinsic Value / Share",
                f"${results['intrinsic_price']:,.2f}",
            )

            col2.metric(
                "Enterprise Value",
                f"${results['enterprise_value'] / 1_000_000_000:,.2f}B",
            )

            col3.metric(
                "Equity Value",
                f"${results['equity_value'] / 1_000_000_000:,.2f}B",
            )

            col4.metric(
                "WACC Used",
                f"{selected_wacc:.2%}",
            )

            st.subheader("Automatic WACC Details")

            wacc_col1, wacc_col2, wacc_col3 = st.columns(3)

            wacc_col1.metric("Beta", f"{wacc_details['beta']:.2f}")
            wacc_col1.metric("Cost of Equity", f"{wacc_details['cost_of_equity']:.2%}")

            wacc_col2.metric("Pre-Tax Cost of Debt", f"{wacc_details['pre_tax_cost_of_debt']:.2%}")
            wacc_col2.metric("After-Tax Cost of Debt", f"{wacc_details['after_tax_cost_of_debt']:.2%}")

            wacc_col3.metric("Equity Weight", f"{wacc_details['equity_weight']:.2%}")
            wacc_col3.metric("Debt Weight", f"{wacc_details['debt_weight']:.2%}")

            with st.expander("View WACC assumptions"):
                st.write(f"Risk-free rate: {wacc_details['risk_free_rate']:.2%}")
                st.write(f"Equity risk premium: {wacc_details['equity_risk_premium']:.2%}")
                st.write(f"Tax rate: {wacc_details['tax_rate']:.2%}")
                st.write(f"Market cap: ${wacc_details['market_cap']:,.0f}")
                st.write(f"Total debt: ${wacc_details['total_debt']:,.0f}")

                if not use_auto_wacc:
                    st.warning("Manual WACC override is active.")

            st.subheader("DCF Historical Table")
            st.dataframe(dcf_table)

            st.subheader("Forecast")
            st.dataframe(results["forecast"])

            st.subheader("Key Inputs Used")
            st.write(f"Net debt: ${net_debt:,.0f}")
            st.write(f"Shares outstanding: {shares:,.0f}")
            st.write(f"Base FCFF: ${results['base_fcff']:,.0f}")

        except Exception as error:
            st.error(f"Could not run valuation: {error}")
