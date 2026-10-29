# Supply Chain Resilience Ranking Survey

A small Streamlit web app that replaces the Google Form. Respondents **tap factors in order**
(first tap = Rank 1, next = Rank 2, ...) instead of picking a number for each factor, so two
factors can never get the same rank. The Next button stays locked until every factor is ranked,
and the save function refuses anything that is not a complete 1..N ranking.

## Files

| File | What it is |
|---|---|
| `app.py` | The survey (consent → details → driving factors → restraining factors → review → submit) |
| `survey_text.py` | All wording and the 17 DFs / 19 RFs. Edit text here, not in `app.py`. |
| `storage.py` | Saves each response as one row to Google Sheets (online) or `responses.db` (local) |
| `eda.py` | Summary tables, Kendall's W, and charts from the collected responses |
| `.streamlit/secrets.toml.example` | Template for the Google Sheets credentials |

## 1. Try it on your computer

```bash
pip install -r requirements.txt
streamlit run app.py
```

It opens in your browser. With no Google credentials set, answers are saved to `responses.db`
in this folder. Delete that file before going live so test answers don't mix with real ones.

## 2. Put it online (free) with answers saved to Google Sheets

A local `responses.db` only works on your own machine, and free hosting wipes local files when
the app restarts, so online responses should go to a Google Sheet.

**a. Make the Google Sheet and a "robot" account that can write to it**

1. Create an empty Google Sheet. Copy its URL.
2. Go to <https://console.cloud.google.com>, create a project.
3. In *APIs & Services → Library*, enable **Google Sheets API** and **Google Drive API**.
4. In *APIs & Services → Credentials*, create a **Service account**. Open it → *Keys* →
   *Add key → JSON*. A `.json` file downloads.
5. Open the Google Sheet → **Share** → paste the service account's email
   (`something@your-project.iam.gserviceaccount.com`) → give it **Editor** access.

**b. Fill in the secrets**

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, paste the sheet URL, and
copy each value from the downloaded JSON into it. Run `streamlit run app.py` again and submit a
test response; it should appear in the sheet (the header row is written automatically).

**c. Deploy on Streamlit Community Cloud**

1. Upload this folder to a GitHub repository (it can be private). **Do not upload
   `secrets.toml` or the JSON key** — `.gitignore` already excludes them.
2. Go to <https://share.streamlit.io>, sign in with GitHub, *Create app*, pick the repo and
   `app.py`.
3. Under *Advanced settings → Secrets*, paste the whole contents of your `secrets.toml`.
4. Deploy and send the link to respondents. Test it once on a phone before sending.

Free apps go to sleep after a while without visitors; the first person to open the link after
that just waits a moment for it to wake up. Saved answers in the sheet are not affected.

## 3. Analyse the results

```bash
python eda.py                  # reads Google Sheets (if secrets set) or responses.db
python eda.py responses.csv    # or a CSV downloaded from the sheet (File → Download → CSV)
```

Outputs go to `eda_output/`:

- `responses_anonymized.csv` — names and organizations removed, respondents labelled R1, R2, …
- `df_summary.csv`, `rf_summary.csv` — mean, SD, median, min/max rank, rank sum, % of experts
  who put the factor in their top 3, and the resulting consensus ranking (lowest mean rank = most significant)
- `agreement.txt` — Kendall's coefficient of concordance W with its chi-square test, i.e. how
  much the experts agree with each other
- `df_mean_rank.png`, `rf_mean_rank.png`, `df_heatmap.png`, `rf_heatmap.png`

In pandas, `storage.load_responses()` gives you the same data as a DataFrame for any extra analysis.

## Data layout

One row per respondent:

`response_id, submitted_at, duration_sec, name, position, organization, DF1 … DF17, RF1 … RF19`

Each DF/RF column holds the rank that respondent gave that factor (1 = most significant).
`duration_sec` is the time from giving consent to submitting, useful for spotting rushed answers.
