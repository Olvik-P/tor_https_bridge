// Matrix rain animation
const canvas = document.getElementById('matrix-bg');
const ctx = canvas.getContext('2d');

function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
resizeCanvas();
window.addEventListener('resize', resizeCanvas);

const chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789ABCDEF';
const fontSize = 14;
let columns = Math.floor(canvas.width / fontSize);
let drops = Array(columns).fill(1);

function drawMatrix() {
    ctx.fillStyle = 'rgba(10, 10, 10, 0.05)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#00ff41';
    ctx.font = `${fontSize}px monospace`;

    for (let i = 0; i < drops.length; i++) {
        const char = chars[Math.floor(Math.random() * chars.length)];
        ctx.fillText(char, i * fontSize, drops[i] * fontSize);

        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
            drops[i] = 0;
        }
        drops[i]++;
    }
}

setInterval(drawMatrix, 50);

window.addEventListener('resize', () => {
    columns = Math.floor(canvas.width / fontSize);
    drops = Array(columns).fill(1);
});

// App logic
let ws = null;
let currentSettings = {};

function updateClock() {
    const now = new Date();
    document.getElementById('footer-time').textContent = now.toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();

        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');
        const version = document.getElementById('version');
        const connections = document.getElementById('connections');

        if (data.running) {
            dot.classList.add('online');
            text.textContent = 'ONLINE';
            text.style.color = '#00ff41';
        } else {
            dot.classList.remove('online');
            text.textContent = 'OFFLINE';
            text.style.color = '#ff0040';
        }

        version.textContent = `v${data.version}`;
        connections.textContent = data.active_connections || 0;

        const s = data.settings;
        document.getElementById('https-status').textContent =
            s.https_proxy_enabled ? `${s.https_proxy_host}:${s.https_proxy_port}` : 'DISABLED';
        document.getElementById('socks-status').textContent =
            s.socks_proxy_enabled ? `${s.socks_proxy_host}:${s.socks_proxy_port}` : 'DISABLED';

        currentSettings = s;
        populateSettings(s);
    } catch (e) {
        console.error('Status fetch failed:', e);
    }
}

function populateSettings(s) {
    document.getElementById('set-tor-host').value = s.tor_socks_host || '';
    document.getElementById('set-tor-port').value = s.tor_socks_port || '';
    document.getElementById('set-https-host').value = s.https_proxy_host || '';
    document.getElementById('set-https-port').value = s.https_proxy_port || '';
    document.getElementById('set-https-enabled').checked = s.https_proxy_enabled !== false;
    document.getElementById('set-socks-host').value = s.socks_proxy_host || '';
    document.getElementById('set-socks-port').value = s.socks_proxy_port || '';
    document.getElementById('set-socks-enabled').checked = s.socks_proxy_enabled !== false;
    document.getElementById('set-buffer-size').value = s.buffer_size || '';
    document.getElementById('set-connect-timeout').value = s.connect_timeout || '';
    document.getElementById('set-read-timeout').value = s.read_timeout || '';
    document.getElementById('set-sanitize').checked = s.sanitize_headers || false;
}

function collectSettings() {
    return {
        tor_socks_host: document.getElementById('set-tor-host').value || undefined,
        tor_socks_port: parseInt(document.getElementById('set-tor-port').value) || undefined,
        https_proxy_host: document.getElementById('set-https-host').value || undefined,
        https_proxy_port: parseInt(document.getElementById('set-https-port').value) || undefined,
        https_proxy_enabled: document.getElementById('set-https-enabled').checked,
        socks_proxy_host: document.getElementById('set-socks-host').value || undefined,
        socks_proxy_port: parseInt(document.getElementById('set-socks-port').value) || undefined,
        socks_proxy_enabled: document.getElementById('set-socks-enabled').checked,
        buffer_size: parseInt(document.getElementById('set-buffer-size').value) || undefined,
        connect_timeout: parseInt(document.getElementById('set-connect-timeout').value) || undefined,
        read_timeout: parseInt(document.getElementById('set-read-timeout').value) || undefined,
        sanitize_headers: document.getElementById('set-sanitize').checked,
    };
}

async function startProxy() {
    const settings = collectSettings();
    try {
        const res = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        const data = await res.json();
        if (data.error) {
            addLog(`[ERROR] ${data.error}`, 'error');
        } else {
            addLog('[SYSTEM] Starting proxy...', 'system');
        }
        setTimeout(fetchStatus, 500);
    } catch (e) {
        addLog(`[ERROR] ${e.message}`, 'error');
    }
}

async function stopProxy() {
    try {
        const res = await fetch('/api/stop', { method: 'POST' });
        const data = await res.json();
        if (data.error) {
            addLog(`[ERROR] ${data.error}`, 'error');
        } else {
            addLog('[SYSTEM] Stopping proxy...', 'system');
        }
        setTimeout(fetchStatus, 500);
    } catch (e) {
        addLog(`[ERROR] ${e.message}`, 'error');
    }
}

async function applySettings() {
    const settings = collectSettings();
    try {
        const res = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        const data = await res.json();
        if (data.error) {
            addLog(`[ERROR] ${data.error}`, 'error');
        } else {
            addLog('[SYSTEM] Settings applied successfully', 'system');
        }
    } catch (e) {
        addLog(`[ERROR] ${e.message}`, 'error');
    }
}

async function shutdownAll() {
    if (!confirm('Shutdown proxy and exit? This will close the server.')) {
        return;
    }
    try {
        addLog('[SYSTEM] Shutting down...', 'system');
        const res = await fetch('/api/shutdown', { method: 'POST' });
        const data = await res.json();
        addLog(`[SYSTEM] ${data.status}`, 'system');

        document.querySelector('.overlay').innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;height:100%;flex-direction:column;">
                <h1 style="color:#ff0040;font-size:28px;letter-spacing:6px;text-shadow:0 0 20px #ff004066;">
                    SYSTEM OFFLINE
                </h1>
                <p style="color:#00ff4188;margin-top:16px;font-size:12px;letter-spacing:2px;">
                    Server has been shut down. Close this tab.
                </p>
            </div>
        `;
    } catch (e) {
        addLog(`[ERROR] ${e.message}`, 'error');
    }
}

function addLog(message, type = '') {
    const container = document.getElementById('log-container');
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.textContent = message;
    container.appendChild(line);
    container.scrollTop = container.scrollHeight;

    while (container.children.length > 500) {
        container.removeChild(container.firstChild);
    }
}

async function fetchLogs() {
    try {
        const res = await fetch('/api/logs?limit=50');
        const logs = await res.json();
        const container = document.getElementById('log-container');
        container.innerHTML = '';
        logs.forEach(log => {
            let type = '';
            if (log.includes('[ERROR]')) type = 'error';
            else if (log.includes('[WARN]')) type = 'warning';
            else if (log.includes('[SYSTEM]')) type = 'system';
            else if (log.includes('[DEBUG]')) type = 'debug';
            addLog(log, type);
        });
    } catch (e) {
        console.error('Logs fetch failed:', e);
    }
}

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/logs`);

    ws.onmessage = (event) => {
        let type = '';
        const msg = event.data;
        if (msg.includes('[ERROR]')) type = 'error';
        else if (msg.includes('[WARN]')) type = 'warning';
        else if (msg.includes('[SYSTEM]')) type = 'system';
        else if (msg.includes('[DEBUG]')) type = 'debug';
        addLog(msg, type);
    };

    ws.onclose = () => {
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        ws.close();
    };
}

// Init
fetchStatus();
fetchLogs();
connectWebSocket();
setInterval(fetchStatus, 2000);
