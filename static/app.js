// PDF Tutor - Frontend JavaScript

let currentKB = null;
let chatHistory = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadKBs();
    setupUpload();
    setupChatInput();
});

// Upload functionality
function setupUpload() {
    const uploadBox = document.getElementById('uploadBox');
    const pdfInput = document.getElementById('pdfInput');
    
    uploadBox.addEventListener('click', () => pdfInput.click());
    
    uploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadBox.style.background = '#f0f4ff';
    });
    
    uploadBox.addEventListener('dragleave', () => {
        uploadBox.style.background = '';
    });
    
    uploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadBox.style.background = '';
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].name.endsWith('.pdf')) {
            uploadFile(files[0]);
        }
    });
    
    pdfInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });
}

async function uploadFile(file) {
    const status = document.getElementById('uploadStatus');
    status.textContent = 'Uploading...';
    status.className = '';
    status.style.display = 'block';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (data.success) {
            status.textContent = `✅ ${data.message}`;
            status.className = 'success';
            loadKBs();
        } else {
            status.textContent = `❌ Error: ${data.error}`;
            status.className = 'error';
        }
    } catch (err) {
        status.textContent = `❌ Error: ${err.message}`;
        status.className = 'error';
    }
}

// Load knowledge bases
async function loadKBs() {
    const kbList = document.getElementById('kbList');
    const quizKB = document.getElementById('quizKB');
    
    kbList.innerHTML = '<p class="loading">Loading...</p>';
    
    try {
        const res = await fetch('/api/kb/list');
        const data = await res.json();
        
        // Update KB list display
        if (data.kbs && data.kbs.length > 0) {
            kbList.innerHTML = data.kbs.map(kb => `
                <div class="kb-item">
                    <span class="kb-name">📚 ${kb}</span>
                    <div class="kb-actions">
                        <button onclick="openChat('${kb}')">Chat</button>
                        <button onclick="deleteKB('${kb}')">🗑️</button>
                    </div>
                </div>
            `).join('');
            
            // Update quiz dropdown
            quizKB.innerHTML = '<option value="">Pilih materi...</option>' +
                data.kbs.map(kb => `<option value="${kb}">${kb}</option>`).join('');
        } else {
            kbList.innerHTML = '<p class="empty">Belum ada materi. Upload PDF dulu.</p>';
            quizKB.innerHTML = '<option value="">Pilih materi...</option>';
        }
    } catch (err) {
        kbList.innerHTML = `<p class="error">Error: ${err.message}</p>`;
    }
}

// Chat functionality
function openChat(kbName) {
    currentKB = kbName;
    document.getElementById('activeKB').textContent = kbName;
    document.getElementById('chatSection').style.display = 'block';
    document.getElementById('chatMessages').innerHTML = '';
    chatHistory = [];
    
    // Add welcome message
    addMessage('bot', `Halo! Aku siap membantu belajar dari materi "${kbName}". Tanya apa saja!`);
    
    // Scroll to chat
    document.getElementById('chatSection').scrollIntoView({ behavior: 'smooth' });
}

function closeChat() {
    document.getElementById('chatSection').style.display = 'none';
    currentKB = null;
}

function addMessage(sender, text) {
    const messages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    
    const senderLabel = sender === 'user' ? 'Kamu' : 'Tutor';
    div.innerHTML = `
        <div class="sender">${senderLabel}</div>
        <div class="text">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
    `;
    
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

function setupChatInput() {
    const textarea = document.getElementById('messageInput');
    
    textarea.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !currentKB) return;
    
    // Add user message
    addMessage('user', message);
    input.value = '';
    
    // Get capability
    const capability = document.getElementById('capabilitySelect').value;
    
    // Show loading
    const messages = document.getElementById('chatMessages');
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot loading';
    loadingDiv.innerHTML = '<div class="text">🤔 Sedang berpikir...</div>';
    messages.appendChild(loadingDiv);
    messages.scrollTop = messages.scrollHeight;
    
    try {
        const formData = new FormData();
        formData.append('message', message);
        formData.append('kb_name', currentKB);
        formData.append('capability', capability);
        
        const res = await fetch('/api/chat', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        // Remove loading
        loadingDiv.remove();
        
        if (data.success) {
            addMessage('bot', data.response);
        } else {
            addMessage('bot', `Error: ${data.error}`);
        }
    } catch (err) {
        loadingDiv.remove();
        addMessage('bot', `Error: ${err.message}`);
    }
}

// Quiz functionality
async function generateQuiz() {
    const topic = document.getElementById('quizTopic').value.trim();
    const kbName = document.getElementById('quizKB').value;
    const count = document.getElementById('quizCount').value;
    const resultDiv = document.getElementById('quizResult');
    
    if (!topic || !kbName) {
        resultDiv.innerHTML = '<p class="error">Isi topik dan pilih materi dulu.</p>';
        return;
    }
    
    resultDiv.innerHTML = '<p class="loading">⏳ Sedang generate quiz...</p>';
    
    try {
        const formData = new FormData();
        formData.append('topic', topic);
        formData.append('kb_name', kbName);
        formData.append('num_questions', count);
        
        const res = await fetch('/api/quiz', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (data.success) {
            resultDiv.innerHTML = `<h3>📝 Quiz: ${topic}</h3><pre>${data.quiz}</pre>`;
        } else {
            resultDiv.innerHTML = `<p class="error">Error: ${data.quiz}</p>`;
        }
    } catch (err) {
        resultDiv.innerHTML = `<p class="error">Error: ${err.message}</p>`;
    }
}

// Delete knowledge base
async function deleteKB(kbName) {
    if (!confirm(`Hapus materi "${kbName}"?`)) return;
    
    try {
        const res = await fetch(`/api/kb/${kbName}`, { method: 'DELETE' });
        const data = await res.json();
        
        if (data.success) {
            loadKBs();
            if (currentKB === kbName) closeChat();
        } else {
            alert(`Error: ${data.message}`);
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

// Helper
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
