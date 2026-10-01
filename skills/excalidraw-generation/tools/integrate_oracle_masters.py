"""Turn a downloaded oracle-masters.json into font-factored oracle masters.

Run:
    uv run python tools/integrate_oracle_masters.py --bundle <path> --date YYYY-MM-DD [--out tests/oracle]
"""
import argparse, json, pathlib, sys

sys.path.insert(0, "tools")
from svg_compare import sub_font_block


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Integrate oracle-masters.json → font-factored SVGs + manifest"
    )
    ap.add_argument("--bundle", required=True, help="Path to oracle-masters.json")
    ap.add_argument("--date", required=True, help="Generation date (YYYY-MM-DD)")
    ap.add_argument(
        "--out",
        default="tests/oracle",
        help="Output directory (default: tests/oracle)",
    )
    a = ap.parse_args(argv)

    bundle = json.loads(pathlib.Path(a.bundle).read_text(encoding="utf-8"))
    out = pathlib.Path(a.out)
    count = 0

    for key, svg in bundle["masters"].items():
        dst = out / f"{key}.svg"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(sub_font_block(svg), encoding="utf-8")
        count += 1

    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "sha": bundle.get("sha"),
                "generated": a.date,
                "count": count,
                "errors": bundle.get("errors", []),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"integrated {count} masters → {out}")


if __name__ == "__main__":
    main()
