import os
import shutil
import sqlite3
import warnings

from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity

from config import QDA_EXTENSIONS, PRIMARY_EXTENSIONS
from isic_taxonomy import load_divisions, ISIC_FILE
from logger import logger

warnings.filterwarnings('ignore')

DATABASE_NAME = "23088045-sq26.db"
CLASSIFICATION_DB = "23088045-sq26-classification.db"

QDA_EXTS = set(e.lower() for e in QDA_EXTENSIONS)
PRIMARY_EXTS = set(e.lower() for e in PRIMARY_EXTENSIONS)

# Words like "research"/"study"/"data" are boilerplate on a *qualitative
# research data* archive -- nearly every project title contains them
# ("Data for: A Qualitative Study of..."). Standard English stopword lists
# don't catch these because they're not generic English function words.
# Left unfiltered, they get inflated IDF weight (they're rare across the
# 87 ISIC division blurbs, appearing mostly in N72 "Scientific research and
# development"), which systematically drags nearly every project toward
# N72/N73 regardless of actual subject matter.
DOMAIN_GENERIC_STOPWORDS = {
    'research', 'study', 'studies', 'data', 'dataset', 'datasets',
    'project', 'qualitative', 'analysis', 'supplementary', 'supporting',
}
CUSTOM_STOP_WORDS = list(ENGLISH_STOP_WORDS.union(DOMAIN_GENERIC_STOPWORDS))


def setup_database():
    shutil.copy(DATABASE_NAME, CLASSIFICATION_DB)
    conn = sqlite3.connect(CLASSIFICATION_DB, timeout=30.0)
    cur = conn.cursor()
    for col in ['primary_class', 'secondary_class', 'project_type']:
        try:
            cur.execute(f"ALTER TABLE PROJECTS ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    try:
        cur.execute("ALTER TABLE FILES ADD COLUMN class TEXT")
    except sqlite3.OperationalError:
        pass

    # Reset old classifications so this can be re-run with current parameters
    cur.execute("UPDATE PROJECTS SET primary_class = NULL, secondary_class = NULL, project_type = NULL")
    cur.execute("UPDATE FILES SET class = NULL")
    conn.commit()
    return conn


def assign_project_types(conn):
    """PROJECT_TYPE per rubric (Part 2 Step 1):
    QDA_PROJECT   -> has a file with a QDA extension
    QD_PROJECT    -> not QDA_PROJECT, but has a primary-data file
    OTHER_PROJECT -> not QD_PROJECT, but has at least one file
    NOT_A_PROJECT -> no files at all
    """
    cur = conn.cursor()
    cur.execute("SELECT id FROM PROJECTS")
    project_ids = [row[0] for row in cur.fetchall()]

    for pid in project_ids:
        cur.execute("SELECT file_type FROM FILES WHERE project_id = ?", (pid,))
        exts = {f".{(row[0] or '').lower().lstrip('.')}" for row in cur.fetchall() if row[0]}

        if exts & QDA_EXTS:
            project_type = "QDA_PROJECT"
        elif exts & PRIMARY_EXTS:
            project_type = "QD_PROJECT"
        elif exts:
            project_type = "OTHER_PROJECT"
        else:
            project_type = "NOT_A_PROJECT"

        cur.execute("UPDATE PROJECTS SET project_type = ? WHERE id = ?", (project_type, pid))
    conn.commit()
    logger.info(f"Assigned project_type for {len(project_ids)} projects")


def train_classifier():
    """Labels are short ISIC division codes (e.g. "R88"), not the full
    class name -- primary_class/secondary_class store the code alone, and
    the report expands codes to full names via isic_taxonomy.full_label()
    when displaying (rubric slide 30.i wants the full name as the bin
    label, but the stored classification value should be the code)."""
    divisions = load_divisions()

    # max_df=0.7: ignore words in >70% of docs (drops generic noise like "research", "data")
    # min_df=2: ignore words that appear only once (drops typos/one-off noise)
    vectorizer = TfidfVectorizer(stop_words=CUSTOM_STOP_WORDS, max_df=0.7, min_df=2)
    tfidf_matrix = vectorizer.fit_transform(divisions['corpus'])

    return vectorizer, tfidf_matrix, divisions['code'].tolist()


def _top2_labels(doc, vectorizer, tfidf_matrix, labels):
    vec = vectorizer.transform([doc])
    if vec.nnz == 0:
        return None, None
    sims = cosine_similarity(vec, tfidf_matrix).flatten()
    top2_idx = sims.argsort()[-2:][::-1]
    return labels[top2_idx[0]], labels[top2_idx[1]]


def classify_projects(conn, vectorizer, tfidf_matrix, labels):
    cur = conn.cursor()
    cur.execute("SELECT id, title, description FROM PROJECTS")
    projects = cur.fetchall()

    for pid, title, desc in projects:
        doc = f"{title or ''} {desc or ''}".strip()
        primary, secondary = _top2_labels(doc, vectorizer, tfidf_matrix, labels)
        conn.execute("UPDATE PROJECTS SET primary_class = ?, secondary_class = ? WHERE id = ?",
                     (primary, secondary, pid))
    conn.commit()
    logger.info(f"Classified {len(projects)} projects")


def classify_files(conn, vectorizer, tfidf_matrix, labels):
    """Part 2 Step 3: for QDA_PROJECT and QD_PROJECT types, classify each
    primary data file individually, not just the project as a whole.
    File content isn't extracted (Tier 2 would parse DOC/TXT bodies), so the
    document here is the project's own title/description plus the file name
    -- the metadata-only (Tier 1) signal available today."""
    cur = conn.cursor()
    cur.execute("""
        SELECT f.id, f.file_name, f.file_type, p.title, p.description
        FROM FILES f
        JOIN PROJECTS p ON f.project_id = p.id
        WHERE p.project_type IN ('QDA_PROJECT', 'QD_PROJECT')
    """)
    files = cur.fetchall()

    classified = 0
    for fid, file_name, file_type, title, desc in files:
        ext = f".{(file_type or '').lower().lstrip('.')}"
        if ext not in QDA_EXTS and ext not in PRIMARY_EXTS:
            continue
        doc = f"{title or ''} {desc or ''} {file_name or ''}".strip()
        primary, _ = _top2_labels(doc, vectorizer, tfidf_matrix, labels)
        if primary:
            conn.execute("UPDATE FILES SET class = ? WHERE id = ?", (primary, fid))
            classified += 1
    conn.commit()
    logger.info(f"Classified {classified} primary/QDA files")


def main():
    if not os.path.exists(DATABASE_NAME):
        logger.error(f"{DATABASE_NAME} not found — run populate_from_disk.py first")
        return
    if not os.path.exists(ISIC_FILE):
        logger.error(f"{ISIC_FILE} not found — needed to build the ISIC taxonomy")
        return

    conn = setup_database()
    assign_project_types(conn)

    vectorizer, tfidf_matrix, labels = train_classifier()
    classify_projects(conn, vectorizer, tfidf_matrix, labels)
    classify_files(conn, vectorizer, tfidf_matrix, labels)

    conn.close()
    logger.info(f"Classification complete -> {CLASSIFICATION_DB}")


if __name__ == "__main__":
    main()
