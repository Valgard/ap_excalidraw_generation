# tools/test_build_oracle_html.py
import subprocess, sys, pathlib, glob
def test_html_embeds_all_scenes_and_pinned_url(tmp_path=None):
    subprocess.run([sys.executable, "tools/build_oracle_html.py"], check=True)
    html = pathlib.Path("tools/oracle-masters.html").read_text(encoding="utf-8")
    assert "@excalidraw/excalidraw@0.18.0-51ca8ab" in html          # pinned SHA
    assert "exportToSvg({" in html                                   # object signature
    stems = [pathlib.Path(p).stem for p in glob.glob("tests/inputs/**/*.excalidraw", recursive=True)]
    assert stems, "no corpus inputs"
    for s in stems:
        assert f'"{s}"' in html, f"scene {s} not embedded"
    assert "oracle-masters.json" in html                            # single-download name
