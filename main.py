"""
Jerry AI - Web App Version
Runs as a proper web server for Render deployment
"""

import os
import asyncio
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
from agents.orchestrator import Orchestrator

load_dotenv()

app = Flask(__name__)
orchestrator = Orchestrator()

# Initialize Jerry on startup
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(orchestrator.initialize())
print("✅ Jerry is ready.")

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jerry AI</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0f0f0f; color: #e8e8e8;
    height: 100vh; display: flex; flex-direction: column;
  }
  header {
    padding: 16px 24px; background: #1a1a1a;
    border-bottom: 1px solid #2a2a2a;
    display: flex; align-items: center; gap: 12px;
  }
  .logo {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #7c3aed, #4f46e5);
    border-radius: 10px; display: flex;
    align-items: center; justify-content: center;
    font-weight: 700; font-size: 16px;
  }
  header h1 { font-size: 18px; font-weight: 600; }
  header p  { font-size: 12px; color: #666; margin-top: 1px; }
  .status {
    margin-left: auto; display: flex;
    align-items: center; gap: 6px;
    font-size: 12px; color: #4ade80;
  }
  .dot {
    width: 7px; height: 7px; background: #4ade80;
    border-radius: 50%; animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  #chat {
    flex: 1; overflow-y: auto; padding: 24px;
    display: flex; flex-direction: column; gap: 16px;
  }
  .msg {
    max-width: 75%; padding: 12px 16px; border-radius: 16px;
    line-height: 1.6; font-size: 14px;
    white-space: pre-wrap; word-wrap: break-word;
  }
  .msg.tom {
    background: #4f46e5; color: #fff;
    align-self: flex-end; border-bottom-right-radius: 4px;
  }
  .msg.jerry {
    background: #1e1e1e; color: #e8e8e8;
    align-self: flex-start; border-bottom-left-radius: 4px;
    border: 1px solid #2a2a2a;
  }
  .msg.jerry .label {
    font-size: 11px; color: #7c3aed;
    font-weight: 600; margin-bottom: 6px; letter-spacing: 0.5px;
  }
  .typing {
    background: #1e1e1e; border: 1px solid #2a2a2a;
    align-self: flex-start; border-bottom-left-radius: 4px;
    padding: 14px 18px; border-radius: 16px;
  }
  .typing span {
    display: inline-block; width: 7px; height: 7px;
    background: #666; border-radius: 50%; margin: 0 2px;
    animation: bounce 1.2s infinite;
  }
  .typing span:nth-child(2){animation-delay:.2s}
  .typing span:nth-child(3){animation-delay:.4s}
  @keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}
  .suggestions {
    display: flex; flex-wrap: wrap; gap: 8px;
    padding: 0 24px 12px; background: #1a1a1a;
  }
  .suggestion {
    background: #2a2a2a; border: 1px solid #3a3a3a;
    border-radius: 20px; padding: 6px 14px;
    font-size: 12px; color: #aaa; cursor: pointer; transition: all .2s;
  }
  .suggestion:hover { background:#3a3a3a; color:#e8e8e8; border-color:#4f46e5; }
  #input-area {
    padding: 16px 24px 24px; background: #1a1a1a;
    border-top: 1px solid #2a2a2a; display: flex; gap: 10px;
  }
  #user-input {
    flex: 1; background: #2a2a2a; border: 1px solid #3a3a3a;
    border-radius: 12px; padding: 12px 16px; color: #e8e8e8;
    font-size: 14px; outline: none; transition: border-color .2s;
    resize: none; height: 48px; font-family: inherit;
  }
  #user-input:focus { border-color: #4f46e5; }
  #user-input::placeholder { color: #555; }
  #send-btn {
    background: #4f46e5; color: #fff; border: none;
    border-radius: 12px; padding: 12px 20px;
    font-size: 14px; font-weight: 600; cursor: pointer;
    transition: background .2s; height: 48px;
  }
  #send-btn:hover    { background: #4338ca; }
  #send-btn:disabled { background: #333; cursor: not-allowed; }
  ::-webkit-scrollbar{width:4px}
  ::-webkit-scrollbar-thumb{background:#333;border-radius:4px}
</style>
</head>
<body>
<header>
  <div class="logo">J</div>
  <div>
    <h1>Jerry AI</h1>
    <p>Tom's Personal AI</p>
  </div>
  <div class="status"><div class="dot"></div>Online</div>
</header>

<div id="chat">
  <div class="msg jerry">
    <div class="label">JERRY</div>
    Hey Tom! I'm fully loaded and ready. I can research anything on the web, analyse stocks, predict sports games with 4-layer analysis, and check what people are saying on social media. What do you need?
  </div>
</div>

<div class="suggestions">
  <div class="suggestion" onclick="quickSend(this)">Analyze Tesla stock</div>
  <div class="suggestion" onclick="quickSend(this)">Research latest AI news</div>
  <div class="suggestion" onclick="quickSend(this)">Predict Lakers vs Celtics</div>
  <div class="suggestion" onclick="quickSend(this)">What's trending on Reddit about Bitcoin</div>
</div>

<div id="input-area">
  <textarea id="user-input" placeholder="Ask Jerry anything..."></textarea>
  <button id="send-btn" onclick="sendMessage()">Send</button>
</div>

<script>
const chat    = document.getElementById('chat');
const input   = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

function quickSend(el) { input.value = el.textContent; sendMessage(); }

function addMsg(text, sender) {
  const div = document.createElement('div');
  div.className = 'msg ' + sender;
  if (sender === 'jerry') {
    div.innerHTML = '<div class="label">JERRY</div>' + escapeHtml(text);
  } else {
    div.textContent = text;
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function addTyping() {
  const d = document.createElement('div');
  d.className = 'typing'; d.id = 'typing';
  d.innerHTML = '<span></span><span></span><span></span>';
  chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typing');
  if (t) t.remove();
}

function escapeHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;')
          .replace(/>/g,'&gt;').replace(/\\n/g,'<br>');
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  addMsg(text, 'tom');
  input.value = '';
  sendBtn.disabled = true;
  addTyping();
  try {
    const res  = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await res.json();
    removeTyping();
    addMsg(data.response || 'Something went wrong.', 'jerry');
  } catch(err) {
    removeTyping();
    addMsg('Connection error — please try again.', 'jerry');
  }
  sendBtn.disabled = false;
  input.focus();
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    data    = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"response": "I didn't catch that Tom, try again."})
    try:
        response = loop.run_until_complete(orchestrator.run(message))
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"response": f"Jerry hit an error: {str(e)}"})


@app.route("/health")
def health():
    return jsonify({"status": "Jerry is alive", "ready": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
