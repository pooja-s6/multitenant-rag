"""Write the fictional Northwind Labs sample files, including small PDFs."""

from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 12 Tf", "72 740 Td", "16 TL"]
    for index, line in enumerate(lines):
        if index:
            commands.append("T*")
        commands.append(f"({_escape(line)}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1")


def build_pdf(pages: list[list[str]]) -> bytes:
    """Catalog is object 1, the page tree is object 2, and Helvetica is object 3."""
    font_id = 3
    objects: list[bytes] = [b""] * (3 + len(pages) * 2)
    kids: list[str] = []
    for index, lines in enumerate(pages):
        content_id = 4 + index * 2
        page_id = 5 + index * 2
        stream = _page_stream(lines)
        objects[content_id - 1] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        )
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode("latin-1")
        kids.append(f"{page_id} 0 R")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode("latin-1")
    objects[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    return _serialize(objects)


def _serialize(objects: list[bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("latin-1"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(output)


HANDBOOK_PAGES = [
    [
        "Northwind Labs Employee Handbook",
        "Northwind Labs is a fictional software company.",
        "Standard working hours are 09:00 to 17:30, Monday to Friday.",
        "Employees may work from home on up to two days each week",
        "after the probation period. Probation lasts three months.",
    ],
    [
        "Leave",
        "Employees receive 20 days of annual leave each calendar year.",
        "Sick leave is available for up to 10 days each year.",
        "Send leave requests to the manager five working days ahead.",
        "Up to five unused annual leave days may carry into next year.",
    ],
]

ENGINEERING_PAGES = [
    [
        "Northwind Labs Engineering Guide",
        "Every change requires a code review before it is merged.",
        "Do not commit secrets, API keys, or passwords.",
        "Use a feature branch and open a pull request to main.",
    ],
    [
        "Testing",
        "New behavior should include automated tests.",
        "Run the backend test suite before you ask for review.",
        "Keep functions small and name them for what they do.",
    ],
]

LEAVE_POLICY = """Northwind Labs Leave Policy

This policy applies to employees of Northwind Labs, a fictional company.

Annual leave allowance is 20 working days per calendar year.
Public holidays are separate from annual leave.
Request annual leave at least five working days in advance.
Up to five unused annual leave days may be carried into the next year.
Sick leave may be used for up to 10 working days each year.
Tell your manager on the morning you are unable to work.
"""

SECURITY_POLICY = """# Security Policy

Northwind Labs requires multi-factor authentication for every account.

Passwords must contain at least 12 characters.
Employees must not share credentials.
Lock your screen when you leave your desk.

Report a suspected incident to security@northwindlabs.example within one hour.
"""


def main() -> None:
    directory = Path(__file__).resolve().parent
    (directory / "employee_handbook.pdf").write_bytes(build_pdf(HANDBOOK_PAGES))
    (directory / "engineering_guide.pdf").write_bytes(build_pdf(ENGINEERING_PAGES))
    (directory / "leave_policy.txt").write_text(LEAVE_POLICY, encoding="utf-8")
    (directory / "security_policy.md").write_text(SECURITY_POLICY, encoding="utf-8")


if __name__ == "__main__":
    main()
