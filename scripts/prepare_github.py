"""Prepare an allowlisted publication package. Does not contact or modify GitHub."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
TARGET = OUTPUT / "github-ready"
FILES = [
    "README.md", ".gitignore", ".gitattributes",
    "docs/data-and-pipeline.md", "docs/illustration.md",
    "docs/research/AI_retrospective_research_v3.docx",
    "docs/assets/retrospective.png", "docs/assets/evidence.json",
    "examples/README.md",
    "examples/01_news.json", "examples/02_market.json", "examples/03_user_actions.json",
    "examples/04_calculated.json", "examples/05_pipeline_and_knowledge.json",
    "examples/build_demo.py", "scripts/prepare_github.py",
]


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for relative in FILES:
        source = ROOT / relative
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    for relative in FILES:
        if relative.endswith(".md"):
            path = TARGET / relative
            content = path.read_text(encoding="utf-8")
            assert "C:/Users/" not in content and "C:\\Users\\" not in content
            for link in re.findall(r"\]\(([^)]+)\)", content):
                if not link.startswith(("https://", "http://", "#")):
                    assert (path.parent / link.split("#")[0]).is_file(), (relative, link)
        if relative.endswith(".json"):
            json.loads((TARGET / relative).read_text(encoding="utf-8"))
    manifest = [{"path": relative, "bytes": (TARGET / relative).stat().st_size,
                 "sha256": hashlib.sha256((TARGET / relative).read_bytes()).hexdigest()}
                for relative in FILES]
    (OUTPUT / "upload-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    settings = {
        "repository": "Kurban4ik/TInvestIdea",
        "description": "ИИ-ретроспектива инвестиционных решений: результат позиции, рыночные события и проверка собственных правил инвестора.",
        "topics": ["investment-analytics", "portfolio-analysis", "explainable-ai", "llm", "behavioral-finance"],
    }
    (OUTPUT / "repository-settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive = OUTPUT / "TInvestIdea-github.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for relative in FILES:
            bundle.write(TARGET / relative, relative)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == set(FILES)
    print(f"Prepared {len(FILES)} files: {archive}")
    print("All Markdown links and JSON files validated. Original notes and temporary previews excluded.")


if __name__ == "__main__":
    main()
