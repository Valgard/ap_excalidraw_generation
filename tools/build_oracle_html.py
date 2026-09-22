"""Emit a self-contained HTML that exports every corpus scene via excalidraw.com's exact
exportToSvg (pinned esm.sh SHA) to one downloadable JSON bundle. Run: uv run python tools/build_oracle_html.py"""
import glob, json, pathlib
PIN = "https://esm.sh/@excalidraw/excalidraw@0.18.0-51ca8ab"
OUT = pathlib.Path("tools/oracle-masters.html")

def main():
    scenes = []
    for p in sorted(glob.glob("tests/inputs/**/*.excalidraw", recursive=True)):
        path = pathlib.Path(p); doc = json.loads(path.read_text(encoding="utf-8"))
        scenes.append({"stem": path.stem, "tier": path.parent.name,
                       "elements": doc.get("elements", []),
                       "appState": doc.get("appState", {}),
                       "files": doc.get("files", {})})
    scenes_json = json.dumps(scenes)
    html = _TEMPLATE.replace("__PIN__", PIN).replace("__SCENES__", scenes_json)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} with {len(scenes)} scenes")

_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Excalidraw oracle masters</title>
<style>body{font:14px ui-monospace,monospace;padding:24px}#log{white-space:pre-wrap;background:#f4f4f4;padding:12px}</style>
</head><body>
<h2>Excalidraw oracle masters (@0.18.0-51ca8ab)</h2>
<button id="go">Generate + download oracle-masters.json</button>
<div id="log">bereit.</div>
<script type="module">
import { exportToSvg } from "__PIN__";
const SCENES = __SCENES__;
const log = (m) => document.getElementById("log").textContent += "\n" + m;
document.getElementById("go").onclick = async () => {
  const out = {}, errs = [];
  for (const s of SCENES) {
    try {
      const svg = await exportToSvg({elements: s.elements, appState: s.appState, files: s.files || {}});
      out[s.tier + "/" + s.stem] = new XMLSerializer().serializeToString(svg);
      log("ok  " + s.tier + "/" + s.stem);
    } catch (e) { errs.push({key: s.tier+"/"+s.stem, error: String(e)}); log("ERR " + s.tier+"/"+s.stem+": "+e); }
  }
  const bundle = {sha: "51ca8abde450e44f8f0db1b2708e0408915c7ab1", masters: out, errors: errs};
  const blob = new Blob([JSON.stringify(bundle)], {type: "application/json"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = "oracle-masters.json"; a.click();
  log("\nDONE — " + Object.keys(out).length + " masters, " + errs.length + " errors. Save confirmed?");
};
</script></body></html>"""

if __name__ == "__main__":
    main()
