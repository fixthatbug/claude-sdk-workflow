"""
Session JSONL Parser - Extract text content from Claude session files.
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"
@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None
@dataclass
class SessionTranscript:
    session_id: str
    messages: List[SessionMessage] = field(default_factory=list)
    cwd: Optional[str] = None
    def to_text(self, include_roles: bool = True) -> str:
        lines = []
        for msg in self.messages:
            if include_roles:
                lines.append(f"[{msg.role.upper()}]")
            lines.append(msg.content)
            lines.append("")
        return chr(10).join(lines)
def extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return chr(10).join(texts)
    return str(content)
def parse_session_file(file_path: Path) -> SessionTranscript:
    transcript = SessionTranscript(session_id=file_path.stem)
    seen = set()
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
            except:
                continue
            if "sessionId" in data:
                transcript.session_id = data["sessionId"]
            if "cwd" in data and not transcript.cwd:
                transcript.cwd = data["cwd"]
            if data.get("type") == "queue-operation":
                continue
            msg_data = data.get("message", {})
            role = msg_data.get("role")
            if role not in ("user", "assistant"):
                continue
            content = extract_text_from_content(msg_data.get("content", ""))
            if not content.strip():
                continue
            h = hash(content[:500])
            if h in seen:
                continue
            seen.add(h)
            transcript.messages.append(SessionMessage(role=role, content=content, model=msg_data.get("model"), session_id=transcript.session_id))
    return transcript
def find_session_files(project_dir=None, limit=10):
    base = project_dir or DEFAULT_PROJECTS_DIR
    if not base.exists():
        return []
    files = list(base.rglob("*.jsonl"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]
def list_recent_sessions(project_dir=None, limit=10):
    return [{"session_id": parse_session_file(f).session_id, "file": str(f), "messages": len(parse_session_file(f).messages)} for f in find_session_files(project_dir, limit)]
