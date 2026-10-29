"""
Saving and loading survey responses.

Two places the answers can go:
  1. Google Sheets  - used when Google credentials are set in .streamlit/secrets.toml
                      (this is what you want once the survey is online)
  2. SQLite file    - used otherwise (responses.db next to this file, good for testing)

Every response is ONE row: who answered, when, and the rank given to every factor
(columns DF1..DF17 and RF1..RF19). That "wide" layout loads straight into pandas for EDA.
"""

import os
import sqlite3

import pandas as pd

from survey_text import DRIVING_FACTORS, RESTRAINING_FACTORS

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "responses.db")

INFO_COLUMNS = ["response_id", "submitted_at", "duration_sec",
                "name", "position", "organization"]
DF_CODES = [code for code, _, _ in DRIVING_FACTORS]
RF_CODES = [code for code, _, _ in RESTRAINING_FACTORS]
COLUMNS = INFO_COLUMNS + DF_CODES + RF_CODES


# ---------------------------------------------------------------- Google Sheets
def _get_secrets():
    """Return Streamlit secrets if they exist, otherwise None."""
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets and "sheet_url" in st.secrets:
            return st.secrets
    except Exception:
        pass
    return None


def _open_sheet(secrets):
    import gspread
    client = gspread.service_account_from_dict(dict(secrets["gcp_service_account"]))
    return client.open_by_url(secrets["sheet_url"]).sheet1


def _save_to_sheet(row, secrets):
    sheet = _open_sheet(secrets)
    # write the header row the first time
    if sheet.row_values(1) != COLUMNS:
        if sheet.row_values(1) == []:
            sheet.append_row(COLUMNS, value_input_option="RAW")
        else:
            raise RuntimeError("The first row of the Google Sheet does not match the "
                               "expected column names. Use an empty sheet.")
    sheet.append_row([row[c] for c in COLUMNS], value_input_option="RAW")


# ---------------------------------------------------------------- SQLite
def _save_to_sqlite(row):
    conn = sqlite3.connect(DB_PATH)
    rank_cols = ", ".join(f'"{c}" INTEGER' for c in DF_CODES + RF_CODES)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS responses ("
        "response_id TEXT PRIMARY KEY, submitted_at TEXT, duration_sec INTEGER, "
        "name TEXT, position TEXT, organization TEXT, " + rank_cols + ")"
    )
    placeholders = ", ".join("?" for _ in COLUMNS)
    col_names = ", ".join(f'"{c}"' for c in COLUMNS)
    conn.execute(f"INSERT INTO responses ({col_names}) VALUES ({placeholders})",
                 [row[c] for c in COLUMNS])
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- public functions
def check_ranking(ranks, codes):
    """True only if every factor has a rank and the ranks are exactly 1..N with no repeats."""
    values = [ranks.get(c) for c in codes]
    return sorted(values) == list(range(1, len(codes) + 1)) if None not in values else False


def save_response(row):
    """Save one response. Refuses to save anything that is not a complete, tie-free ranking."""
    if not check_ranking(row, DF_CODES) or not check_ranking(row, RF_CODES):
        raise ValueError("Ranking is incomplete or has repeated ranks - not saved.")

    secrets = _get_secrets()
    if secrets is not None:
        _save_to_sheet(row, secrets)
        return "Google Sheets"
    _save_to_sqlite(row)
    return "SQLite (" + DB_PATH + ")"


def load_responses(source=None):
    """
    Load all responses into a pandas DataFrame.
    source can be: a .db file, a .csv file (e.g. downloaded from Google Sheets),
    or None to use Google Sheets if configured, else the local responses.db.
    """
    if source is None:
        secrets = _get_secrets()
        if secrets is not None:
            return pd.DataFrame(_open_sheet(secrets).get_all_records())
        source = DB_PATH

    if source.endswith(".csv"):
        return pd.read_csv(source)

    conn = sqlite3.connect(source)
    df = pd.read_sql_query("SELECT * FROM responses", conn)
    conn.close()
    return df
