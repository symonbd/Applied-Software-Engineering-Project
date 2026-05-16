import os

# =========================
# Storage configuration
# =========================
BASE_DOWNLOAD_DIR = "downloads"
DATABASE_NAME = "23088045-seeding.db"

# =========================
# Networking configuration
# =========================
MAX_THREADS = 10
REQUEST_TIMEOUT = 45

# =========================
# Search queries (Hyper-Expanded & Multi-Disciplinary)
# =========================
SEARCH_QUERIES = [
    # Broad Methodologies
    "qualitative interview", "qualitative research", "ethnography",
    "focus group","international data" "field study", "participant observation",
    "grounded theory", "narrative inquiry", "phenomenology",
    "case study", "action research", "heuristic inquiry",
    "phenomenography", "autoethnography", "meta-ethnography",
    "mixed methods qualitative", "longitudinal qualitative",

    # Specific Data Types & Artifacts
    "interview transcript", "focus group transcript", "field notes",
    "observation notes", "diary study", "open-ended survey",
    "anthropology field notes", "life history interview", "oral history",
    "semi-structured interview", "unstructured interview", "in-depth interview",
    "analytical memo", "coding tree", "codebook", "research diary",
    "qualitative dataset", "qualitative study", "qdainterview",

    # Analysis & Coding Terms (How researchers describe their data)
    "qualitative coding", "thematic analysis", "discourse analysis",
    "content analysis", "codebook qualitative", "coded transcripts",
    "inductive coding", "deductive coding", "axial coding", "open coding",
    "selective coding", "thematic network", "interpretative phenomenological analysis",
    "constant comparative method",

    # Tool-Specific Bait (Guarantees software file hits)
    "MAXQDA dataset", "MAXQDA project", "MAXQDA teamcloud", "MAXQDA exchange",
    "NVivo research data", "NVivo project", "NVivo export",
    "ATLAS.ti project", "ATLAS.ti bundle", "ATLAS.ti codebook",
    "QDA Miner project", "REFI-QDA export", "REFI-QDA standard",
    "Dedoose export", "HyperRESEARCH study", "Transana database",
    "RQDA project", "Quirkos project", "f4analyse data"
]

# =========================
# QDA Software File Types (Ultimate List)
# =========================
QDA_EXTENSIONS = [
    # Universal / REFI-QDA Standards
    ".qdpx", ".qdpxm", ".qdc",

    # MAXQDA (Current, Legacy, Backup, TeamCloud, Exchange)
    ".mqda", ".mqbac", ".mqtc", ".mqex", ".mqmtr",
    ".mx24", ".mx24bac", ".mc24", ".mex24",
    ".mx22", ".mex22", ".mx20", ".mx18", ".mx12", ".mx11",
    ".mx5", ".mx4", ".mx3", ".mx2", ".m2k", ".mxd",
    ".loa", ".sea", ".mtr", ".mod",

    # NVivo (PC & Mac)
    ".nvpx", ".nvp", ".nvpb", ".qdp",

    # ATLAS.ti (Projects and Codebooks)
    ".atlproj", ".atlproj22", ".hpr8", ".hpr7", ".hpr6", ".atlcb",

    # Other QDA Tools (QDA Miner, HyperRESEARCH, Transana, RQDA, Quirkos, f4analyse)
    ".ppj", ".hs2", ".tra", ".rqda", ".qrk", ".f4a"
]

# =========================
# Primary Research Data (Text, Media, Archives, Images)
# =========================
PRIMARY_EXTENSIONS = [
    # Documents & Text
    ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".pages",

    # Spreadsheets & Structured Data
    ".xlsx", ".xls", ".csv", ".tsv", ".ods", ".xml", ".json",

    # Web Data
    ".html", ".htm",

    # Audio (Interview recordings)
    ".mp3", ".wav", ".m4a", ".wma", ".flac", ".aac",

    # Video (Focus groups, observational video)
    ".mp4", ".avi", ".mov", ".mkv", ".wmv",

    # Images (Photovoice, visual sociology, artifact analysis)
    ".jpg", ".jpeg", ".png", ".tiff", ".bmp",

    # Archives (How researchers often package whole datasets)
    ".zip", ".tar", ".gz", ".7z", ".rar"
]

# =========================
# Combined extensions
# =========================
# Use a set to automatically remove any accidental duplicates
ALLOWED_EXTENSIONS = list(set(QDA_EXTENSIONS + PRIMARY_EXTENSIONS))

# Ensure the download directory exists immediately upon load
os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)
