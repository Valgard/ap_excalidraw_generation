# tools/test_integrate_oracle_masters.py
import subprocess, sys, json, pathlib


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
    real_oracle = pathlib.Path("tests/oracle")
    assert not real_oracle.exists() or not (real_oracle / "manifest.json").exists(), (
        "Script wrote into the real tests/oracle/ — isolation broken"
    )
