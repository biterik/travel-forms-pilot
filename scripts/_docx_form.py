"""Self-contained DOCX form-filler for MPIE travel forms.

No external dependencies beyond Python stdlib + optional LibreOffice (soffice) for PDF.

The class works directly on the DOCX zip — it never invokes Word. It edits
`word/document.xml` to:
  * fill FORMTEXT fields (indexed by their order of appearance)
  * toggle ☐ → ☒ checkboxes (indexed in the same order)
  * optionally trim the 7-page Antrag template down to "application + A1"
    or "inland single page"

PDF conversion is delegated to LibreOffice / soffice. If soffice is missing
the DOCX is still produced and the caller is told to convert manually.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

# Matchers operate on raw UTF-8 bytes so we don't have to decode the whole XML.
FORMTEXT_BEGIN = re.compile(rb'<w:fldChar w:fldCharType="begin">.*?</w:fldChar>', re.DOTALL)
FORMTEXT_END = re.compile(rb'<w:fldChar w:fldCharType="end"/>')
RUN_T_RE = re.compile(rb'<w:t(\s[^>]*)?>([^<]*)</w:t>')
PAGE_BREAK = rb'<w:br w:type="page"/>'
SECTPR_OPEN = rb'<w:sectPr'

CHECKBOX_EMPTY = '☐'.encode('utf-8')   # ☐
CHECKBOX_FULL = '☒'.encode('utf-8')    # ☒
CHECKBOX_EMPTY_TAG = b'<w:t>' + CHECKBOX_EMPTY + b'</w:t>'
CHECKBOX_FULL_TAG = b'<w:t>' + CHECKBOX_FULL + b'</w:t>'


def _esc(s: str) -> bytes:
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')).encode('utf-8')


def _find_soffice() -> str | None:
    """Return a working soffice executable path, or None if not found."""
    candidates = [
        'soffice',
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
        '/usr/bin/soffice',
        '/usr/local/bin/soffice',
        '/opt/homebrew/bin/soffice',
    ]
    for cmd in candidates:
        try:
            r = subprocess.run([cmd, '--version'], capture_output=True, timeout=10)
            if r.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


class DocxForm:
    """In-memory editor for a single MPIE travel-form DOCX."""

    def __init__(self, template_path: str | Path):
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(self.template_path)
        self._tmpdir = Path(tempfile.mkdtemp(prefix='travelfp_'))
        self._unpacked = self._tmpdir / 'unpacked'
        self._unpacked.mkdir()
        with zipfile.ZipFile(self.template_path) as z:
            z.extractall(self._unpacked)
        self._doc_path = self._unpacked / 'word' / 'document.xml'
        self.content: bytes = self._doc_path.read_bytes()

    # ------------------------------------------------------------------ fields

    def fill_fields(self, values: dict) -> None:
        """Fill FORMTEXT fields by 0-based index. None or '' = leave empty."""
        begins = list(FORMTEXT_BEGIN.finditer(self.content))
        ends = [m.start() for m in FORMTEXT_END.finditer(self.content)]
        end_tag_len = len(b'<w:fldChar w:fldCharType="end"/>')
        if len(begins) != len(ends):
            raise RuntimeError(
                f"FORMTEXT begin/end mismatch: {len(begins)} vs {len(ends)}"
            )
        spans = [(b.start(), ends[i] + end_tag_len) for i, b in enumerate(begins)]
        # Work back-to-front so byte offsets remain valid.
        for idx in range(len(spans) - 1, -1, -1):
            val = values.get(idx)
            if val is None or val == '':
                continue
            s, e = spans[idx]
            span = self.content[s:e]
            m = RUN_T_RE.search(span)
            if not m:
                continue
            attrs = m.group(1) or b''
            if b'xml:space="preserve"' not in attrs:
                attrs = attrs + b' xml:space="preserve"'
            new_t = b'<w:t' + attrs + b'>' + _esc(str(val)) + b'</w:t>'
            new_span = span[:m.start()] + new_t + span[m.end():]
            self.content = self.content[:s] + new_span + self.content[e:]

    # -------------------------------------------------------------- checkboxes

    def toggle_checkboxes(self, to_check) -> None:
        """Toggle ☐ → ☒ at the given 0-based indices (iterable of ints)."""
        to_check = set(int(c) for c in to_check)
        out = bytearray()
        pos = 0
        cidx = 0
        while True:
            i = self.content.find(CHECKBOX_EMPTY_TAG, pos)
            if i < 0:
                out.extend(self.content[pos:])
                break
            out.extend(self.content[pos:i])
            out.extend(CHECKBOX_FULL_TAG if cidx in to_check else CHECKBOX_EMPTY_TAG)
            pos = i + len(CHECKBOX_EMPTY_TAG)
            cidx += 1
        self.content = bytes(out)

    # -------------------------------------------------------- counts / helpers

    def field_count(self) -> int:
        return sum(1 for _ in FORMTEXT_BEGIN.finditer(self.content))

    def checkbox_count(self) -> int:
        # count both currently-empty and currently-checked boxes
        return (self.content.count(CHECKBOX_EMPTY_TAG)
                + self.content.count(CHECKBOX_FULL_TAG))

    # ------------------------------------------------------------ trim recipes

    def trim_application_with_a1(self) -> None:
        """Trim the 7-page Antrag template to "application + A1" (2 pages).

        Recipe per docs/formular_mechanik.md:
          1. Drop everything from <w:body> start through the first page break paragraph.
          2. Replace the "Kostenauslösung …" disclaimer paragraph with a minimal
             paragraph that only carries the page break to the A1 page.
          3. Drop everything from the "Liste der EU-Länder …" paragraph through
             the closing </w:body>, but keep the trailing <w:sectPr>.
          4. Drop empty trailing paragraphs immediately before <w:sectPr>.
        """
        body_open = self.content.find(b'<w:body>')
        if body_open < 0:
            raise RuntimeError("No <w:body> tag found.")
        body_inner_start = body_open + len(b'<w:body>')

        # 1. Drop through the first page-break paragraph (index page).
        first_break = self.content.find(PAGE_BREAK, body_inner_start)
        if first_break >= 0:
            para_end = self.content.find(b'</w:p>', first_break)
            if para_end >= 0:
                cut_end = para_end + len(b'</w:p>')
                self.content = (self.content[:body_inner_start]
                                + self.content[cut_end:])

        # 2. Replace the "Kostenauslösung" disclaimer paragraph with a minimal
        #    paragraph that just carries a page break.
        marker = 'Kostenauslösung'.encode('utf-8')
        m = self.content.find(marker)
        if m >= 0:
            para_start = self.content.rfind(b'<w:p ', 0, m)
            if para_start < 0:
                para_start = self.content.rfind(b'<w:p>', 0, m)
            para_end = self.content.find(b'</w:p>', m)
            if para_start >= 0 and para_end >= 0:
                replacement = (b'<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
                self.content = (self.content[:para_start]
                                + replacement
                                + self.content[para_end + len(b'</w:p>'):])

        # 3. Drop from "Liste der EU-Länder" through end of body (keep <w:sectPr>).
        marker = 'Liste der EU-Länder'.encode('utf-8')
        m = self.content.find(marker)
        if m >= 0:
            para_start = self.content.rfind(b'<w:p ', 0, m)
            if para_start < 0:
                para_start = self.content.rfind(b'<w:p>', 0, m)
            sect = self.content.find(SECTPR_OPEN, m)
            if para_start >= 0 and sect >= 0:
                self.content = self.content[:para_start] + self.content[sect:]

        self._trim_trailing_empty_paragraphs()

    def trim_inland_single_page(self) -> None:
        """Trim to "inland single page" (no A1).

        Differs from the A1 trim only in that we also drop the A1 page (everything
        from after the disclaimer through the EU country list).
        """
        body_open = self.content.find(b'<w:body>')
        if body_open < 0:
            raise RuntimeError("No <w:body> tag found.")
        body_inner_start = body_open + len(b'<w:body>')

        # 1. Drop through the first page-break paragraph (index page).
        first_break = self.content.find(PAGE_BREAK, body_inner_start)
        if first_break >= 0:
            para_end = self.content.find(b'</w:p>', first_break)
            if para_end >= 0:
                cut_end = para_end + len(b'</w:p>')
                self.content = (self.content[:body_inner_start]
                                + self.content[cut_end:])

        # 2. Drop from the "Kostenauslösung" paragraph (inclusive) through the
        #    closing of the body, keeping only <w:sectPr>.
        marker = 'Kostenauslösung'.encode('utf-8')
        m = self.content.find(marker)
        sect = self.content.find(SECTPR_OPEN, m if m >= 0 else 0)
        if m >= 0 and sect >= 0:
            para_start = self.content.rfind(b'<w:p ', 0, m)
            if para_start < 0:
                para_start = self.content.rfind(b'<w:p>', 0, m)
            if para_start >= 0:
                self.content = self.content[:para_start] + self.content[sect:]

        self._trim_trailing_empty_paragraphs()

    def _trim_trailing_empty_paragraphs(self) -> None:
        """Drop empty <w:p>…</w:p> blocks immediately before the body's <w:sectPr>.

        "Empty" = a paragraph whose only descendants are <w:pPr> formatting
        (and optionally whitespace) — i.e. no runs (<w:r>), no breaks (<w:br>),
        no field characters (<w:fldChar>).

        We work on the prefix before the LAST <w:sectPr> in the document, since
        in-paragraph section breaks would sit earlier inside a <w:pPr>.
        """
        # Use the last <w:sectPr> (the body-level one).
        last_sect = self.content.rfind(SECTPR_OPEN)
        if last_sect < 0:
            return
        # Step backwards over paragraphs and drop empties.
        while True:
            # Trim whitespace just before <w:sectPr>.
            i = last_sect
            while i > 0 and self.content[i - 1:i] in (b' ', b'\t', b'\n', b'\r'):
                i -= 1
            if i <= 0:
                break
            # The character before `i` should be '>' (closing some tag).
            if self.content[i - 1:i] != b'>':
                break
            # Find the matching </w:p> right before `i`.
            close_tag = b'</w:p>'
            if not self.content[i - len(close_tag):i] == close_tag:
                # Could also be a self-closing <w:p/>; check that too.
                if self.content[i - len(b'<w:p/>'):i] == b'<w:p/>':
                    # Self-closing empty paragraph: drop it.
                    start = i - len(b'<w:p/>')
                    self.content = (self.content[:start]
                                    + self.content[i:])
                    last_sect = self.content.rfind(SECTPR_OPEN)
                    continue
                break
            close_end = i
            close_start = i - len(close_tag)
            # Find the matching opening <w:p ...> or <w:p>.
            cand1 = self.content.rfind(b'<w:p ', 0, close_start)
            cand2 = self.content.rfind(b'<w:p>', 0, close_start)
            open_start = max(cand1, cand2)
            if open_start < 0:
                break
            # If a later </w:p> exists between open_start and close_start,
            # we've miscounted nesting — bail.
            inner = self.content[open_start:close_start]
            # `<w:p>` doesn't nest, so any earlier </w:p> means we picked the wrong opener.
            if b'</w:p>' in inner[5:]:  # skip the opening tag itself
                break
            para = self.content[open_start:close_end]
            # Empty if no run / break / fldChar / text content.
            if (b'<w:r ' in para or b'<w:r>' in para
                    or b'<w:r/>' in para
                    or b'<w:br' in para
                    or b'<w:fldChar' in para
                    or b'<w:t ' in para or b'<w:t>' in para):
                break
            # Drop the empty paragraph.
            self.content = self.content[:open_start] + self.content[close_end:]
            last_sect = self.content.rfind(SECTPR_OPEN)

    # ------------------------------------------------------------- output

    def _fix_broken_template_ref(self) -> None:
        """Strip the Windows-path attached-template ref from settings.xml.

        Otherwise repacking and downstream tools complain about a broken
        external reference (see formular_mechanik.md).
        """
        settings_xml = self._unpacked / 'word' / 'settings.xml'
        settings_rels = self._unpacked / 'word' / '_rels' / 'settings.xml.rels'
        if settings_xml.exists():
            text = settings_xml.read_text(encoding='utf-8')
            text = re.sub(r'<w:attachedTemplate[^/]*/>', '', text)
            settings_xml.write_text(text, encoding='utf-8')
        if settings_rels.exists():
            settings_rels.write_text(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>\n',
                encoding='utf-8',
            )

    def save_docx(self, out_path: str | Path) -> Path:
        """Write the modified XML and repack the DOCX."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._doc_path.write_bytes(self.content)
        self._fix_broken_template_ref()
        # Repack — preserve original order by reading from the template's manifest.
        with zipfile.ZipFile(self.template_path) as orig:
            names = orig.namelist()
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in names:
                src = self._unpacked / name
                if src.exists():
                    z.write(src, name)
        return out_path

    def to_pdf(self, docx_path: str | Path, pdf_path: str | Path) -> bool:
        """Convert DOCX to PDF via LibreOffice headless. Returns True on success."""
        docx_path = Path(docx_path)
        pdf_path = Path(pdf_path)
        out_dir = pdf_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        soffice = _find_soffice()
        if soffice is None:
            return False
        try:
            subprocess.run(
                [soffice, '--headless', '--convert-to', 'pdf',
                 '--outdir', str(out_dir), str(docx_path)],
                capture_output=True, timeout=90, check=False,
            )
        except subprocess.TimeoutExpired:
            return False
        produced = out_dir / (docx_path.stem + '.pdf')
        if produced.exists():
            if produced != pdf_path:
                produced.replace(pdf_path)
            return pdf_path.exists()
        return False

    # -------------------------------------------------------------- cleanup

    def cleanup(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()
