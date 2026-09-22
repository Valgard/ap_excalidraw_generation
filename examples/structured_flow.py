from excalidraw import Diagram

def make():
    d = Diagram("consistency-metrics")
    before = d.panel("before", title="Vorher (Phase 2)", fill="#fff0f0", accent="#f08c8c",
                     rows=["Gesamtkonsistenz 7/10", "Fehlerbehandlung 14/16", "Wizard-Struktur 4/5"])
    after = d.panel("after", x=560, title="Nachher (Phase 4)", fill="#ebfbee", accent="#69db7c",
                    rows=["Gesamtkonsistenz 9.8/10 ✅", "Fehlerbehandlung 15/15 ✅", "Wizard-Struktur 5/5 ✅"])
    d.connect("flow", before, after, label="SDD-Restrukturierung", dashed=True)
    return d

if __name__ == "__main__":
    make().write("structured_flow.excalidraw")
