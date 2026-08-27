"""Markdown -> HTML -> PDF conversion (FR-012, research.md §9): renders the
report's *current on-disk* Markdown content to PDF, independent of and
without re-running the pairing computation -- never touches season data,
never rewrites the `.md` file."""

from __future__ import annotations

from pathlib import Path

import markdown
from xhtml2pdf import pisa


def render_pdf(md_path: Path, pdf_path: Path) -> None:
    html = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["extra"])
    with pdf_path.open("wb") as pdf_file:
        # `path=str(md_path)` anchors relative image src paths to the .md
        # file's own directory (xhtml2pdf.context.pisaContext.pathDirectory).
        pisa.CreatePDF(html, dest=pdf_file, path=str(md_path))
