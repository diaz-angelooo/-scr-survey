"""
Exploratory data analysis of the ranking survey.

Usage:
    python eda.py                    # Google Sheets if configured, else responses.db
    python eda.py responses.db       # a SQLite file
    python eda.py responses.csv      # a CSV (e.g. File > Download > CSV from Google Sheets)

Everything is saved in the eda_output/ folder:
    responses_anonymized.csv  - data with names/orgs removed (R1, R2, ...)
    df_summary.csv            - descriptive stats + consensus ranking of driving factors
    rf_summary.csv            - same for restraining factors
    agreement.txt             - Kendall's W (how much the experts agree)
    *_mean_rank.png           - bar charts of mean rank
    *_heatmap.png             - every respondent's ranks at a glance
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import storage
from survey_text import DRIVING_FACTORS, RESTRAINING_FACTORS

OUT = "eda_output"
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ load
source = sys.argv[1] if len(sys.argv) > 1 else None
data = storage.load_responses(source)
print(f"Loaded {len(data)} responses")
if len(data) == 0:
    sys.exit("No responses yet.")

# ------------------------------------------------------------------ validity check
# The app already blocks ties, but this double-checks (e.g. if someone edits the sheet by hand).
groups = [("df", "Driving", DRIVING_FACTORS), ("rf", "Restraining", RESTRAINING_FACTORS)]
valid = pd.Series(True, index=data.index)
for _, _, factors in groups:
    codes = [c for c, _, _ in factors]
    ranks = data[codes].apply(pd.to_numeric, errors="coerce")
    is_perm = ranks.apply(lambda r: sorted(r.tolist()) == list(range(1, len(codes) + 1)), axis=1)
    valid &= is_perm
if (~valid).any():
    print(f"WARNING: {(~valid).sum()} response(s) are not complete 1..N rankings and were "
          f"dropped: {data.loc[~valid, 'response_id'].tolist()}")
data = data[valid].reset_index(drop=True)

# ------------------------------------------------------------------ anonymize
data.insert(0, "respondent", [f"R{i + 1}" for i in range(len(data))])
anon = data.drop(columns=["name", "organization"])
anon.to_csv(os.path.join(OUT, "responses_anonymized.csv"), index=False)

print(f"\nValid responses: {len(data)}")
print(f"Median completion time: {data['duration_sec'].astype(float).median() / 60:.1f} min")
print("\nPositions of respondents:")
print(data["position"].value_counts().to_string())

agreement_lines = []

# ------------------------------------------------------------------ per section
for prefix, label, factors in groups:
    codes = [c for c, _, _ in factors]
    names = {c: n for c, n, _ in factors}
    ranks = data[codes].astype(int)          # rows = respondents, columns = factors
    m, n = ranks.shape                       # m experts, n factors

    # --- descriptive statistics (rank 1 = most significant, so LOWER mean = more significant)
    summary = pd.DataFrame({
        "code": codes,
        "factor": [names[c] for c in codes],
        "mean_rank": ranks.mean().values,
        "sd": ranks.std(ddof=1).values if m > 1 else np.nan,
        "median_rank": ranks.median().values,
        "min_rank": ranks.min().values,
        "max_rank": ranks.max().values,
        "rank_sum": ranks.sum().values,
        "pct_ranked_top3": (ranks <= 3).mean().values * 100,
    })
    summary = summary.sort_values("mean_rank").reset_index(drop=True)
    summary.insert(0, "consensus_rank", range(1, n + 1))
    summary.round(2).to_csv(os.path.join(OUT, f"{prefix}_summary.csv"), index=False)

    print(f"\n=== {label} factors: consensus ranking (lower mean rank = more significant) ===")
    print(summary[["consensus_rank", "code", "factor", "mean_rank", "sd", "pct_ranked_top3"]]
          .round(2).to_string(index=False))

    # --- Kendall's coefficient of concordance W (no ties possible, so the simple formula works)
    R = ranks.sum().values
    S = ((R - R.mean()) ** 2).sum()
    W = 12 * S / (m ** 2 * (n ** 3 - n))
    chi2 = m * (n - 1) * W                   # Friedman chi-square
    p = stats.chi2.sf(chi2, n - 1)
    if W < 0.1:
        strength = "very weak"
    elif W < 0.3:
        strength = "weak"
    elif W < 0.5:
        strength = "moderate"
    elif W < 0.7:
        strength = "strong"
    else:
        strength = "very strong"
    line = (f"{label} factors: Kendall's W = {W:.3f} ({strength} agreement), "
            f"chi-square({n - 1}) = {chi2:.2f}, p = {p:.4f}, m = {m} experts")
    print(line)
    agreement_lines.append(line)

    # --- bar chart of mean rank with SD error bars
    plt.figure(figsize=(9, 0.45 * n + 1.5))
    labels = [f"{c}  {names[c]}" for c in summary["code"]]
    plt.barh(labels[::-1], summary["mean_rank"][::-1],
             xerr=summary["sd"][::-1] if m > 1 else None, color="#4C72B0", capsize=3)
    plt.xlabel("Mean rank (1 = most significant)")
    plt.title(f"{label} factors - mean rank across {m} experts")
    plt.xlim(0, n + 1)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f"{prefix}_mean_rank.png"), dpi=150)
    plt.close()

    # --- heatmap: each respondent's rank for each factor (factors in consensus order)
    ordered = ranks[summary["code"]]
    plt.figure(figsize=(0.45 * n + 2, 0.35 * m + 1.8))
    plt.imshow(ordered.values, cmap="viridis_r", aspect="auto", vmin=1, vmax=n)
    plt.colorbar(label="Rank given")
    plt.xticks(range(n), ordered.columns, rotation=90)
    plt.yticks(range(m), data["respondent"])
    plt.title(f"{label} factors - ranks by respondent")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f"{prefix}_heatmap.png"), dpi=150)
    plt.close()

with open(os.path.join(OUT, "agreement.txt"), "w") as f:
    f.write("\n".join(agreement_lines) + "\n")
    f.write("\nGuide: W ranges from 0 (no agreement) to 1 (all experts gave identical "
            "rankings). A significant p-value (< 0.05) means the agreement is unlikely "
            "to be due to chance.\n")

print(f"\nSaved tables and charts to {OUT}/")
