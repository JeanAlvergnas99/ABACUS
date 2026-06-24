import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from fmp_client import FMPClient
from valuation import (
    build_dcf_dataframe,
    calculate_fcff_growth,
    calculate_terminal_growth,
    calculate_wacc,
    get_net_debt_and_shares,
    run_dcf,
)


st.set_page_config(page_title="Abacus", layout="wide")

st.title("Abacus")
st.subheader("Intrinsic value calculator using a DCF model")

with st.sidebar:
    st.header("Inputs")

    api_key = st.text_input("FMP API Key", type="password")
    ticker = st.text_input("Ticker", value="AAPL").upper().strip()

    st.header("DCF Assumptions")

    use_auto_wacc = st.checkbox("Use automatic WACC", value=True)
    manual_wacc = st.slider("Manual WACC", 0.05, 0.20, 0.10, 0.01)

    use_auto_fcff_growth = st.checkbox("Use automatic FCFF growth", value=True)
    manual_forecast_growth = st.slider("Manual Annual FCFF Growth", -0.05, 0.15, 0.05, 0.01)

    use_auto_terminal_growth = st.checkbox("Use automatic terminal growth", value=True)
    manual_terminal_growth = st.slider("Manual Terminal Growth", 0.00, 0.05, 0.025, 0.005)

    years = st.slider("Forecast Years", 3, 10, 5, 1)

    run_button = st.button("Run valuation")


def to_billions(df, columns):
    df = df.copy()
    for col in columns:
        df[col] = df[col] / 1_000_000_000
    return df


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

            risk_free_rate = client.risk_free_rate_10y()

            dcf_table = build_dcf_dataframe(income, balance, cashflow)
            net_debt, shares = get_net_debt_and_shares(balance, profile, income)

            wacc_details = calculate_wacc(
                income=income,
                balance=balance,
                profile=profile,
                risk_free_rate=risk_free_rate,
            )

            terminal_growth_details = calculate_terminal_growth(income)
            fcff_growth_details = calculate_fcff_growth(dcf_table, income)

            selected_wacc = wacc_details["wacc"] if use_auto_wacc else manual_wacc
            selected_terminal_growth = (
                terminal_growth_details["terminal_growth"]
                if use_auto_terminal_growth
                else manual_terminal_growth
            )
            selected_forecast_growth = (
                fcff_growth_details["forecast_growth"]
                if use_auto_fcff_growth
                else manual_forecast_growth
            )

            results = run_dcf(
                historical_fcff=dcf_table["fcff"],
                net_debt=net_debt,
                shares_outstanding=shares,
                wacc=selected_wacc,
                forecast_growth=selected_forecast_growth,
                terminal_growth=selected_terminal_growth,
                years=years,
            )

            st.success("Valuation completed successfully.")

            current_price = profile.get("price")
            intrinsic_value = results["intrinsic_price"]

            if current_price:
                upside_downside = (intrinsic_value / current_price) - 1
            else:
                upside_downside = None

            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric("Intrinsic Value", f"${intrinsic_value:,.2f}")

            if current_price:
                col2.metric("Current Price", f"${current_price:,.2f}")
            else:
                col2.metric("Current Price", "N/A")

            if upside_downside is not None:
                col3.metric("Upside / Downside", f"{upside_downside:.2%}")
            else:
                col3.metric("Upside / Downside", "N/A")

            col4.metric("WACC", f"{selected_wacc:.2%}")
            col5.metric("FCFF Growth", f"{selected_forecast_growth:.2%}")

            st.divider()

            st.subheader("Valuation Overview")

            overview_col1, overview_col2 = st.columns(2)

            with overview_col1:
                valuation_fig = go.Figure()

                valuation_fig.add_trace(
                    go.Bar(
                        x=["Current Price", "Intrinsic Value"],
                        y=[
                            current_price if current_price else 0,
                            intrinsic_value,
                        ],
                        text=[
                            f"${current_price:,.2f}" if current_price else "N/A",
                            f"${intrinsic_value:,.2f}",
                        ],
                        textposition="auto",
                    )
                )

                valuation_fig.update_layout(
                    title="Current Price vs Intrinsic Value",
                    yaxis_title="Price per Share",
                    showlegend=False,
                    height=420,
                )

                st.plotly_chart(valuation_fig, use_container_width=True)

            with overview_col2:
                assumptions_fig = go.Figure()

                assumptions_fig.add_trace(
                    go.Bar(
                        x=["WACC", "FCFF Growth", "Terminal Growth"],
                        y=[
                            selected_wacc * 100,
                            selected_forecast_growth * 100,
                            selected_terminal_growth * 100,
                        ],
                        text=[
                            f"{selected_wacc:.2%}",
                            f"{selected_forecast_growth:.2%}",
                            f"{selected_terminal_growth:.2%}",
                        ],
                        textposition="auto",
                    )
                )

                assumptions_fig.update_layout(
                    title="Key DCF Assumptions",
                    yaxis_title="Rate (%)",
                    showlegend=False,
                    height=420,
                )

                st.plotly_chart(assumptions_fig, use_container_width=True)

            st.subheader("Business Fundamentals")

            fundamentals = to_billions(
                dcf_table[["year", "revenue", "ebit", "fcff"]],
                ["revenue", "ebit", "fcff"],
            )

            fundamentals_long = fundamentals.melt(
                id_vars="year",
                value_vars=["revenue", "ebit", "fcff"],
                var_name="Metric",
                value_name="Amount",
            )

            fundamentals_fig = px.line(
                fundamentals_long,
                x="year",
                y="Amount",
                color="Metric",
                markers=True,
                title="Revenue, EBIT, and FCFF",
                labels={"Amount": "Amount ($B)", "year": "Year"},
            )

            fundamentals_fig.update_layout(height=450)

            st.plotly_chart(fundamentals_fig, use_container_width=True)

            st.subheader("DCF Forecast")

            forecast = results["forecast"].copy()
            forecast["fcff"] = forecast["fcff"] / 1_000_000_000
            forecast["present_value"] = forecast["present_value"] / 1_000_000_000

            forecast_long = forecast.melt(
                id_vars="forecast_year",
                value_vars=["fcff", "present_value"],
                var_name="Metric",
                value_name="Amount",
            )

            forecast_fig = px.bar(
                forecast_long,
                x="forecast_year",
                y="Amount",
                color="Metric",
                barmode="group",
                title="Forecast FCFF vs Present Value",
                labels={
                    "forecast_year": "Forecast Year",
                    "Amount": "Amount ($B)",
                },
            )

            forecast_fig.update_layout(height=450)

            st.plotly_chart(forecast_fig, use_container_width=True)

            st.subheader("Automatic WACC Details")

            wacc_col1, wacc_col2, wacc_col3 = st.columns(3)

            wacc_col1.metric("Beta", f"{wacc_details['beta']:.2f}")
            wacc_col1.metric("Cost of Equity", f"{wacc_details['cost_of_equity']:.2%}")

            wacc_col2.metric("Pre-Tax Cost of Debt", f"{wacc_details['pre_tax_cost_of_debt']:.2%}")
            wacc_col2.metric("After-Tax Cost of Debt", f"{wacc_details['after_tax_cost_of_debt']:.2%}")

            wacc_col3.metric("Equity Weight", f"{wacc_details['equity_weight']:.2%}")
            wacc_col3.metric("Debt Weight", f"{wacc_details['debt_weight']:.2%}")

            st.subheader("Automatic Growth Details")

            growth_col1, growth_col2, growth_col3 = st.columns(3)

            growth_col1.metric("Historical FCFF CAGR", f"{fcff_growth_details['fcff_cagr']:.2%}")
            growth_col2.metric("Revenue CAGR", f"{fcff_growth_details['revenue_cagr']:.2%}")
            growth_col3.metric("Terminal Growth", f"{selected_terminal_growth:.2%}")

            with st.expander("View assumptions"):
                st.write(f"Risk-free rate / 10Y Treasury: {wacc_details['risk_free_rate']:.2%}")
                st.write(f"Equity risk premium: {wacc_details['equity_risk_premium']:.2%}")
                st.write(f"Size premium: {wacc_details['size_premium']:.2%}")
                st.write(f"Interest coverage: {wacc_details['interest_coverage']:.2f}x")
                st.write(f"Credit spread: {wacc_details['credit_spread']:.2%}")
                st.write(f"Tax rate: {wacc_details['tax_rate']:.2%}")
                st.write(f"Market cap: ${wacc_details['market_cap']:,.0f}")
                st.write(f"Total debt: ${wacc_details['total_debt']:,.0f}")
                st.write(f"Net debt: ${net_debt:,.0f}")
                st.write(f"Shares outstanding: {shares:,.0f}")
                st.write(f"Base FCFF: ${results['base_fcff']:,.0f}")

            with st.expander("View source data used by Abacus"):
                tab1, tab2, tab3, tab4, tab5 = st.tabs(
                    [
                        "Income Statement",
                        "Balance Sheet",
                        "Cash Flow",
                        "DCF Table",
                        "Forecast",
                    ]
                )

                with tab1:
                    st.dataframe(income.head())

                with tab2:
                    st.dataframe(balance.head())

                with tab3:
                    st.dataframe(cashflow.head())

                with tab4:
                    st.dataframe(dcf_table.head())

                with tab5:
                    st.dataframe(results["forecast"].head())

        except Exception as error:
            st.error(f"Could not run valuation: {error}")
