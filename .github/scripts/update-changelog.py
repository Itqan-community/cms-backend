#!/usr/bin/env python3
import os
import re

version = os.environ["SEMVER"]
ai_notes = open("/tmp/ai-release-notes.txt").read().strip()  # nosec B108
changelog = "CHANGELOG.md"

with open(changelog) as f:
    content = f.read()

ai_block = f"### AI Summary\n\n{ai_notes}\n\n### Commits\n\n"
content = re.sub(
    rf"(## {re.escape(version)}[^\n]*\n\n)",
    rf"\g<1>{ai_block}",
    content,
    count=1,
)

with open(changelog, "w") as f:
    f.write(content)

print(f"CHANGELOG.md updated with AI summary for {version}")
