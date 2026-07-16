"""Shared ISIC Rev. 5 division-level taxonomy loader.

Used by both classifier.py (to build the TF-IDF corpus classification is
trained against) and export_submission.py (to expand short codes like
"R88" into their full class name for charts/tables, per rubric slide
30.i). Centralized here so the two stay in sync -- they must agree on
which 87 rows are actually "divisions".
"""
import pandas as pd

ISIC_FILE = "ISIC5_Exp_Notes_11Mar2024.xlsx"
CODE_COL = "ISIC Rev 5 Code (with Section)"


def load_divisions():
    """The 87 ISIC Rev. 5 divisions, each with its short code, title, and a
    text corpus (title + introductory text + includes) for classification.

    Division-level rows are identified by CODE_COL matching one letter
    followed by exactly two digits (e.g. "A01", "R88", "V99") -- the plain
    "ISIC Rev 5 Code" column can't be used for this: pandas reads it as
    numeric and silently drops the leading zero on single-digit divisions
    (01-09 become "1"-"9"), which corrupts any length-based filter and
    ends up training against a mix of group- and division-level rows.
    """
    df = pd.read_excel(ISIC_FILE, sheet_name="ISIC5")
    divisions = df[df[CODE_COL].astype(str).str.match(r"^[A-Z]\d{2}$")].copy()

    def make_corpus(row):
        cols = ["ISIC Rev 5 Title", "ISIC Rev 5 Introductory Text",
                "ISIC Rev 5 Includes", "ISIC Rev 5 Includes Also"]
        return " ".join(str(row[c]) for c in cols if pd.notna(row.get(c)))

    divisions["corpus"] = divisions.apply(make_corpus, axis=1)
    result = divisions[[CODE_COL, "ISIC Rev 5 Title"]].rename(
        columns={CODE_COL: "code", "ISIC Rev 5 Title": "title"}
    )
    result["corpus"] = divisions["corpus"].values
    return result.reset_index(drop=True)


def code_to_title_map():
    """{'R88': 'Social work activities without accommodation', ...}"""
    divisions = load_divisions()
    return dict(zip(divisions["code"], divisions["title"]))


def full_label(code, titles=None):
    """'R88' -> 'R88 - Social work activities without accommodation'.
    Pass a pre-built titles dict (from code_to_title_map()) when labeling
    many codes to avoid re-reading the spreadsheet each call."""
    if titles is None:
        titles = code_to_title_map()
    title = titles.get(code)
    return f"{code} - {title}" if title else str(code)
