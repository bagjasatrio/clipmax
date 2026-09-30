import os
import json
import time
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

from clipmax.pipeline import ClipResult

PROJECTS_DIR = Path("./projects").resolve()
PROJECTS_FILE = PROJECTS_DIR / "projects.json"

class ProjectRecord(BaseModel):
    project_id: str
    title: str
    created_at: str
    timestamp: float
    input_source: str
    clip_mode: str
    clip_count: int
    clips: List[Dict[str, Any]]
    cover_thumbnail: str = ""

def ensure_projects_dir() -> Path:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if not PROJECTS_FILE.exists():
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    return PROJECTS_DIR

def list_projects() -> List[Dict[str, Any]]:
    ensure_projects_dir()
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            data.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return data
    except Exception as e:
        print(f"[ProjectManager Error] Failed to read projects.json: {e}")
    return []

def get_last_project() -> Optional[Dict[str, Any]]:
    projects = list_projects()
    return projects[0] if projects else None

def get_project_by_id(project_id: str) -> Optional[Dict[str, Any]]:
    projects = list_projects()
    for p in projects:
        if p.get("project_id") == project_id:
            return p
    return None

def save_project(
    clips: List[ClipResult],
    input_source: str,
    clip_mode: str = "single",
    project_title: Optional[str] = None
) -> Dict[str, Any]:
    ensure_projects_dir()
    
    timestamp = time.time()
    now_dt = datetime.now()
    proj_id = f"proj_{now_dt.strftime('%Y%m%d_%H%M%S')}"
    created_str = now_dt.strftime("%d %b %Y, %H:%M")
    
    # Title resolution
    derived_title = project_title
    if not derived_title and clips:
        derived_title = clips[0].title
    if not derived_title:
        derived_title = Path(input_source).stem if os.path.exists(input_source) else "ClipMax Project"

    proj_folder = PROJECTS_DIR / proj_id
    proj_folder.mkdir(parents=True, exist_ok=True)

    persisted_clips = []
    cover_thumb = ""

    for idx, c in enumerate(clips):
        c_dict = c.model_dump()
        src_vid = Path(c.staging_path)
        if src_vid.exists():
            dest_vid = proj_folder / src_vid.name
            shutil.copy2(str(src_vid), str(dest_vid))
            c_dict["staging_path"] = str(dest_vid.resolve())

            # Also backup the clean base file if exists
            base_vid = src_vid.parent / f"{src_vid.stem}_base{src_vid.suffix}"
            if base_vid.exists():
                shutil.copy2(str(base_vid), str(proj_folder / base_vid.name))

        if c.thumbnail_path and os.path.exists(c.thumbnail_path):
            src_th = Path(c.thumbnail_path)
            dest_th = proj_folder / src_th.name
            shutil.copy2(str(src_th), str(dest_th))
            c_dict["thumbnail_path"] = str(dest_th.resolve())
            if not cover_thumb:
                cover_thumb = f"/projects_media/{proj_id}/{dest_th.name}"

        persisted_clips.append(c_dict)

    record = ProjectRecord(
        project_id=proj_id,
        title=derived_title,
        created_at=created_str,
        timestamp=timestamp,
        input_source=input_source,
        clip_mode=clip_mode,
        clip_count=len(persisted_clips),
        clips=persisted_clips,
        cover_thumbnail=cover_thumb
    ).model_dump()

    all_projs = list_projects()
    all_projs.insert(0, record)
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_projs, f, indent=2)

    return record

def restore_project_to_staging(project_id: str, staging_dir: Path) -> Optional[List[ClipResult]]:
    record = get_project_by_id(project_id)
    if not record:
        return None

    staging_dir.mkdir(parents=True, exist_ok=True)
    restored_clips = []

    for c_data in record.get("clips", []):
        src_str = c_data.get("staging_path", "").strip()
        if src_str and os.path.isfile(src_str):
            src_path = Path(src_str)
            dest_path = staging_dir / src_path.name
            shutil.copy2(str(src_path), str(dest_path))
            c_data["staging_path"] = str(dest_path.resolve())

            # Also copy base backup if available in project folder
            proj_folder = src_path.parent
            base_path = proj_folder / f"{src_path.stem}_base{src_path.suffix}"
            if base_path.exists() and base_path.is_file():
                shutil.copy2(str(base_path), str(staging_dir / base_path.name))

        # Copy thumbnail
        th_str = c_data.get("thumbnail_path", "").strip()
        if th_str and os.path.isfile(th_str):
            th_path = Path(th_str)
            dest_th = staging_dir / th_path.name
            shutil.copy2(str(th_path), str(dest_th))
            c_data["thumbnail_path"] = str(dest_th.resolve())

        restored_clips.append(ClipResult(**c_data))

    return restored_clips

def delete_project(project_id: str) -> bool:
    ensure_projects_dir()
    projs = list_projects()
    remaining = [p for p in projs if p.get("project_id") != project_id]
    
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(remaining, f, indent=2)

    proj_folder = PROJECTS_DIR / project_id
    if proj_folder.exists():
        try:
            shutil.rmtree(proj_folder)
        except Exception as e:
            print(f"[ProjectManager Warning] Gagal hapus folder {proj_folder}: {e}")

    return True
