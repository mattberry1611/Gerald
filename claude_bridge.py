import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

CLAUDE_CMD = r"C:\Users\Matt\AppData\Roaming\npm\claude.cmd"
PROJECT_PATH = r"C:\Users\Matt\Desktop\RentMe"
PORT = 8787

PAGE = """<!doctype html>
<html>
<head>
  <title>CommuteCoder Voice Bridge</title>
</head>
<body style="font-family: Arial; max-width: 900px; margin: 40px auto;">
  <h1>CommuteCoder Voice Bridge</h1>

  <button onclick="startVoice()" style="font-size:20px;">🎤 Start Voice</button>
  <button onclick="sendToClaude()" style="font-size:20px;">Send to Claude</button>

  <p id="status" style="font-weight:bold;">Ready</p>

  <h3>Prompt</h3>
  <textarea id="prompt" style="width:100%; height:160px; font-size:16px;"></textarea>

  <h3>Claude Response</h3>
  <pre id="response" style="white-space:pre-wrap; background:#eee; padding:20px;"></pre>

<script>
function startVoice() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition not supported in this browser. Use Chrome or Edge.");
    return;
  }

  const rec = new SpeechRecognition();
  rec.lang = "en-AU";
  rec.continuous = false;
  rec.interimResults = false;

  document.getElementById("status").textContent = "Listening...";

  rec.onresult = function(event) {
    const text = event.results[0][0].transcript;
    document.getElementById("prompt").value = text;
    document.getElementById("status").textContent = "Heard. Sending to Claude...";
    sendToClaude();
  };

  rec.onerror = function(event) {
    document.getElementById("status").textContent = "Voice error: " + event.error;
  };

  rec.onend = function() {
    if (document.getElementById("status").textContent === "Listening...") {
      document.getElementById("status").textContent = "Stopped listening.";
    }
  };

  rec.start();
}

async function sendToClaude() {
  const prompt = document.getElementById("prompt").value;
  document.getElementById("response").textContent = "Thinking...";

  const res = await fetch("/ask?prompt=" + encodeURIComponent(prompt));
  const text = await res.text();

  document.getElementById("response").textContent = text;
  document.getElementById("status").textContent = "Done.";
}
</script>
</body>
</html>
"""

class ClaudeBridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            self.reply_html(PAGE)
            return

        if parsed.path == "/ask":
            query = urllib.parse.parse_qs(parsed.query)
            prompt = query.get("prompt", [""])[0]

            if not prompt:
                self.reply_text(400, "No prompt provided")
                return

            result = subprocess.run(
                [CLAUDE_CMD, "-p", prompt],
                cwd=PROJECT_PATH,
                capture_output=True,
                text=True
            )

            output = result.stdout

            if result.stderr:
                output += "\\n\\nERRORS:\\n" + result.stderr

            self.reply_text(200, output)
            return

        self.reply_text(404, "Unknown endpoint")

    def reply_html(self, message):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8", errors="replace"))

    def reply_text(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8", errors="replace"))

print(f"CommuteCoder Voice Bridge running at http://127.0.0.1:{PORT}")
server = HTTPServer(("127.0.0.1", PORT), ClaudeBridgeHandler)
server.serve_forever()