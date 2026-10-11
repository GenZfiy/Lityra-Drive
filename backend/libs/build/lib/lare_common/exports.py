"""Zero-dependency document generation: XLSX, PDF, and QR (stdlib only).

Production can swap in openpyxl / reportlab / qrcode for richer output, but these
pure-stdlib generators keep exports, offer letters, hall tickets, and
certificates working with no extra packages installed.
"""
from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape


# ---------------- XLSX (minimal OOXML) ----------------
def to_xlsx(headers: list[str], rows: list[list], sheet: str = "Sheet1") -> bytes:
    def cell(col: int, row: int, val) -> str:
        ref = f"{_col_letter(col)}{row}"
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return f'<c r="{ref}"><v>{val}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(val))}</t></is></c>'

    xml_rows = []
    xml_rows.append("<row r=\"1\">" + "".join(cell(i + 1, 1, h) for i, h in enumerate(headers)) + "</row>")
    for r, data in enumerate(rows, start=2):
        xml_rows.append(f'<row r="{r}">' + "".join(cell(i + 1, r, v) for i, v in enumerate(data)) + "</row>")

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(xml_rows) + "</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buf.getvalue()


def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


# ---------------- PDF (minimal, text lines) ----------------
def to_pdf(title: str, lines: list[str]) -> bytes:
    """A single-page, text-only PDF. Enough for offer letters, hall tickets and
    certificates; production can substitute reportlab for layout/logos."""
    def esc(t: str) -> str:
        return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content_lines = [f"BT /F1 18 Tf 72 760 Td ({esc(title)}) Tj ET"]
    y = 730
    for ln in lines:
        content_lines.append(f"BT /F1 11 Tf 72 {y} Td ({esc(ln)}) Tj ET")
        y -= 18
        if y < 60:
            break
    stream = "\n".join(content_lines).encode("latin-1", "replace")

    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode())
    return out.getvalue()


# ---------------- QR (optional lib, graceful) ----------------
def qr_datauri(text: str) -> str | None:
    """PNG data-URI for a QR code if the `qrcode` lib is installed, else None.
    Hall tickets embed the raw token/URL as text regardless, so scanning still
    works via any generator when the lib is present."""
    try:
        import base64
        import qrcode  # type: ignore

        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001
        return None
