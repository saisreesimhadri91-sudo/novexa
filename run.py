import sys
import time
import threading
import webbrowser
from server import start_server

def open_browser(port=8000):
    time.sleep(1.2)
    url = f"http://localhost:{port}"
    print(f"Opening NIVORA in your default web browser: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    PORT = 8000
    threading.Thread(target=open_browser, args=(PORT,), daemon=True).start()
    try:
        start_server(PORT)
    except KeyboardInterrupt:
        print("\nNIVORA Server stopped safely.")
        sys.exit(0)
