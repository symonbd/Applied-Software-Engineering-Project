import os

# =========================
# Storage configuration
# =========================
BASE_DOWNLOAD_DIR = "downloads"
DATABASE_NAME = "23088045-seeding.db"

# =========================
# Networking configuration
# =========================
MAX_THREADS = 8
REQUEST_TIMEOUT = 45
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
BANNED_EXTENSIONS = [".dat", ".tar", ".bin", ".nc", ".h5", ".exe", ".dll"]

# =========================
# Search queries (Incremental High-Quality Qualitative Focus)
# =========================
SEARCH_QUERIES = [
    "interview",
    "qdpx",
    "qualitative",
    "focus group",
    "transcript",
    "ethnography",
    "maxqda",
    "nvivo",
]

# =========================
# QDA Software File Types (Ultimate List)
# =========================
QDA_EXTENSIONS = [
    # REFI-QDA standard / QDAcity (qdasoftware.org)
    ".qdpx", ".qdpxm", ".qdc",
    # MaxQDA
    ".mqda", ".mqbac", ".mqtc", ".mqex", ".mqmtr",
    ".mx24", ".mx24bac", ".mc24", ".mex24",
    ".mx22", ".mex22", ".mx20", ".mx18", ".mx12", ".mx11",
    ".mx5", ".mx4", ".mx3", ".mx2", ".m2k", ".mxd",
    ".loa", ".sea", ".mtr", ".mod",
    # NVivo
    ".nvpx", ".nvp", ".nvpb",
    # ATLAS.ti -- verified extension is .atlasproj (not .atlproj, a past typo here)
    ".atlasproj", ".atlproj", ".atlproj22", ".hpr8", ".hpr7", ".hpr6", ".atlcb",
    # QDA Miner
    ".ppj", ".pprj", ".qlt",
    # Quirkos -- verified extension is .qpd (letters were transposed to .qdp here)
    ".qpd", ".qdp",
    # f4analyse -- verified extension is .f4p (was .f4a here)
    ".f4p", ".f4a",
    ".hs2", ".tra", ".rqda", ".qrk"
]

# =========================
# Primary Research Data (Text, Media, Archives, Images)
# =========================
PRIMARY_EXTENSIONS = [
    ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".pages",
    ".xlsx", ".xls", ".csv", ".tsv", ".ods", ".xml", ".json",
    ".html", ".htm",
    ".mp3", ".wav", ".m4a", ".wma", ".flac", ".aac",
    ".mp4", ".avi", ".mov", ".mkv", ".wmv",
    ".jpg", ".jpeg", ".png", ".tiff", ".bmp",
    ".zip", ".tar", ".gz", ".7z", ".rar"
]

# =========================
# Combined extensions
# =========================
ALLOWED_EXTENSIONS = list(set(QDA_EXTENSIONS + PRIMARY_EXTENSIONS))

os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)
