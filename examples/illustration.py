from excalidraw import Diagram

def make():
    d = Diagram("berater-buero")
    office = d.box("office", 40, 60, 320, 220, fill="#dee2e6")
    llm = d.ellipse("llm", 120, 150, 90, 90, fill="#a5d8ff", text="LLM")
    d.group("office-grp", office, llm)
    d.text("office-cap", 60, 80, 200, 24, "leeres Büro", align="left")
    tools = d.box("tools", 600, 120, 160, 60, fill="#fff3bf", text="Wetterdienst")
    d.connect("bridge", office, tools, label="braucht")
    return d

if __name__ == "__main__":
    make().write("illustration.excalidraw")
