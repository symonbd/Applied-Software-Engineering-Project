"""Extracts zip/tar archives already on disk in-place, so the files
bundled inside them (primary data, and QDA files if any exist) become
individually visible to populate_from_disk.py / classifier.py instead of
being hidden behind one opaque .zip/.tar entry.

Idempotent: skips an archive if it's already been extracted (marked by a
sibling ".extracted" marker file), so re-running is safe and cheap.
"""
import os
import tarfile
import zipfile
from pathlib import Path

from config import BASE_DOWNLOAD_DIR, MAX_FILE_SIZE_BYTES
from logger import logger

# Zip bombs are the obvious risk of blind extraction -- cap total
# extracted size per archive well above any single real primary-data
# bundle, but far below anything that could exhaust disk space.
MAX_EXTRACTED_BYTES = 20 * MAX_FILE_SIZE_BYTES
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".tar.gz", ".tgz"}


def _archive_kind(path: Path):
    name = path.name.lower()
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".tar.gz") or name.endswith(".tgz") or name.endswith(".tar"):
        return "tar"
    return None


def _safe_members_zip(zf: zipfile.ZipFile, dest: Path):
    total = 0
    members = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        target = (dest / info.filename).resolve()
        if not str(target).startswith(str(dest.resolve())):
            logger.warning(f"  Skipping path-traversal entry: {info.filename}")
            continue
        total += info.file_size
        if total > MAX_EXTRACTED_BYTES:
            logger.warning(f"  Aborting extraction: exceeds {MAX_EXTRACTED_BYTES/1e6:.0f}MB cap")
            return None
        members.append(info)
    return members


def _safe_members_tar(tf: tarfile.TarFile, dest: Path):
    total = 0
    members = []
    for info in tf.getmembers():
        if not info.isfile():
            continue
        target = (dest / info.name).resolve()
        if not str(target).startswith(str(dest.resolve())):
            logger.warning(f"  Skipping path-traversal entry: {info.name}")
            continue
        total += info.size
        if total > MAX_EXTRACTED_BYTES:
            logger.warning(f"  Aborting extraction: exceeds {MAX_EXTRACTED_BYTES/1e6:.0f}MB cap")
            return None
        members.append(info)
    return members


def extract_one(archive_path: Path):
    dest = archive_path.parent
    marker = dest / f".{archive_path.name}.extracted"
    if marker.exists():
        return 0

    kind = _archive_kind(archive_path)
    if kind is None:
        return 0

    try:
        if kind == "zip":
            with zipfile.ZipFile(archive_path) as zf:
                members = _safe_members_zip(zf, dest)
                if members is None:
                    return 0
                zf.extractall(dest, members=members)
                count = len(members)
        else:
            with tarfile.open(archive_path) as tf:
                members = _safe_members_tar(tf, dest)
                if members is None:
                    return 0
                tf.extractall(dest, members=members)
                count = len(members)
    except Exception as e:
        logger.warning(f"  Failed to extract {archive_path}: {e}")
        return 0

    marker.touch()
    logger.info(f"  Extracted {count} file(s) from {archive_path.relative_to(BASE_DOWNLOAD_DIR)}")
    return count


def main():
    total_archives = 0
    total_files = 0
    for root, dirs, files in os.walk(BASE_DOWNLOAD_DIR):
        for fname in files:
            path = Path(root) / fname
            if _archive_kind(path) is None:
                continue
            total_archives += 1
            total_files += extract_one(path)

    logger.info(f"Archive extraction complete: {total_archives} archive(s) seen, {total_files} file(s) extracted")


if __name__ == "__main__":
    main()
