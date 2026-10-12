import os
import shutil
from pathlib import Path
from clipmax.pipeline import ClipResult
import clipmax.project_manager as pm

def test_project_manager_lifecycle(tmp_path, monkeypatch):
    # Point projects dir to tmp_path
    monkeypatch.setattr(pm, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(pm, "PROJECTS_FILE", tmp_path / "projects" / "projects.json")

    # Initial list is empty
    projs = pm.list_projects()
    assert projs == []
    assert pm.get_last_project() is None

    # Create dummy video & thumb
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    vid1 = source_dir / "clipmax_1_100.mp4"
    vid1.write_text("dummy video content")
    thumb1 = source_dir / "thumb_1_100.jpg"
    thumb1.write_text("dummy thumb content")
    srt1 = source_dir / "clipmax_1_100.srt"
    srt1.write_text("1\n00:00:00,000 --> 00:00:02,000\nHELLO TEST\n")

    clips = [
        ClipResult(
            clip_id=1,
            title="Cara Sukses Coding",
            hook="Trik rahasia",
            virality_score=95,
            reasoning="Keren",
            start_time=10.0,
            end_time=35.0,
            staging_path=str(vid1),
            thumbnail_path=str(thumb1),
            srt_path=str(srt1),
            social_caption="Caption #coding",
            hook_timestamp=12.5
        )
    ]

    saved = pm.save_project(
        clips=clips,
        input_source="https://youtube.com/watch?v=123",
        clip_mode="single",
        project_title="Proyek Testing"
    )

    assert saved["title"] == "Proyek Testing"
    assert saved["clip_count"] == 1
    assert Path(saved["clips"][0]["staging_path"]).exists()

    # Verify list_projects and get_last_project
    projs = pm.list_projects()
    assert len(projs) == 1
    last = pm.get_last_project()
    assert last is not None
    assert last["project_id"] == saved["project_id"]

    # Verify restore to staging
    staging_target = tmp_path / "target_staging"
    restored = pm.restore_project_to_staging(saved["project_id"], staging_target)
    assert restored is not None
    assert len(restored) == 1
    assert restored[0].title == "Cara Sukses Coding"
    assert restored[0].social_caption == "Caption #coding"
    assert restored[0].hook_timestamp == 12.5
    assert Path(restored[0].staging_path).exists()
    assert Path(restored[0].staging_path).read_text() == "dummy video content"
    assert Path(restored[0].srt_path).exists()
    assert "HELLO TEST" in Path(restored[0].srt_path).read_text()

    # Verify delete
    ok = pm.delete_project(saved["project_id"])
    assert ok is True
    assert len(pm.list_projects()) == 0
    assert pm.get_last_project() is None
