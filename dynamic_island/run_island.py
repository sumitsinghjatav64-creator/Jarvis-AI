"""
run_island.py
Master Launcher for Dynamic Island AI Companion & Jev-Ultrafast.
Launches the background FastAPI server and displays the PyQt6 transparent HUD.
"""
import sys
import threading
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

from config import LOCAL_SERVER_PORT
from server import run_server
from window import DynamicIslandWindow

def start_server_in_thread():
    t = threading.Thread(target=run_server, args=(LOCAL_SERVER_PORT,), daemon=True)
    t.start()
    time.sleep(0.8)  # Allow server to bind cleanly
    return t

def main():
    print("=" * 60)
    print("🚀 Starting Dynamic Island AI Companion & Jev-Ultrafast...")
    print(f"📡 Local server initializing on http://127.0.0.1:{LOCAL_SERVER_PORT}")
    print("=" * 60)

    # 1. Start backend server
    start_server_in_thread()

    # 2. Start PyQt6 GUI Application
    app = QApplication(sys.argv)
    app.setApplicationName("Dynamic Island AI")

    # 3. Create & show transparent desktop overlay
    window = DynamicIslandWindow(port=LOCAL_SERVER_PORT)
    window.show()

    print("✨ Dynamic Island is now floating at the top-center of your screen!")
    print("👉 Use the Test Controls in the drawer or click the pill to expand.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
