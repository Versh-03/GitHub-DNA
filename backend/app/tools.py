"""Safe, read-only tools the agent can call. Every path is confined to the cloned repo."""
import re
from pathlib import Path
from app.config import SKIP_DIRS, MAX_FILE_SIZE_KB

MAX_READ_LINES = 60
MAX_OUTPUT_CHARS = 3500
MAX_SEARCH_HITS = 15


class ToolError(Exception):
    pass


TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_outline",
        "description": "List the classes and functions (with line numbers) of one Python file. Cheap; use before read_file.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "description": "repo-relative path"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read up to 60 numbered lines of a Python file.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"},
                                      "start_line": {"type": "integer"},
                                      "end_line": {"type": "integer"}},
                       "required": ["path", "start_line", "end_line"]}}},
    {"type": "function", "function": {
        "name": "search_code",
        "description": "Regex search across the repo's Python files. Returns path:line: text.",
        "parameters": {"type": "object",
                       "properties": {"pattern": {"type": "string"}},
                       "required": ["pattern"]}}},
]


class ToolBox:
    def __init__(self, repo_dir, analysis: dict):
        self.repo_dir = Path(repo_dir).resolve()
        self.files = {f["path"]: f for f in analysis["files"]}

    def _resolve(self, rel) -> Path:
        if not isinstance(rel, str) or not rel:
            raise ToolError("path is required")
        p = (self.repo_dir / rel).resolve()
        if self.repo_dir not in p.parents:
            raise ToolError("path is outside the repository")
        if any(part in SKIP_DIRS for part in p.relative_to(self.repo_dir).parts):
            raise ToolError("directory is not allowed")
        if p.suffix != ".py" or not p.is_file():
            raise ToolError(f"not a Python file in this repo: {rel}")
        if p.stat().st_size > MAX_FILE_SIZE_KB * 1024:
            raise ToolError("file too large")
        return p

    def read_text(self, rel):
        """Used by the grounding check. Returns None if the file is not readable."""
        try:
            return self._resolve(rel).read_text(encoding="utf-8", errors="replace")
        except ToolError:
            return None

    def get_outline(self, path):
        self._resolve(path)
        info = self.files.get(path)
        if not info:
            raise ToolError("file was not part of the analysis")
        classes = ", ".join(f"{c.get('name')}@{c.get('line')}" for c in info["classes"]) or "none"
        funcs = ", ".join(f"{f.get('name')}@{f.get('line')}" for f in info["functions"]) or "none"
        return f"{path} ({info['lines']} lines)\nclasses: {classes}\nfunctions/methods: {funcs}"

    def read_file(self, path, start_line=1, end_line=None):
        lines = self._resolve(path).read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(int(start_line or 1), 1)
        if start > len(lines):
            raise ToolError(f"file has only {len(lines)} lines")
        end = int(end_line) if end_line else start + MAX_READ_LINES - 1
        end = min(end, start + MAX_READ_LINES - 1, len(lines))
        body = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
        return f"{path} lines {start}-{end} of {len(lines)}\n{body}"

    def search_code(self, pattern):
        if not isinstance(pattern, str) or not pattern or len(pattern) > 100:
            raise ToolError("pattern must be 1-100 characters")
        try:
            rx = re.compile(pattern)
        except re.error as e:
            raise ToolError(f"invalid regex: {e}")
        hits = []
        for rel in sorted(self.files):
            text = self.read_text(rel)
            if text is None:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{rel}:{n}: {line.strip()[:160]}")
                    if len(hits) >= MAX_SEARCH_HITS:
                        return "\n".join(hits) + "\n...[stopped at max hits]"
        return "\n".join(hits) or "no matches"

    def call(self, name, args):
        try:
            if name == "get_outline":
                out = self.get_outline(args.get("path"))
            elif name == "read_file":
                out = self.read_file(args.get("path"), args.get("start_line", 1), args.get("end_line"))
            elif name == "search_code":
                out = self.search_code(args.get("pattern"))
            else:
                return f"ERROR: unknown tool '{name}'"
        except ToolError as e:
            return f"ERROR: {e}"
        except (TypeError, ValueError) as e:
            return f"ERROR: bad arguments ({e})"
        if len(out) > MAX_OUTPUT_CHARS:
            out = out[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
        return out
