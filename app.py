"""
Ranking survey - Supply Chain Resilience in the Philippine Tourism and Hospitality Industry

Run locally:   streamlit run app.py

How ties are prevented: respondents never pick a number. They tap factors in order of
significance - the first one tapped becomes Rank 1, the next Rank 2, and so on. A factor
leaves the list once it is ranked, so two factors can never share a rank, and the Next
button stays locked until every factor has been ranked.
"""

import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import storage
from survey_text import (TITLE, INTRO, CONSENT, DF_INTRO, RF_INTRO, CLOSING, DECLINED,
                         DRIVING_FACTORS, RESTRAINING_FACTORS)

st.set_page_config(page_title="Supply Chain Resilience Ranking", page_icon="📋",
                   layout="wide")

# quick lookups: code -> name / description
NAMES = {code: name for code, name, _ in DRIVING_FACTORS + RESTRAINING_FACTORS}
DESCRIPTIONS = {code: desc for code, _, desc in DRIVING_FACTORS + RESTRAINING_FACTORS}

STEPS = ["consent", "info", "df", "rf", "review"]
STEP_LABELS = ["Consent", "Your details", "Driving factors",
               "Restraining factors", "Review & submit"]


# Small layout tweaks:
#  - factor buttons are left-aligned so long names read naturally
#  - on wide screens, "Your ranking" stays visible while scrolling the list
#  - on phones (columns stack), "Your ranking" is shown above the list
CSS = """
<style>
.st-key-pool button, .st-key-pool button > div { justify-content: flex-start; text-align: left; }
.st-key-pool button > div { width: 100%; }
.st-key-pool [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) {
  margin: -0.3rem 0 0.6rem 0.25rem;
}
@media (min-width: 641px) {
  [data-testid="stColumn"]:has(.st-key-ranking_panel) {
    position: sticky; top: 4rem; align-self: flex-start;
    max-height: calc(100vh - 5rem); overflow-y: auto;
  }
}
@media (max-width: 640px) {
  [data-testid="stColumn"]:has(.st-key-ranking_panel) { order: -1; }
}
</style>
"""


# ---------------------------------------------------------------- session state
def init_state():
    defaults = {
        "step": "consent",
        "df_order": [],          # list of DF codes, position 0 = Rank 1
        "rf_order": [],
        "name": "", "position": "", "organization": "",
        "start_time": None,
        "page_changes": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to(step):
    st.session_state.step = step
    st.session_state.page_changes += 1   # used to scroll back to the top


def scroll_to_top():
    # the counter makes the snippet different each page so the browser runs it again
    st.html(
        f"<script>/* {st.session_state.page_changes} */"
        "var m = window.parent.document.querySelector('[data-testid=\"stMain\"]');"
        "if (m) {{ m.scrollTo(0, 0); }} window.scrollTo(0, 0);</script>",
        unsafe_allow_javascript=True,
    )


def show_progress():
    current = STEPS.index(st.session_state.step)
    st.progress((current + 1) / len(STEPS),
                text=f"Step {current + 1} of {len(STEPS)}: {STEP_LABELS[current]}")


# ---------------------------------------------------------------- ranking widget
def add_factor(order_key, code):
    if code not in st.session_state[order_key]:
        st.session_state[order_key].append(code)


def remove_factor(order_key, code):
    st.session_state[order_key].remove(code)


def move_factor(order_key, index, direction):
    order = st.session_state[order_key]
    new_index = index + direction
    order[index], order[new_index] = order[new_index], order[index]


def clear_ranking(order_key):
    st.session_state[order_key] = []


def ranking_section(order_key, factors, kind):
    """Tap-to-rank widget. Returns True when every factor has been ranked."""
    order = st.session_state[order_key]
    total = len(factors)
    unranked = [code for code, _, _ in factors if code not in order]

    st.info(
        f"**How to rank:** tap the {kind} factor you consider **most significant** first — "
        f"it becomes **Rank 1**. Then tap the next most significant (Rank 2), and so on "
        f"until all {total} are ranked. Each rank can only be given to one factor. "
        f"Use ↑ ↓ to adjust the order or ✕ to send a factor back."
    )
    st.progress(len(order) / total, text=f"Ranked {len(order)} of {total}")

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown(f"#### Factors left to rank ({len(unranked)})")
        if unranked:
            show_desc = st.toggle("Show descriptions", value=True, key=f"{order_key}_desc")
            st.caption(f"The next factor you tap becomes **Rank {len(order) + 1}**.")
            with st.container(key="pool", gap="small"):
                for code in unranked:
                    st.button(f"{code}. {NAMES[code]}", key=f"add_{code}", width="stretch",
                              on_click=add_factor, args=(order_key, code))
                    if show_desc:
                        st.caption(DESCRIPTIONS[code])
        else:
            st.success("All factors are ranked. Check your ranking, then press Next.")

    with right:
        with st.container(key="ranking_panel", gap="small"):
            st.markdown("#### Your ranking")
            if not order:
                st.caption("Nothing ranked yet. Tap a factor to give it Rank 1.")
            for i, code in enumerate(order):
                with st.container(border=True, horizontal=True, wrap=False,
                                  vertical_alignment="center", gap="small"):
                    st.markdown(f"**{i + 1}.** {code}. {NAMES[code]}",
                                help=DESCRIPTIONS[code], width="stretch")
                    st.button("↑", key=f"up_{code}", disabled=(i == 0),
                              on_click=move_factor, args=(order_key, i, -1),
                              help="Move up (more significant)", type="tertiary")
                    st.button("↓", key=f"down_{code}", disabled=(i == len(order) - 1),
                              on_click=move_factor, args=(order_key, i, 1),
                              help="Move down (less significant)", type="tertiary")
                    st.button("✕", key=f"del_{code}", on_click=remove_factor,
                              args=(order_key, code), help="Send back to the list",
                              type="tertiary")
            if order:
                st.button("Clear and start over", key=f"clear_{order_key}",
                          on_click=clear_ranking, args=(order_key,))

    return len(order) == total


# ---------------------------------------------------------------- pages
def page_consent():
    st.markdown(INTRO)
    with st.expander("Informed Consent, Data Privacy, and Background of the Thesis",
                     expanded=True):
        st.markdown(CONSENT)
    st.markdown("**Do you consent and allow the researchers to gather data from your "
                "response to the survey questionnaire?**")
    choice = st.radio("Consent", ["I agree to participate voluntarily.",
                                  "I do not agree to participate."],
                      index=None, key="consent_choice", label_visibility="collapsed")
    if st.button("Next", type="primary"):
        if choice is None:
            st.warning("Please choose one of the options above.")
        elif choice.startswith("I agree"):
            if st.session_state.start_time is None:
                st.session_state.start_time = time.time()
            go_to("info")
            st.rerun()
        else:
            go_to("declined")
            st.rerun()


def page_info():
    st.subheader("Participant Information")
    # widget values are copied into permanent keys so they survive going Back/Next
    for label, key in [("Participant name *", "name"),
                       ("Current position/designation *", "position"),
                       ("Organization or institution *", "organization")]:
        st.session_state[key] = st.text_input(label, value=st.session_state[key],
                                              key=f"w_{key}")
    back, nxt = st.columns(2)
    if back.button("Back"):
        go_to("consent")
        st.rerun()
    if nxt.button("Next", type="primary"):
        missing = [label for label, key in [("name", "name"), ("position", "position"),
                                            ("organization", "organization")]
                   if not st.session_state[key].strip()]
        if missing:
            st.warning("Please fill in your " + ", ".join(missing) + ".")
        else:
            go_to("df")
            st.rerun()


def page_ranking(order_key, factors, intro, title, kind, prev_step, next_step):
    st.subheader(title)
    st.markdown(intro)
    done = ranking_section(order_key, factors, kind)
    st.divider()
    back, nxt = st.columns(2)
    if back.button("Back", key=f"back_{order_key}"):
        go_to(prev_step)
        st.rerun()
    if nxt.button("Next", type="primary", key=f"next_{order_key}", disabled=not done):
        go_to(next_step)
        st.rerun()
    if not done:
        left = len(factors) - len(st.session_state[order_key])
        st.caption(f"Next unlocks once all factors are ranked ({left} left).")


def ranking_table(order):
    return pd.DataFrame({"Rank": range(1, len(order) + 1),
                         "Code": order,
                         "Factor": [NAMES[c] for c in order]})


def page_review():
    st.subheader("Review your answers")
    st.write(f"**Name:** {st.session_state.name}  \n"
             f"**Position:** {st.session_state.position}  \n"
             f"**Organization:** {st.session_state.organization}")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### Driving factors")
        st.dataframe(ranking_table(st.session_state.df_order), hide_index=True)
        if st.button("Edit driving factors"):
            go_to("df")
            st.rerun()
    with right:
        st.markdown("#### Restraining factors")
        st.dataframe(ranking_table(st.session_state.rf_order), hide_index=True)
        if st.button("Edit restraining factors"):
            go_to("rf")
            st.rerun()

    st.divider()
    if st.button("Submit my response", type="primary"):
        submit()


def submit():
    row = {
        "response_id": str(uuid.uuid4()),
        "submitted_at": datetime.now(ZoneInfo("Asia/Manila")).strftime("%Y-%m-%d %H:%M:%S"),
        "duration_sec": int(time.time() - (st.session_state.start_time or time.time())),
        "name": st.session_state.name.strip(),
        "position": st.session_state.position.strip(),
        "organization": st.session_state.organization.strip(),
    }
    # rank of each factor = its position in the list + 1
    for i, code in enumerate(st.session_state.df_order):
        row[code] = i + 1
    for i, code in enumerate(st.session_state.rf_order):
        row[code] = i + 1

    try:
        with st.spinner("Saving your response..."):
            storage.save_response(row)
    except Exception as error:
        # keep everything on screen so nothing is lost; they can just press Submit again
        st.error("Sorry, your response could not be saved. Please press Submit again. "
                 "If this keeps happening, contact the researchers.\n\n"
                 f"Details: {error}")
        return
    go_to("done")
    st.rerun()


# ---------------------------------------------------------------- main
init_state()
st.html(CSS)
st.title(TITLE)
scroll_to_top()

step = st.session_state.step
if step == "done":
    st.success("Your response has been recorded.")
    st.markdown(CLOSING)
elif step == "declined":
    st.markdown(DECLINED)
else:
    show_progress()
    if step == "consent":
        page_consent()
    elif step == "info":
        page_info()
    elif step == "df":
        page_ranking("df_order", DRIVING_FACTORS, DF_INTRO,
                     "Ranking of Driving Factors (DFs)", "driving", "info", "rf")
    elif step == "rf":
        page_ranking("rf_order", RESTRAINING_FACTORS, RF_INTRO,
                     "Ranking of Restraining Factors (RFs)", "restraining", "df", "review")
    elif step == "review":
        page_review()
