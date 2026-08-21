#!/usr/bin/env python3
"""Regenerate committed PDF test fixtures.

Runtime parsing uses pypdf, not PyMuPDF. PyMuPDF is only needed to *create*
these tiny fixtures. Tests read the committed binaries.
"""

from __future__ import annotations

from pathlib import Path

try:
    import pymupdf
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyMuPDF is required to regenerate PDF fixtures: pip install pymupdf"
    ) from exc

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pdf"


def make_multipage(path: Path) -> None:
    doc = pymupdf.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((72, 72), "Page one title", fontsize=18)
    p1.insert_text((72, 110), "This is a normal paragraph on page one.", fontsize=12)
    p1.insert_text(
        (72, 130), "It contains a second line of prose for extraction.", fontsize=12
    )
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((72, 72), "Page two title", fontsize=18)
    p2.insert_text((72, 110), "Beta paragraph lives on page two.", fontsize=12)
    p3 = doc.new_page(width=612, height=792)
    p3.insert_text((72, 72), "Page three title", fontsize=18)
    p3.insert_text((72, 110), "Gamma concludes the fixture.", fontsize=12)
    doc.save(path)
    doc.close()


def make_unicode(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Built-in fonts cover Latin-1; CJK is omitted on purpose.
    page.insert_text((72, 72), "Unicode: café naïve — résumé", fontsize=14)
    doc.save(path)
    doc.close()


def make_empty_middle(path: Path) -> None:
    doc = pymupdf.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((72, 72), "Text before empty page.", fontsize=12)
    doc.new_page(width=612, height=792)
    p3 = doc.new_page(width=612, height=792)
    p3.insert_text((72, 72), "Text after empty page.", fontsize=12)
    doc.save(path)
    doc.close()


def make_image_only(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), 0)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 200, 200), pixmap=pix)
    doc.save(path)
    doc.close()


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    make_multipage(ROOT / "multi_page.pdf")
    make_unicode(ROOT / "unicode.pdf")
    make_empty_middle(ROOT / "empty_middle.pdf")
    make_image_only(ROOT / "image_only.pdf")
    print(f"Wrote PDF fixtures in {ROOT}")


if __name__ == "__main__":
    main()
