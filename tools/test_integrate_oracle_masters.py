# tools/test_integrate_oracle_masters.py
import hashlib
import subprocess, sys, json, pathlib


def _tree_digest(root):
    """Content fingerprint of a directory tree: relative path + sha256 per file.

    Returns None for a missing tree, so a directory that appears where there was
    none also registers as a change.
    """
    if not root.exists():
        return None
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode("utf-8"))
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def test_integrate_writes_factored_masters_and_manifest(tmp_path):
    bundle = {
        "sha": "51ca8abde450e44f8f0db1b2708e0408915c7ab1",
        "masters": {
            "atomic/diamond": '<svg><defs><style class="style-fonts">@font-face{src:url(AAAA)}</style></defs><path d="M0 0"/></svg>'
        },
        "errors": [],
    }
    bp = tmp_path / "oracle-masters.json"
    bp.write_text(json.dumps(bundle))
    out_dir = tmp_path / "oracle"

    # Fingerprint the real corpus BEFORE the run. An existence check cannot serve
    # here: tests/oracle/ and its manifest.json are committed files, so they are
    # present either way. Only their content can tell the two cases apart.
    real_oracle = pathlib.Path("tests/oracle")
    before = _tree_digest(real_oracle)

    subprocess.run(
        [
            sys.executable,
            "tools/integrate_oracle_masters.py",
            "--bundle",
            str(bp),
            "--date",
            "2026-07-05",
            "--out",
            str(out_dir),
        ],
        check=True,
    )
    svg = (out_dir / "atomic/diamond.svg").read_text(encoding="utf-8")
    assert "@@FONTS@@" in svg and "AAAA" not in svg and '<path d="M0 0"/>' in svg
    man = json.loads((out_dir / "manifest.json").read_text())
    assert (
        man["sha"].startswith("51ca8ab")
        and man["count"] == 1
        and man["generated"] == "2026-07-05"
    )
    # Confirm the REAL tests/oracle/ was NOT touched
    assert _tree_digest(real_oracle) == before, (
        "Script wrote into the real tests/oracle/ — isolation broken"
    )
