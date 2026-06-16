import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pyautogui
import pyperclip

CURSOR_PATH = r"C:\Users\Matt\AppData\Local\Programs\cursor\Cursor.exe"
PORT = 8765

CHAT_X = 3369
CHAT_Y = 977

class CommuteCoderHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/send_to_cursor_and_submit":
            query = urllib.parse.parse_qs(parsed.query)
            text = query.get("text", [""])[0]

            pyperclip.copy(text)

            os.system(f'start "" "{CURSOR_PATH}"')
            time.sleep(2)

            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.5)

            pyautogui.click(CHAT_X, CHAT_Y)
            time.sleep(0.3)

            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.2)

            pyautogui.hotkey("ctrl", "v")
            time.sleep(2)

            pyautogui.click(3543, 1019)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Prompt submitted to Cursor")

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Unknown command")

print(f"CommuteCoder Agent running at http://127.0.0.1:{PORT}")
server = HTTPServer(("127.0.0.1", PORT), CommuteCoderHandler)
server.serve_forever()