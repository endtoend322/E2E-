from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
import time
import threading
import re
import logging
from datetime import datetime
from collections import deque
import os
import sys

app = Flask(__name__)
CORS(app)

# Configuration
MAX_LOGS = 500
log_storage = deque(maxlen=MAX_LOGS)
active_session = {
    "running": False,
    "thread": None,
    "stop_flag": False,
    "tokens": [],
    "message": "",
    "header_name": "",
    "delay_seconds": 5,
    "stats": {"sent": 0, "failed": 0, "current_token_index": 0}
}

# HTML Template (embedded for single-file deployment)
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Offline Convo E2E | Messenger Auto-Sender</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        body { background: #f4f7fc; font-family: 'Segoe UI', Roboto, sans-serif; }
        .card-shadow { border-radius: 28px; box-shadow: 0 12px 28px rgba(0,0,0,0.08); border: none; }
        .console-area { background: #1e1e2f; color: #e0e0e0; font-family: 'Fira Code', monospace; font-size: 13px; border-radius: 20px; height: 320px; overflow-y: auto; padding: 16px; white-space: pre-wrap; word-break: break-word; }
        .btn-submit { background: #0084ff; border: none; border-radius: 40px; padding: 10px 28px; font-weight: 600; }
        .btn-stop { background: #e34f4f; border: none; border-radius: 40px; padding: 10px 28px; font-weight: 600; }
        .badge-e2e { background: #25c2a0; color: white; font-size: 0.7rem; padding: 6px 14px; border-radius: 30px; }
        footer { font-size: 0.85rem; border-top: 1px solid #e2e8f0; }
        .form-control, .form-select { border-radius: 20px; padding: 10px 16px; }
    </style>
</head>
<body class="p-3 p-md-4">
<div class="container-lg py-2 py-md-3">
    <div class="d-flex flex-wrap align-items-center justify-content-between mb-4">
        <div><h1 class="display-6 fw-semibold" style="color:#1a3e50;"><i class="fab fa-facebook-messenger me-2"></i> Offline Convo E2E</h1><p class="text-secondary">Token-based · Facebook Messenger Autopilot · 24/7 Non-Stop</p></div>
        <div><span class="badge-e2e"><i class="fas fa-lock me-1"></i> End-to-End Encryption by Virat Rajput</span></div>
    </div>
    <div class="row g-4">
        <div class="col-lg-5 col-xl-4">
            <div class="card card-shadow bg-white p-3 p-xl-4">
                <div class="card-body">
                    <h5 class="fw-bold mb-3"><i class="fas fa-key me-2"></i>Token Management</h5>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">🔑 Facebook Tokens (one per line) - EAAD6V7 only</label>
                        <textarea class="form-control" id="tokensInput" rows="3" placeholder="EAAD6V7...xyz&#10;EAAD6V7...abc"></textarea>
                        <div class="mt-2"><button class="btn btn-outline-secondary btn-sm" id="uploadTokenFileBtn"><i class="fas fa-upload"></i> Upload .txt token file</button><input type="file" id="tokenFileInput" accept=".txt" style="display:none"></div>
                    </div>
                    <hr>
                    <h5 class="fw-bold mb-3"><i class="fas fa-comment-dots me-2"></i>Message & Header</h5>
                    <div class="mb-3"><input type="text" class="form-control" id="headerName" placeholder="Header / Sender Name (Optional)"></div>
                    <div class="mb-3"><textarea class="form-control" id="messageContent" rows="3" placeholder="Type your message here... or upload .txt file"></textarea><div class="mt-2"><label class="btn btn-outline-secondary btn-sm" for="messageFileUpload"><i class="fas fa-file-alt"></i> Upload message .txt</label><input type="file" id="messageFileUpload" accept=".txt" style="display:none"></div></div>
                    <div class="mb-4"><label class="fw-semibold">⏱️ Delay Between Messages (seconds)</label><input type="range" id="delaySlider" class="form-range" min="1" max="60" step="1" value="5"><span id="delayValue" class="badge bg-secondary ms-2 px-3 py-2">5 s</span></div>
                    <div class="d-flex gap-3"><button id="submitBtn" class="btn btn-submit text-white px-4"><i class="fas fa-paper-plane me-1"></i> Start Server</button><button id="stopBtn" class="btn btn-stop text-white px-4"><i class="fas fa-stop-circle me-1"></i> Stop 🛑</button></div>
                    <div class="alert alert-info mt-3 small"><i class="fas fa-info-circle"></i> Only EAAD6V7 tokens are supported. Messages sent via Facebook Graph API.</div>
                </div>
            </div>
        </div>
        <div class="col-lg-7 col-xl-8">
            <div class="card card-shadow bg-white p-3 p-xl-4 h-100">
                <div class="d-flex justify-content-between align-items-center mb-2"><h5 class="fw-bold mb-0"><i class="fas fa-terminal me-2"></i>Live Console</h5><button id="clearConsoleBtn" class="btn btn-sm btn-outline-secondary rounded-pill"><i class="fas fa-eraser"></i> Clear</button></div>
                <div id="liveConsole" class="console-area mb-2"><span style="color:#a5d6ff;">>> Offline Convo E2E • Messenger Engine Ready</span><br><span style="color:#9cd9b4;">● Idle | Waiting for start command</span><br></div>
                <div class="text-muted small"><i class="fas fa-sync-alt"></i> Non-stop 24/7 runs on Render</div>
            </div>
        </div>
    </div>
    <footer class="mt-5 pt-3 text-center text-secondary"><p>All Rights Reserved 2026 | Made by Virat Rajput | End-to-End Offline Server</p></footer>
</div>
<script>
    const consoleDiv = document.getElementById('liveConsole');
    function addLog(msg, type='info'){const time=new Date().toLocaleTimeString();let color='#e0e0e0';if(type==='error')color='#ff9e8f';else if(type==='success')color='#a3f0b0';else if(type==='warn')color='#ffd966';const div=document.createElement('div');div.innerHTML=`[${time}] <span style="color:${color};">${msg}</span>`;consoleDiv.appendChild(div);consoleDiv.scrollTop=consoleDiv.scrollHeight;}
    let isRunning=false,logInterval=null,lastLogCount=0;
    async function fetchLogs(){if(!isRunning)return;try{const res=await fetch('/api/logs');const data=await res.json();if(data.logs&&data.logs.length>lastLogCount){for(let i=lastLogCount;i<data.logs.length;i++){const log=data.logs[i];if(log.level==='error')addLog(log.message,'error');else if(log.level==='success')addLog(log.message,'success');else if(log.level==='warn')addLog(log.message,'warn');else addLog(log.message,'info');}lastLogCount=data.logs.length;}}catch(e){}}
    document.getElementById('uploadTokenFileBtn').onclick=()=>document.getElementById('tokenFileInput').click();
    document.getElementById('tokenFileInput').onchange=e=>{const file=e.target.files[0];if(file){const reader=new FileReader();reader.onload=ev=>{const lines=ev.target.result.split(/\\r?\\n/).filter(l=>l.trim());const existing=document.getElementById('tokensInput').value;document.getElementById('tokensInput').value=existing?(existing+'\\n'+lines.join('\\n')):lines.join('\\n');addLog(`✅ Loaded ${lines.length} tokens`,'success');};reader.readAsText(file);}};
    document.getElementById('messageFileUpload').onchange=e=>{const file=e.target.files[0];if(file){const reader=new FileReader();reader.onload=ev=>{document.getElementById('messageContent').value=ev.target.result;addLog('📄 Message loaded','success');};reader.readAsText(file);}};
    document.getElementById('delaySlider').oninput=()=>document.getElementById('delayValue').innerText=document.getElementById('delaySlider').value+' s';
    document.getElementById('clearConsoleBtn').onclick=()=>{consoleDiv.innerHTML='<span style="color:#a5d6ff;">>> Console cleared.</span><br>';};
    document.getElementById('submitBtn').onclick=async()=>{if(isRunning){addLog('Already running','warn');return;}const tokens=document.getElementById('tokensInput').value.trim().split('\\n').filter(t=>t.trim().startsWith('EAAD6V7'));if(tokens.length===0){addLog('❌ Need at least one EAAD6V7 token','error');return;}const message=document.getElementById('messageContent').value.trim();if(!message){addLog('❌ Message empty','error');return;}const payload={tokens,message,header_name:document.getElementById('headerName').value.trim()||"Offline Convo",delay_seconds:parseInt(document.getElementById('delaySlider').value)};try{const res=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await res.json();if(data.status==='started'){isRunning=true;lastLogCount=0;addLog('✅ Automation started successfully','success');if(logInterval)clearInterval(logInterval);logInterval=setInterval(fetchLogs,1500);}else addLog('Start failed: '+data.error,'error');}catch(err){addLog('Connection error','error');}};
    document.getElementById('stopBtn').onclick=async()=>{if(!isRunning){addLog('No active session','warn');return;}try{await fetch('/api/stop',{method:'POST'});isRunning=false;if(logInterval){clearInterval(logInterval);logInterval=null;}addLog('🛑 Server stopped','success');}catch(e){addLog('Stop error','error');}};
</script>
</body>
</html>'''

def add_log(message, level="info"):
    """Add log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {"timestamp": timestamp, "message": message, "level": level}
    log_storage.append(log_entry)
    print(f"[{timestamp}] {level.upper()}: {message}")

def validate_token(token):
    """Validate token format - only EAAD6V7 tokens accepted"""
    if not token or not isinstance(token, str):
        return False
    # Strict validation: must start with EAAD6V7 and be reasonably long
    return token.startswith('EAAD6V7') and len(token) > 20

def send_facebook_message(access_token, recipient_id, message_text):
    """
    Send message via Facebook Messenger Graph API
    Using the send API endpoint
    """
    url = f"https://graph.facebook.com/v18.0/me/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "messaging_type": "RESPONSE"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if "message_id" in result:
                return True, "Sent successfully"
            else:
                return False, f"API error: {result.get('error', {}).get('message', 'Unknown error')}"
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
            return False, error_msg
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"

def get_user_id_from_token(access_token):
    """Get user's Facebook ID from token for validation"""
    url = f"https://graph.facebook.com/v18.0/me?access_token={access_token}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return True, data.get('id')
        return False, None
    except:
        return False, None

def messenger_worker():
    """Background worker that sends messages continuously"""
    add_log("🚀 Messenger worker thread started", "success")
    
    tokens = active_session["tokens"]
    message = active_session["message"]
    header_name = active_session["header_name"]
    delay = active_session["delay_seconds"]
    
    # First validate all tokens
    valid_tokens = []
    for token in tokens:
        if validate_token(token):
            valid, user_id = get_user_id_from_token(token)
            if valid:
                valid_tokens.append({"token": token, "user_id": user_id})
                add_log(f"✅ Token validated: {user_id} (EAAD6V7)", "success")
            else:
                add_log(f"❌ Invalid token (can't get user): {token[:20]}...", "error")
        else:
            add_log(f"❌ Rejected token - must start with EAAD6V7: {token[:20]}...", "error")
    
    if not valid_tokens:
        add_log("❌ No valid EAAD6V7 tokens found. Worker stopped.", "error")
        active_session["running"] = False
        return
    
    active_session["valid_tokens"] = valid_tokens
    add_log(f"📊 Ready with {len(valid_tokens)} valid EAAD6V7 token(s)", "success")
    add_log(f"💬 Message: {message[:100]}{'...' if len(message)>100 else ''}", "info")
    add_log(f"⏱️ Delay: {delay} seconds between messages", "info")
    
    # For demo/example: We need recipient IDs. In production, you would fetch threads.
    # For this implementation, we'll demonstrate by sending to self (user's own ID)
    # Or you can modify to fetch conversation list from /me/conversations
    add_log("ℹ️ Sending messages to self (test mode). For production, modify to fetch threads.", "warn")
    
    token_index = 0
    sent_count = 0
    fail_count = 0
    
    while active_session["running"] and not active_session["stop_flag"]:
        current_token_info = valid_tokens[token_index % len(valid_tokens)]
        token = current_token_info["token"]
        user_id = current_token_info["user_id"]
        
        # Send message to self (or you can modify recipient to specific user/page)
        # For actual conversation: you would list threads and send to each participant
        recipient_id = user_id  # Send to self for testing/demo
        
        add_log(f"📤 Sending to {recipient_id} using token {token[:15]}...", "info")
        success, result_msg = send_facebook_message(token, recipient_id, message)
        
        if success:
            sent_count += 1
            active_session["stats"]["sent"] = sent_count
            add_log(f"✅ Message #{sent_count} sent successfully", "success")
        else:
            fail_count += 1
            active_session["stats"]["failed"] = fail_count
            add_log(f"❌ Failed: {result_msg}", "error")
        
        active_session["stats"]["current_token_index"] = token_index
        token_index += 1
        
        # Wait before next message (check stop flag every second)
        for _ in range(delay):
            if active_session["stop_flag"] or not active_session["running"]:
                break
            time.sleep(1)
    
    add_log(f"🛑 Worker stopped. Total: {sent_count} sent, {fail_count} failed", "info")
    active_session["running"] = False

@app.route('/')
def index():
    """Serve the main HTML interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/start', methods=['POST'])
def start_automation():
    """Start the background messaging worker"""
    if active_session["running"]:
        return jsonify({"status": "error", "error": "Session already running"}), 400
    
    data = request.json
    tokens = data.get('tokens', [])
    message = data.get('message', '').strip()
    header_name = data.get('header_name', 'Offline Convo')
    delay_seconds = data.get('delay_seconds', 5)
    
    # Filter only EAAD6V7 tokens
    filtered_tokens = [t for t in tokens if t.startswith('EAAD6V7')]
    
    if not filtered_tokens:
        add_log("No EAAD6V7 tokens provided", "error")
        return jsonify({"status": "error", "error": "At least one EAAD6V7 token required"}), 400
    
    if not message:
        return jsonify({"status": "error", "error": "Message content is empty"}), 400
    
    # Setup active session
    active_session["running"] = True
    active_session["stop_flag"] = False
    active_session["tokens"] = filtered_tokens
    active_session["message"] = message
    active_session["header_name"] = header_name
    active_session["delay_seconds"] = max(1, min(60, delay_seconds))
    active_session["stats"] = {"sent": 0, "failed": 0, "current_token_index": 0}
    
    # Start worker thread
    thread = threading.Thread(target=messenger_worker, daemon=True)
    thread.start()
    active_session["thread"] = thread
    
    add_log(f"🚀 Started with {len(filtered_tokens)} EAAD6V7 token(s)", "success")
    return jsonify({"status": "started", "token_count": len(filtered_tokens)})

@app.route('/api/stop', methods=['POST'])
def stop_automation():
    """Stop the background messaging worker"""
    if not active_session["running"]:
        return jsonify({"status": "stopped", "message": "No active session"})
    
    active_session["stop_flag"] = True
    active_session["running"] = False
    
    add_log("🛑 Stop command received", "warn")
    return jsonify({"status": "stopped", "stats": active_session["stats"]})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Retrieve recent logs for console display"""
    return jsonify({"logs": list(log_storage)})

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current session status"""
    return jsonify({
        "running": active_session["running"],
        "stats": active_session["stats"],
        "token_count": len(active_session.get("tokens", []))
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render uptime monitoring"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# For Render deployment - gunicorn will run this
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    add_log(f"🌐 Offline Convo E2E Server starting on port {port}", "success")
    add_log("🔐 End-to-End Encryption by Virat Rajput", "info")
    add_log("📱 Facebook Messenger Token Server Active", "success")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)