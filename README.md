# Marketing Budget Allocation Simulator

A Streamlit simulator for marketing channel mix planning, CAC, ROI, payback, revenue forecasting, contribution analysis, and budget trade-off recommendations.

## Live Demo

[Open the Streamlit app](https://budget-allocation-simulator.streamlit.app/)

## What It Does

- Simulates current vs recommended marketing budget allocation
- Models diminishing returns by channel using spend elasticity assumptions
- Calculates projected customers, revenue, gross profit, contribution, CAC, ROAS, contribution ROI, LTV:CAC, and payback
- Reallocates budget across channels while respecting minimum and maximum spend constraints
- Shows channel-level spend, revenue, contribution, and customer changes
- Generates an executive budget allocation memo
- Supports CSV upload for custom channel assumptions

## Why This Project Matters

This project demonstrates marketing strategy and commercial planning. It shows how a growth, marketing analytics, business analyst, or consulting team can evaluate where the next marketing dollar should go before changing channel budgets.

## Tech Stack

- Python
- Streamlit
- Pandas
- Standard-library tests with `unittest`

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Validate

```bash
python scripts/validate.py
```

## Methodology Notes

- Channel response uses diminishing returns: projected customers scale with spend raised to each channel's elasticity.
- Allocation scores combine contribution ROI, CAC efficiency, payback speed, retention quality, and strategic priority.
- A risk adjustment reduces channel attractiveness before budget is allocated.
- Recommended spend is constrained by each channel's minimum and maximum budget limits.
- This is a planning simulator, not a substitute for incrementality testing, attribution analysis, or media-mix modeling.

## Portfolio Talking Points

- Built a marketing budget simulator that connects channel spend to revenue, CAC, contribution, payback, and LTV:CAC
- Added diminishing-return response curves so budget changes do not scale unrealistically
- Created a constrained allocation model with minimum and maximum channel spend limits
- Converted the scenario output into an executive memo for marketing strategy and business planning discussions

## Author

Dhruv Harlalka

MBA Finance, Middlesex University Dubai
