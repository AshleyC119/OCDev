"""Verify the two archived development files without external workspace access."""
from pathlib import Path
from hashlib import sha256
import json

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "data/manifest.json").read_text(encoding="utf-8"))
assert manifest["sample_id"] == "B"
assert manifest["role_in_this_experiment"] == "development"
assert len(manifest["files"]) == 2
assert {f["side"] for f in manifest["files"]} == {"oc", "cli"}
for record in manifest["files"]:
    path = (root / record["path"]).resolve()
    if root not in path.parents:
        raise ValueError("Material path outside workspace")
    raw = path.read_bytes()
    if len(raw) != record["bytes"] or sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Material mismatch: " + str(path))
print("Verified: sample B, one OC and one CLI, both hashes match.")
