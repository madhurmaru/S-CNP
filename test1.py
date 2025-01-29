import os
import json
from flask import Flask, render_template_string, request, send_from_directory
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test1'
socketio = SocketIO(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

messages = []
user_last_message_time = {}
user_data = {}
USER_DATA_FILE = "user_data.json"

RATE_LIMIT_SECONDS = 3  

if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        user_ip_log = json.load(f)
else:
    user_ip_log = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>H Section Chat</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; color: #333; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        h1 { color: #007BFF; }
        .chat { width: 80%; max-width: 800px; border: 1px solid #ddd; padding: 10px; border-radius: 5px; background: #fff; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); }
        .messages { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; }
        .messages p { margin: 5px 0; }
        form { display: flex; gap: 10px; }
        input[type="text"], input[type="file"] { flex: 1; padding: 8px; border: 1px solid #ccc; border-radius: 3px; }
        button { padding: 8px 15px; background-color: #007BFF; color: white; border: none; border-radius: 3px; cursor: pointer; }
        button:hover { background-color: #0056b3; }
    </style>
    <script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const socket = io();
            const messagesDiv = document.querySelector('.messages');
            const form = document.querySelector('form');
            const input = document.querySelector('input[name="message"]');
            const fileInput = document.querySelector('input[name="file"]');
            const sendFileBtn = document.querySelector('button[name="sendFile"]');
            let username = localStorage.getItem('username');

            socket.emit('check_username');

            socket.on('set_username', (savedUsername) => {
                username = savedUsername;
                localStorage.setItem('username', username);
            });

            socket.on('request_username', () => {
                username = prompt("Enter a unique username:");
                if (!username) {
                    alert("Username is required to chat.");
                    return;
                }
                localStorage.setItem('username', username);
                socket.emit('register_username', username);
            });

            socket.on('new_message', (message) => {
                const p = document.createElement('p');
                if (message.type === "file") {
                    p.innerHTML = `<strong>${message.username}:</strong> <a href="${message.url}" target="_blank">${message.filename}</a>`;
                } else {
                    p.innerHTML = `<strong>${message.username}:</strong> ${message.text}`;
                }
                messagesDiv.appendChild(p);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            });

            socket.on('error_message', (error) => {
                alert(error);
            });

            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const message = input.value.trim();
                if (message) {
                    socket.emit('send_message', { username, message });
                    input.value = '';
                }
            });

            sendFileBtn.addEventListener('click', () => {
                const file = fileInput.files[0];
                if (file) {
                    const formData = new FormData();
                    formData.append("file", file);
                    formData.append("username", username);

                    fetch('/upload', {
                        method: 'POST',
                        body: formData
                    }).then(response => response.json()).then(data => {
                        if (data.success) {
                            socket.emit('send_file', { username, filename: data.filename, url: data.url });
                        } else {
                            alert("File upload failed.");
                        }
                    });
                    fileInput.value = "";
                }
            });
        });
    </script>
</head>
<body>
    <h1>H Section Chat</h1>
    <div class="chat">
        <div class="messages">
            {% for msg in messages %}
                {% if msg.type == "file" %}
                    <p><strong>{{ msg.username }}:</strong> <a href="{{ msg.url }}" target="_blank">{{ msg.filename }}</a></p>
                {% else %}
                    <p><strong>{{ msg.username }}:</strong> {{ msg.text }}</p>
                {% endif %}
            {% endfor %}
        </div>
        <form>
            <input type="text" name="message" placeholder="Type your message here..." required>
            <button type="submit">Send</button>
        </form>
        <input type="file" name="file">
        <button name="sendFile">Upload & Send File</button>
    </div>
</body>
</html>
"""

@app.route('/')
def chat():
    return render_template_string(HTML_TEMPLATE, messages=messages)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return {"success": False, "error": "No file uploaded"}, 400

    file = request.files['file']
    username = request.form.get("username", "Unknown")
    filename = file.filename
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    file_url = f"/uploads/{filename}"
    return {"success": True, "filename": filename, "url": file_url}

@socketio.on('send_message')
def handle_message(data):
    user_ip = request.remote_addr
    username = user_ip_log.get(user_ip, "Unknown")

    message_text = data.get("message", "").strip()
    if len(message_text) > 50:
        message_text = message_text[:50] + "..."

    message_data = {"username": username, "text": message_text, "type": "text"}
    messages.append(message_data)
    emit('new_message', message_data, broadcast=True)

@socketio.on('send_file')
def handle_file(data):
    message_data = {"username": data["username"], "filename": data["filename"], "url": data["url"], "type": "file"}
    messages.append(message_data)
    emit('new_message', message_data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000, debug=True)
