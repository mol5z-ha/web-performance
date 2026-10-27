"""Validate skill metadata and relative Markdown links (PyYAML required)."""
from pathlib import Path
import re
import yaml

root = Path(__file__).resolve().parents[1]
text = (root / "SKILL.md").read_text(encoding="utf-8")
match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
assert match, "Missing YAML frontmatter"
metadata = yaml.safe_load(match.group(1))
assert metadata["name"] == "web-performance"
assert isinstance(metadata["description"], str) and metadata["description"].strip()
assert len(metadata["description"]) <= 1024
ui = yaml.safe_load((root / "agents/openai.yaml").read_text(encoding="utf-8"))
assert "$web-performance" in ui["interface"]["default_prompt"]
assert 25 <= len(ui["interface"]["short_description"]) <= 64
assert ui.get("policy", {}).get("allow_implicit_invocation", True) is True
for path in root.rglob("*.md"):
    content = path.read_text(encoding="utf-8")
    assert "[TODO:" not in content, f"Unfinished scaffold: {path.name}"
    for target in re.findall(r"\]\(([^)]+)\)", content):
        if "://" in target or target.startswith("#"):
            continue
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        assert resolved.is_relative_to(root), f"Reference escapes package: {target}"
        assert resolved.exists(), f"Missing reference: {target}"
print("Skill metadata and relative links validated.")
