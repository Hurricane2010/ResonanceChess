import tkinter as tk
from gui import CharismaChessGUI
from utils import play_background_music, stop_background_music

# -----------------------------
#   Charisma Chess - Main Entry
# -----------------------------
# Handles setup, GUI launch, and background music control.

def main():
    # Initialize root window
    root = tk.Tk()
    root.title("Charisma Chess")

    # Start background music
    # Adjust the path if your mp3 is stored elsewhere
    play_background_music("background.mp3", volume=0.35)

    # Create and run the game GUI
    app = CharismaChessGUI(root)

    # Handle window close event cleanly
    def on_close():
        stop_background_music()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
