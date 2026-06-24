# Abacus - Stock Intrinsic Value App

Abacus is a simple Streamlit app that estimates a stock's intrinsic value per share using a DCF model.

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Add your FMP API key

Create a file named `.env` in the project folder:

```bash
FMP_API_KEY=your_api_key_here
```

Or enter the API key directly in the Streamlit sidebar.

## 3. Run

```bash
streamlit run app.py
```

## What it does

1. User enters a stock ticker.
2. The app pulls financial statements from Financial Modeling Prep.
3. It estimates Free Cash Flow to Firm.
4. It runs a DCF using assumptions for WACC, growth, and terminal growth.
5. It returns enterprise value, equity value, and intrinsic price per share.

## Important

This is an educational valuation tool, not financial advice.
