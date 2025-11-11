import tkinter as tk
from gui import CharismaChessGUI

if __name__ == "__main__":
    root = tk.Tk()
    app = CharismaChessGUI(root)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
