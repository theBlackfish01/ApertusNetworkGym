"""Render the technical report to HTML with a print stylesheet, and to PDF through a headless browser.

    uv run python src/report_pdf.py                       # docs/technical_report.html
    uv run python src/report_pdf.py --pdf docs/Team_Report.pdf --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"

The PDF step calls Chrome or Edge in headless mode (``--print-to-pdf``), the only PDF engine that
is on every judge's machine; the page count is read back with pypdf when it is installed. The
stylesheet is sized for the six-page limit of the hackathon (without references): A4, 14 mm
margins, 9 pt text. Images are held to the text width: a wider one made Chrome shrink every page
to fit it, which until 15 October cut off the right half of each figure.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
CSS = """
@page { size: A4; margin: 14mm 14mm 13mm 14mm; }
html { font-size: 9pt; }
body { font-family: "Source Serif 4", Georgia, "Times New Roman", serif; line-height: 1.32; color: #111; max-width: 182mm; margin: 0 auto; }
h1 { font-size: 16pt; margin: 0 0 4pt; line-height: 1.2; }
h2 { font-size: 11.8pt; margin: 10pt 0 3pt; border-bottom: 0.5pt solid #999; padding-bottom: 1pt; }
h3 { font-size: 10.6pt; margin: 7pt 0 2pt; }
p { margin: 0 0 5pt; text-align: justify; hyphens: auto; }
ul, ol { margin: 0 0 5pt 16pt; padding: 0; }
li { margin: 0 0 1.5pt; }
blockquote { margin: 0 0 6pt; padding: 3pt 8pt; border-left: 2pt solid #bbb; color: #333; font-size: 9.4pt; }
code { font-family: "JetBrains Mono", Consolas, "Courier New", monospace; font-size: 8pt; }
p code, li code, td code { overflow-wrap: anywhere; }
pre { font-size: 6.2pt; line-height: 1.25; background: #f5f5f5; padding: 4pt 6pt; border: 0.5pt solid #ddd; overflow: hidden; white-space: pre; margin: 0 0 6pt; }
table { border-collapse: collapse; margin: 3pt 0 7pt; font-size: 8.8pt; width: 100%; }
th, td { border-bottom: 0.5pt solid #bbb; padding: 1.5pt 4pt; text-align: left; vertical-align: top; }
th { border-bottom: 1pt solid #444; font-weight: 600; }
tr, h2, h3 { page-break-inside: avoid; }
h2, h3 { page-break-after: avoid; }
a { color: #0b3d91; text-decoration: none; }
img { display: block; max-width: 100%; height: auto; margin: 2pt auto 3pt; page-break-inside: avoid; }
.meta { font-size: 9.4pt; color: #333; }
"""


def render_html(source: Path, out: Path) -> Path:
    text = source.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = body.replace('src="docs/', 'src="')  # the page lives in docs/, next to the figures
    title = re.search(r"^# (.+)$", text, re.MULTILINE)
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{title.group(1) if title else source.stem}</title><style>{CSS}</style></head>"
        f"<body>{body}</body></html>"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8", newline="\n")
    return out


def render_pdf(html: Path, pdf: Path, browser: str) -> Path:
    pdf.parent.mkdir(parents=True, exist_ok=True)
    command = [
        browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf.resolve()}", html.resolve().as_uri(),
    ]  # fmt: skip
    subprocess.run(command, check=True, capture_output=True, timeout=120)
    return pdf


def page_count(pdf: Path) -> int | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    return len(PdfReader(str(pdf)).pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=ROOT / "technical_report.md")
    parser.add_argument("--html", type=Path, default=ROOT / "docs" / "technical_report.html")
    parser.add_argument("--pdf", type=Path, default=None, help="write a PDF here (needs --browser)")
    parser.add_argument("--browser", default=None, help="path of a Chrome or Edge executable")
    args = parser.parse_args()
    html = render_html(args.source, args.html)
    print(f"wrote {html}")
    if args.pdf:
        if not args.browser:
            raise SystemExit("--pdf needs --browser (a Chrome or Edge executable)")
        pdf = render_pdf(html, args.pdf, args.browser)
        pages = page_count(pdf)
        print(f"wrote {pdf}" + (f" ({pages} pages)" if pages else ""))


if __name__ == "__main__":
    main()
