# populate_from_disk.py
import os
import glob
import sqlite3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

DB_NAME = "23088045-sq26.db"
SEEDING_DB = "23088045-seeding.db"
DOWNLOADS_DIR = "downloads"

REPO_MAP = {
    "finnish-social-science-data-archive": "https://www.fsd.tuni.fi",
    "sikt": "https://sikt.no"
}

# FSD Catalogue API for metadata enrichment fallback
FSD_CATALOGUE_API = "https://services.fsd.tuni.fi/catalogue/study/{project_id}?lang=en"


def parse_fsd_xml(xml_path):
    """Parse DDI XML metadata file for title, description, and keywords.
    Prefers English (xml:lang='en') when available."""
    title = ""
    description = ""
    keywords = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for elem in root.iter():
            tag_local = elem.tag.split('}')[-1]
            lang = elem.attrib.get('{http://www.w3.org/XML/1998/namespace}lang', '')
            
            # Prefer English titles and abstracts
            if tag_local == "titl":
                txt = (elem.text or "").strip()
                if txt:
                    if lang == "en":
                        title = txt
                    elif not title:
                        title = txt
            elif tag_local == "abstract":
                # Collect all paragraph text within abstract elements
                txt = (elem.text or "").strip()
                # Also get text from child <p> elements
                child_texts = []
                for child in elem:
                    child_tag = child.tag.split('}')[-1]
                    if child_tag == "p" and child.text:
                        child_texts.append(child.text.strip())
                combined = txt
                if child_texts:
                    combined = (txt + " " + " ".join(child_texts)).strip()
                if combined:
                    if lang == "en":
                        description = combined
                    elif not description:
                        description = combined
            elif tag_local == "keyword":
                txt = (elem.text or "").strip()
                if txt:
                    if lang == "en" or not lang:
                        # Split on commas and semicolons
                        for part in txt.replace(';', ',').split(','):
                            clean_part = part.strip()
                            if clean_part:
                                keywords.append(clean_part)
    except Exception as e:
        print(f"Error parsing XML {xml_path}: {e}")
    return title, description, keywords


def fetch_fsd_api_metadata(project_id):
    """Fallback: fetch title and description from FSD catalogue REST API."""
    title = ""
    description = ""
    try:
        url = FSD_CATALOGUE_API.format(project_id=project_id)
        r = requests.get(url, timeout=15, headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })
        if r.status_code == 200:
            data = r.json()
            # Try common JSON response structures
            title = data.get("title", data.get("name", ""))
            description = data.get("description", data.get("abstract", ""))
            # If nested in a 'study' or 'data' key
            if not title and "study" in data:
                study = data["study"]
                title = study.get("title", "")
                description = study.get("description", study.get("abstract", ""))
            if not title and "data" in data:
                d = data["data"]
                title = d.get("title", "")
                description = d.get("description", d.get("abstract", ""))
            if title:
                print(f"  API enrichment for {project_id}: '{title[:60]}...'")
    except Exception as e:
        print(f"  API fallback failed for {project_id}: {e}")
    return title, description


def sync_files_for_project(cursor, project_id, project_path):
    """Insert any file on disk not yet recorded in FILES for this project.
    Walks recursively -- extract_archives.py unpacks zips/tars into
    subdirectories, so a flat os.listdir() misses everything but each
    archive's immediate siblings. Uses the path relative to the project
    folder as file_name (e.g. "navajo/pom.xml") so files with the same
    basename in different subdirectories don't collide. Returns the number
    of newly inserted files."""
    cursor.execute("SELECT file_name FROM FILES WHERE project_id = ?", (project_id,))
    known = {row[0] for row in cursor.fetchall()}

    inserted = 0
    try:
        on_disk = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__MACOSX']
            for f in files:
                if f.startswith('.') or f.endswith('.extracted'):
                    continue
                rel = os.path.relpath(os.path.join(root, f), project_path)
                on_disk.append(rel)
    except Exception as e:
        print(f"Error listing files in {project_path}: {e}")
        return 0

    for file_name in on_disk:
        if file_name in known:
            continue
        file_type = file_name.split('.')[-1].lower() if '.' in file_name else ''
        try:
            cursor.execute("""
            INSERT INTO FILES (project_id, file_name, file_type, status)
            VALUES (?, ?, ?, ?)
            """, (project_id, file_name, file_type, "SUCCEEDED"))
            inserted += 1
        except Exception as e:
            print(f"Error inserting file {file_name} for project_id {project_id}: {e}")
    return inserted


def main():
    print(f"Populating database {DB_NAME} from disk and seeding database...")
    
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    conn.commit()

    # Get repository IDs
    repo_ids = {}
    cursor.execute("SELECT id, name FROM REPOSITORIES")
    for row in cursor.fetchall():
        repo_ids[row[1]] = row[0]

    # Load seeding database project metadata if available
    seeding_projects = {}
    if os.path.exists(SEEDING_DB):
        try:
            conn_seeding = sqlite3.connect(SEEDING_DB)
            cursor_seeding = conn_seeding.cursor()
            cursor_seeding.execute("SELECT project_identifier, title, description, project_url FROM PROJECTS")
            for row in cursor_seeding.fetchall():
                # Normalize key by stripping
                key = row[0].strip() if row[0] else ""
                seeding_projects[key] = {
                    "title": row[1],
                    "description": row[2],
                    "project_url": row[3]
                }
            conn_seeding.close()
            print(f"Loaded {len(seeding_projects)} project metadata entries from {SEEDING_DB}.")
        except Exception as e:
            print(f"Warning: could not load seeding database metadata: {e}")

    inserted_repos = set()
    inserted_projects_count = 0
    inserted_files_count = 0
    enriched_count = 0

    # Walk downloads/ folder structure (repo -> project -> files)
    for repo_folder in os.listdir(DOWNLOADS_DIR):
        repo_path = os.path.join(DOWNLOADS_DIR, repo_folder)
        if not os.path.isdir(repo_path) or repo_folder.startswith('.'):
            continue

        if repo_folder not in REPO_MAP:
            continue

        repository_id = repo_ids.get(repo_folder)
        if not repository_id:
            continue

        repository_url = REPO_MAP[repo_folder]
        download_method = "API-CALL" if repo_folder in ["sikt"] else "SCRAPING"
        is_fsd = (repo_folder == "finnish-social-science-data-archive")

        print(f"Scanning project folders in {repo_folder}...")

        for project_folder in os.listdir(repo_path):
            project_path = os.path.join(repo_path, project_folder)
            if not os.path.isdir(project_path) or project_folder.startswith('.'):
                continue

            # Check for duplicate projects
            cursor.execute("""
            SELECT id FROM PROJECTS 
            WHERE download_project_folder = ? AND repository_id = ?
            """, (project_folder, repository_id))
            existing_project = cursor.fetchone()
            if existing_project:
                existing_id = existing_project[0]
                newly_synced = sync_files_for_project(cursor, existing_id, project_path)
                if newly_synced:
                    inserted_files_count += newly_synced
                    print(f"  Synced {newly_synced} new file(s) for existing project {project_folder} "
                          f"(e.g. from archive extraction)")

                # Even if project exists, try to enrich missing metadata
                if is_fsd:
                    cursor.execute("SELECT description FROM PROJECTS WHERE id = ?", (existing_id,))
                    desc_row = cursor.fetchone()
                    current_desc = desc_row[0] if desc_row else ""
                    # If description is generic/missing, try to enrich
                    if not current_desc or current_desc == f"{project_folder} qualitative research dataset":
                        enriched_title, enriched_desc = _try_enrich_fsd(
                            project_path, project_folder
                        )
                        if enriched_desc:
                            cursor.execute(
                                "UPDATE PROJECTS SET description = ? WHERE id = ?",
                                (enriched_desc, existing_id)
                            )
                            if enriched_title:
                                cursor.execute(
                                    "UPDATE PROJECTS SET title = ? WHERE id = ?",
                                    (enriched_title, existing_id)
                                )
                            enriched_count += 1
                continue

            # Find files and modification date
            files_in_project = []
            newest_mtime = None

            try:
                for f in os.listdir(project_path):
                    file_path = os.path.join(project_path, f)
                    if os.path.isfile(file_path) and not f.startswith('.'):
                        files_in_project.append(f)
                        mtime = os.path.getmtime(file_path)
                        if newest_mtime is None or mtime > newest_mtime:
                            newest_mtime = mtime
            except Exception as e:
                print(f"Error listing files in {project_path}: {e}")
                continue

            if newest_mtime is not None:
                download_date = datetime.fromtimestamp(newest_mtime).isoformat()
            else:
                download_date = datetime.now().isoformat()

            # Default values
            title = project_folder
            description = f"{project_folder} qualitative research dataset"
            project_url = f"{repository_url}/some-path/{project_folder}"
            extracted_keywords = []

            # 1. Check if we can parse metadata from XML (primarily FSD projects)
            #    Use glob to find any *_metadata.xml file in the project folder
            xml_found = False
            xml_candidates = glob.glob(os.path.join(project_path, "*_metadata.xml"))
            if not xml_candidates:
                # Also try the explicit naming pattern
                explicit_xml = os.path.join(project_path, f"{project_folder}_metadata.xml")
                if os.path.exists(explicit_xml):
                    xml_candidates = [explicit_xml]

            for xml_path in xml_candidates:
                parsed_title, parsed_desc, parsed_keywords = parse_fsd_xml(xml_path)
                if parsed_title:
                    title = parsed_title
                    xml_found = True
                if parsed_desc:
                    description = parsed_desc
                    xml_found = True
                if parsed_keywords:
                    extracted_keywords.extend(parsed_keywords)
                    xml_found = True
                if xml_found:
                    break  # Use the first XML that yields data

            # 2. FSD API fallback: if no XML or XML had no description
            if is_fsd and (not xml_found or not description or
                    description == f"{project_folder} qualitative research dataset"):
                api_title, api_desc = fetch_fsd_api_metadata(project_folder)
                if api_title and not xml_found:
                    title = api_title
                if api_desc:
                    description = api_desc
                    enriched_count += 1

            # 3. Check lookup in seeding database
            lookup_key = project_folder.strip()
            if lookup_key in seeding_projects:
                seed_data = seeding_projects[lookup_key]
                # Only overwrite if we don't have a cleaner title from XML (or if XML wasn't present)
                if not xml_found:
                    if seed_data.get("title"):
                        title = seed_data["title"]
                    if seed_data.get("description"):
                        description = seed_data["description"]
                if seed_data.get("project_url"):
                    project_url = seed_data["project_url"]

            title = title.replace('\n', '').strip()
            
            # Metadata Fixing: Filter physics/quantitative data blobs
            if any(sub in title.lower() or sub in project_folder.lower() for sub in ["fields-", ".dat", ".tar"]):
                continue
                
            if len(title) > 120:
                title = title[:117] + "..."

            # Insert into PROJECTS
            try:
                cursor.execute("""
                INSERT OR IGNORE INTO PROJECTS (
                    repository_id, repository_url, project_url, title, description,
                    download_date, download_repository_folder, download_project_folder,
                    download_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    repository_id, repository_url, project_url, title, description,
                    download_date, repo_folder, project_folder, download_method
                ))
                project_id = cursor.lastrowid
                inserted_projects_count += 1
                inserted_repos.add(repo_folder)
            except Exception as e:
                print(f"Error inserting project {project_folder}: {e}")
                continue

            # Insert keywords
            for kw in extracted_keywords:
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO KEYWORDS (project_id, keyword)
                    VALUES (?, ?)
                    """, (project_id, kw))
                except Exception as e:
                    pass

            # Insert files (also covers any already extracted from an archive)
            inserted_files_count += sync_files_for_project(cursor, project_id, project_path)

    conn.commit()
    conn.close()

    print("\nPopulation Summary:")
    print(f"  Repositories populated: {len(inserted_repos)}")
    print(f"  Projects inserted:      {inserted_projects_count}")
    print(f"  Files inserted:         {inserted_files_count}")
    print(f"  Metadata enriched:      {enriched_count}")


def _try_enrich_fsd(project_path, project_folder):
    """Try to enrich FSD metadata via XML or API for an existing project."""
    title = ""
    description = ""

    # Try XML first
    xml_candidates = glob.glob(os.path.join(project_path, "*_metadata.xml"))
    if not xml_candidates:
        explicit_xml = os.path.join(project_path, f"{project_folder}_metadata.xml")
        if os.path.exists(explicit_xml):
            xml_candidates = [explicit_xml]

    for xml_path in xml_candidates:
        parsed_title, parsed_desc, _ = parse_fsd_xml(xml_path)
        if parsed_title:
            title = parsed_title
        if parsed_desc:
            description = parsed_desc
            return title, description

    # Fallback to API
    api_title, api_desc = fetch_fsd_api_metadata(project_folder)
    if api_title:
        title = api_title
    if api_desc:
        description = api_desc

    return title, description


if __name__ == "__main__":
    main()
