import re, pathlib
root = pathlib.Path(".")
src_path = root / "CLAUDE.md"
src = src_path.read_text(encoding="utf-8")
blocks = re.findall(r"^=====BEGIN FILE: (.+?)=====\n(.*?)^=====END FILE: \1=====$",
                    src, flags=re.S | re.M)
assert len(blocks) >= 9, f"expected >= 9 embedded files, found {len(blocks)}"
(root / "docs").mkdir(exist_ok=True)
backup = re.sub(r"^=====BEGIN FILE: backend/\.env=====\n.*?^=====END FILE: backend/\.env=====\n", "",
                src, flags=re.S | re.M)                     # never keep the secret in docs/
(root / "docs" / "BOOTSTRAP_CLAUDE.md").write_text(backup, encoding="utf-8")
for path, body in blocks:
    p = root / path.strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    if p.name == ".env":
        p.chmod(0o600)
        print(f"wrote {p} (secret, not printed)")
    else:
        print(f"wrote {p} ({len(body):,} chars)")
print("unpacked", len(blocks), "files; CLAUDE.md is now the short rules + autopilot version")
