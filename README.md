# CFPL 2026/27 Dashboard

A Streamlit dashboard for:

**CHINCHINIM FPL 26/27 by ABSgym**  
League ID: **402686**

## Features

- Automatic current mini-league standings
- Latest completed Gameweek results
- Manager of the Gameweek
- Monthly standings
- Manager of the Month
- Transfer-hit deductions
- Joint winners on tied scores
- Manager of the Month Hall of Fame
- Manual refresh button
- Automatic 5-minute API cache

## Manager-of-the-Month rule

Each FPL Gameweek is assigned to the calendar month containing that Gameweek's
**official FPL deadline**.

For each manager:

Monthly score = sum of Gameweek points in that month - transfer-hit costs

Examples:
- A -4 hit reduces the monthly score by 4.
- A -8 hit reduces the monthly score by 8.
- If two managers finish on the same highest score, both are shown as joint winners.

You can turn off hit deductions in the app sidebar if your CFPL rules use raw GW points.

## Run on your computer

1. Install Python 3.10 or newer.
2. Open Command Prompt / Terminal in this folder.
3. Install packages:

   pip install -r requirements.txt

4. Start the app:

   streamlit run app.py

5. Streamlit will open the dashboard in your browser.

## Put it online for free with Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload:
   - app.py
   - requirements.txt
3. Go to Streamlit Community Cloud.
4. Create a new app from that GitHub repository.
5. Set the main file to `app.py`.
6. Deploy.

The app then gets a shareable web link that can be opened on a phone or computer.

## Data

The dashboard reads current public Fantasy Premier League endpoints at runtime.
No passwords or FPL login details are stored.
