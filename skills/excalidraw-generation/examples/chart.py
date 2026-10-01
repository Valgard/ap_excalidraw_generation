import math
from excalidraw import Diagram

def make():
    d = Diagram("ebbinghaus")
    d.axes("eb", ox=100, oy=340, width=500, height=300)
    d.curve("eb", lambda t: 100 * math.e ** (-t / 5), 0, 30, n=60,
            ox=100, oy=340, sx=15, sy=3, stroke="#e03131")
    d.text("eb-formula", 420, 60, 200, 28, "R(t) = e^(-t/S)")
    return d

if __name__ == "__main__":
    make().write("chart.excalidraw")
