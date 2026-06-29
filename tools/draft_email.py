"""draft_email — produce a clean, reviewable email draft (subject + body), no send.

Robin could *send* email (send_message) but had no way to *draft* one as a reviewable
deliverable. This tool formats a draft (markdown body flattened to clean text),
optionally saves it to a .eml/.txt artifact, and returns it for the user to review.
Sending stays an explicit, separate step (send_message) so an email is never sent by
accident.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_EMPHASIS = None


def _flatten_markdown(text: str) -> str:
    """Flatten light markdown to clean email body text (keep list structure)."""
    import re

    out_lines = []
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        line = re.sub(r"^#{1,6}\s+", "", line)               # headings → plain
        line = re.sub(r"\[([^\]]+)\]\(([^)]*)\)", r"\1 (\2)", line)  # links → text (url)
        line = re.sub(r"[*_`~]{1,3}([^*_`~]+)[*_`~]{1,3}", r"\1", line)  # emphasis
        line = re.sub(r"^\s*[-*+]\s+", "• ", line)           # bullets → •
        out_lines.append(line)
    return "\n".join(out_lines).strip()


DRAFT_EMAIL_SCHEMA = {
    "name": "draft_email",
    "description": (
        "Draft a professional email (subject + body) as a reviewable deliverable — does NOT "
        "send. Provide the body as plain text or light markdown; it is flattened to clean email "
        "text. Optionally save to a .eml/.txt file. To actually send, the user must explicitly "
        "ask and you then use send_message."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Email subject line."},
            "body": {"type": "string", "description": "Email body (plain text or light markdown)."},
            "to": {"type": "string", "description": "Optional recipient(s)."},
            "cc": {"type": "string", "description": "Optional cc."},
            "out_path": {"type": "string", "description": "Optional path to save the draft (.eml or .txt)."},
        },
        "required": ["subject", "body"],
    },
}


def _render_draft(subject: str, body: str, to: str = "", cc: str = "") -> str:
    head = []
    if to:
        head.append(f"To: {to}")
    if cc:
        head.append(f"Cc: {cc}")
    head.append(f"Subject: {subject}")
    return "\n".join(head) + "\n\n" + _flatten_markdown(body) + "\n"


async def _draft_email_handler(args: dict, **_kw) -> str:
    subject = str(args.get("subject") or "").strip()
    body = str(args.get("body") or "")
    to = str(args.get("to") or "").strip()
    cc = str(args.get("cc") or "").strip()
    if not subject or not body.strip():
        return json.dumps({"error": "subject and body are required"})
    draft = _render_draft(subject, body, to, cc)
    out = {"subject": subject, "to": to, "cc": cc, "draft": draft, "sent": False}
    out_path = str(args.get("out_path") or "").strip()
    if out_path:
        try:
            p = Path(os.path.expanduser(out_path))
            p.write_text(draft, encoding="utf-8")
            out["path"] = str(p)
        except Exception as e:  # noqa: BLE001
            out["save_error"] = str(e)
    return json.dumps(out)


# Top-level registration so discover_builtin_tools() picks this up (see office_docx).
from tools.registry import registry  # noqa: E402

registry.register(
    name="draft_email",
    toolset="office",
    schema=DRAFT_EMAIL_SCHEMA,
    handler=_draft_email_handler,
    check_fn=lambda: True,
    emoji="✉️",
)
