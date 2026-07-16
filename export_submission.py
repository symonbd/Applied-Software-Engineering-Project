import sqlite3

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from isic_taxonomy import code_to_title_map, full_label

DB_NAME = "23088045-sq26-classification.db"
XLSX_NAME = "23088045-sq26-classification.xlsx"
REPORT_PDF_NAME = "SQ26_Classification_Report.pdf"

# Validated palette (see dataviz skill references/palette.md) — light-mode chart
# surface. Categorical hues are assigned in fixed order, never cycled.
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SEQUENTIAL_BLUE = "#2a78d6"  # step 450 — magnitude encodings (bar charts)
CATEGORICAL = {
    "QDA_PROJECT": "#2a78d6",    # slot 1 blue
    "QD_PROJECT": "#1baf7a",     # slot 2 aqua
    "OTHER_PROJECT": "#eda100",  # slot 3 yellow
    "NOT_A_PROJECT": "#008300",  # slot 4 green
}

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRIDLINE,
    "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "axes.titlecolor": INK_PRIMARY,
    "font.family": "sans-serif",
})


def clean_title(title):
    if pd.isna(title):
        return ""
    title = str(title).replace('\n', ' ').replace('\r', ' ').strip()
    if len(title) > 100:
        return title[:97] + "..."
    return title


def relabel_with_titles(class_counts, titles):
    """primary_class/secondary_class store short codes (e.g. "R88") --
    charts and tables display the full class name (rubric slide 30.i)."""
    relabeled = class_counts.copy()
    relabeled.index = [full_label(code, titles) for code in relabeled.index]
    return relabeled


def load_dataframe(conn):
    query = """
    SELECT
        p.repository_id,
        p.project_type,
        p.title as project_title,
        p.primary_class,
        p.secondary_class,
        (SELECT COUNT(*) FROM FILES f WHERE f.project_id = p.id) as no_project_files
    FROM PROJECTS p
    """
    df = pd.read_sql_query(query, conn)
    df['project_title'] = df['project_title'].apply(clean_title)
    # NOTE: don't blanket .astype(str) here -- that turns a real SQL NULL
    # (unclassifiable project, "leave it empty" per the rubric) into the
    # literal string "None", which then shows up as a fake class in charts
    # and the exported spreadsheet. Only clean values that are actually there.
    for col in ['project_type', 'primary_class', 'secondary_class']:
        df[col] = df[col].apply(
            lambda v: str(v).replace('\n', ' ').replace('\r', ' ').strip() if pd.notna(v) else None
        )
    return df


# Only these two project types get their own histogram/table/comment
# distribution (rubric slide 25 + slide 29's repository x project_type
# distribution matrix). OTHER_PROJECT/NOT_A_PROJECT are counted but not
# charted -- there's no primary_class to speak of for a NOT_A_PROJECT, and
# OTHER_PROJECT isn't one of the two types Step 3 asks to classify.
CHARTED_PROJECT_TYPES = ["QDA_PROJECT", "QD_PROJECT"]


LABEL_MAX_CHARS = 48
TABLE_LABEL_MAX_CHARS = 78


def truncate_label(label, max_chars=LABEL_MAX_CHARS):
    """Single-line label, never wrapped. Wrapping to 2-3 lines (the previous
    approach) needs more vertical space than either a barh chart with dozens
    of categories, or a fixed-row-height matplotlib table, actually gives
    each row -- in both cases long labels overflowed into their neighbor.
    Truncating keeps every label on exactly one line and legible."""
    label = str(label)
    if len(label) <= max_chars:
        return label
    return label[:max_chars - 1].rstrip() + "…"


def plot_histogram(ax, class_counts, title):
    """Horizontal bar chart of primary-class frequencies (barh avoids the
    left-to-right overlap long ISIC names create on a vertical axis)."""
    labels = [truncate_label(label) for label in class_counts.index]
    labels.reverse()
    values = class_counts.values.tolist()
    values.reverse()

    bars = ax.barh(labels, values, color=SEQUENTIAL_BLUE, height=0.65)
    ax.bar_label(bars, padding=3, color=INK_PRIMARY, fontsize=8)
    ax.set_title(title)
    ax.set_xlabel("Count")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)


def save_distribution_svg(class_counts, repo_id, project_type):
    """Standalone vector chart per (repository, project_type) distribution
    (rubric slide 30.iii: vector graphics so reviewers can zoom in)."""
    fig, ax = plt.subplots(figsize=(10, max(6, len(class_counts) * 0.4)))
    plot_histogram(ax, class_counts, f"{project_type} Primary Class Frequencies — Repository {repo_id}")
    plt.tight_layout()
    svg_name = f"Repository_{repo_id}_{project_type}_Chart.svg"
    plt.savefig(svg_name, format="svg", bbox_inches='tight')
    plt.close(fig)
    print(f"Saved vector histogram: {svg_name}")


def save_project_type_donut(df):
    """Donut chart of project-type composition across all repositories.
    Categorical identity encoding -> fixed hue order, direct labels (no
    hover available in a static export)."""
    counts = df['project_type'].value_counts()
    order = [t for t in CATEGORICAL if t in counts.index]
    counts = counts.reindex(order).dropna()
    if counts.empty:
        print("No project_type data to chart — skipping donut chart.")
        return

    colors = [CATEGORICAL[t] for t in counts.index]
    total = counts.sum()

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, _ = ax.pie(
        counts.values, colors=colors, startangle=90,
        wedgeprops=dict(width=0.4, edgecolor=SURFACE, linewidth=2),
    )
    ax.set_title("Project Type Composition (all repositories)")

    # Direct labels: category, count, and share — never color alone.
    labels = [f"{t}\n{c} ({c/total:.0%})" for t, c in counts.items()]
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
              frameon=False, labelcolor=INK_PRIMARY)

    plt.tight_layout()
    svg_name = "Project_Type_Composition.svg"
    plt.savefig(svg_name, format="svg", bbox_inches='tight')
    plt.close(fig)
    print(f"Saved vector donut chart: {svg_name}")


def save_file_extension_chart(conn, top_n=15):
    """Bar chart of the most common downloaded file extensions."""
    ext_df = pd.read_sql_query("SELECT file_type FROM FILES", conn)
    if ext_df.empty:
        print("No FILES rows to chart — skipping file-extension chart.")
        return

    counts = ext_df['file_type'].fillna("unknown").str.lower().value_counts().head(top_n)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(counts.index.astype(str), counts.values, color=SEQUENTIAL_BLUE, width=0.6)
    ax.bar_label(bars, padding=3, color=INK_PRIMARY, fontsize=8)
    ax.set_title(f"Top {len(counts)} Downloaded File Extensions")
    ax.set_ylabel("Count")
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    plt.xticks(rotation=45, ha="right")
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    plt.tight_layout()
    svg_name = "Top_File_Extensions.svg"
    plt.savefig(svg_name, format="svg", bbox_inches='tight')
    plt.close(fig)
    print(f"Saved vector file-extension chart: {svg_name}")


def _distribution_page(pdf, class_counts, repo_id, project_type, n_total_in_type):
    """Two pages for one (repository, project_type) distribution: a
    histogram sized to the number of classes (a busy distribution can have
    30-40+ distinct classes -- cramming that into a fixed-height page is
    what caused labels to collide), then a separate page for the
    rank-ordered top-20 table + comment."""
    fig_hist, ax_hist = plt.subplots(figsize=(11, max(6, len(class_counts) * 0.35)))
    plot_histogram(ax_hist, class_counts, f"{project_type} Primary Class Frequencies — Repository {repo_id}")
    plt.tight_layout()
    pdf.savefig(fig_hist)
    plt.close(fig_hist)

    top_20 = class_counts.head(20)
    fig_table = plt.figure(figsize=(11, 10))
    gs = fig_table.add_gridspec(2, 1, height_ratios=[5, 1.2], hspace=0.35)

    ax_table = fig_table.add_subplot(gs[0])
    ax_table.axis("off")
    table_data = [[str(rank), truncate_label(cls, TABLE_LABEL_MAX_CHARS), str(count)]
                  for rank, (cls, count) in enumerate(top_20.items(), 1)]
    table = ax_table.table(
        cellText=table_data,
        colLabels=["Rank", "ISIC Class", "Count"],
        colWidths=[0.08, 0.77, 0.15],
        loc="upper center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.3)
    ax_table.set_title(f"Top {len(top_20)} Classes — {project_type}, Repository {repo_id}",
                        loc="left", color=INK_PRIMARY)

    ax_comment = fig_table.add_subplot(gs[1])
    ax_comment.axis("off")
    dominant = class_counts.index[0]
    dominant_pct = class_counts.iloc[0] / n_total_in_type if n_total_in_type else 0
    comment = (
        f"Auto-generated summary — replace with your own findings before submitting.\n"
        f"{n_total_in_type} {project_type} project(s) analyzed. Dominant class: {dominant} "
        f"({class_counts.iloc[0]}/{n_total_in_type}, {dominant_pct:.0%}). "
        f"{len(class_counts)} distinct primary classes identified."
    )
    ax_comment.text(0, 1, comment, va="top", ha="left", fontsize=9,
                     color=INK_SECONDARY, wrap=True)

    pdf.savefig(fig_table)
    plt.close(fig_table)


def _summary_page(pdf, repo_id, type_counts):
    """One page per repository: a project-type counts table before its
    per-type distribution pages, matching slide 29's repository x
    project_type breakdown."""
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.axis("off")
    ax.set_title(f"Repository {repo_id} — Project Type Counts", loc="left", color=INK_PRIMARY)
    rows = [[t, str(type_counts.get(t, 0))] for t in
            ["QDA_PROJECT", "QD_PROJECT", "OTHER_PROJECT", "NOT_A_PROJECT"]]
    table = ax.table(cellText=rows, colLabels=["Project Type", "Count"],
                      colWidths=[0.3, 0.15], loc="upper left", cellLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)
    pdf.savefig(fig)
    plt.close(fig)


def build_report_pdf(df, titles):
    """Part 2 Step 4d, structured per slide 29: for each repository, a
    project-type summary, then a separate histogram + top-20 table +
    comment distribution for each of QDA_PROJECT and QD_PROJECT (the two
    types Part 2 Step 3 asks to classify). Auto-generated comments are
    factual summaries of the counts, not analysis -- read them and add
    your own interpretation before submitting."""
    with PdfPages(REPORT_PDF_NAME) as pdf:
        for repo_id in sorted(df['repository_id'].dropna().unique()):
            repo_id = int(repo_id)
            repo_df = df[df['repository_id'] == repo_id]
            type_counts = repo_df['project_type'].value_counts()
            _summary_page(pdf, repo_id, type_counts)

            for project_type in CHARTED_PROJECT_TYPES:
                type_df = repo_df[repo_df['project_type'] == project_type]
                class_counts = type_df['primary_class'].value_counts()
                if class_counts.empty:
                    continue
                _distribution_page(pdf, relabel_with_titles(class_counts, titles),
                                    repo_id, project_type, len(type_df))

    print(f"Saved combined report: {REPORT_PDF_NAME}")


def print_repo_stats(df, titles):
    for repo_id in df['repository_id'].dropna().unique():
        repo_id = int(repo_id)
        repo_df = df[df['repository_id'] == repo_id]

        total_projects = len(repo_df)
        qda_projects = len(repo_df[repo_df['project_type'] == 'QDA_PROJECT'])
        qd_projects = len(repo_df[repo_df['project_type'] == 'QD_PROJECT'])
        other_projects = len(repo_df[repo_df['project_type'] == 'OTHER_PROJECT'])
        not_a_project = len(repo_df[repo_df['project_type'] == 'NOT_A_PROJECT'])

        class_counts = relabel_with_titles(repo_df['primary_class'].value_counts(), titles)
        most_common = class_counts.index[0] if not class_counts.empty else "None"

        print(f"=== Repository ID: {repo_id} ===")
        print(f"Total projects: {total_projects}")
        print(f"No QDA_PROJECT found: {qda_projects}")
        print(f"No QD_PROJECT found: {qd_projects}")
        print(f"No OTHER_PROJECT found: {other_projects}")
        print(f"No NOT_A_PROJECT found: {not_a_project}")
        print(f"Dominant class: {most_common}")

        print(f"\nTop 20 Classes for Repo {repo_id}:")
        for rank, (cls_name, count) in enumerate(class_counts.head(20).items(), 1):
            print(f"{rank}. {cls_name} ({count})")
        print("=" * 40 + "\n")

        for project_type in CHARTED_PROJECT_TYPES:
            type_counts = repo_df[repo_df['project_type'] == project_type]['primary_class'].value_counts()
            if not type_counts.empty:
                save_distribution_svg(relabel_with_titles(type_counts, titles), repo_id, project_type)


def main():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)

    df = load_dataframe(conn)
    df.to_excel(XLSX_NAME, index=False)
    print(f"Exported data to {XLSX_NAME}\n")

    titles = code_to_title_map()
    print_repo_stats(df, titles)
    save_project_type_donut(df)
    save_file_extension_chart(conn)
    build_report_pdf(df, titles)

    conn.close()


if __name__ == "__main__":
    main()
