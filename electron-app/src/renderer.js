const { ipcRenderer } = require('electron');
const axios = require('axios');

class BuddhistRAGApp {
    constructor() {
        this.backendUrl = 'http://127.0.0.1:8000';
        this.backendReady = false;
        this.documents = [];
        this.queryCount = 0;

        this.initializeElements();
        this.attachEventListeners();
        this.checkBackendStatus();
        this.setupAutoRefresh();
    }

    initializeElements() {
        this.elements = {
            statusDot: document.getElementById('status-dot'),
            statusText: document.getElementById('status-text'),
            uploadArea: document.getElementById('upload-area'),
            uploadBtn: document.getElementById('upload-btn'),
            documentList: document.getElementById('document-list'),
            documentsLoading: document.getElementById('documents-loading'),
            chatMessages: document.getElementById('chat-messages'),
            chatInput: document.getElementById('chat-input'),
            sendButton: document.getElementById('send-button'),
            totalDocuments: document.getElementById('total-documents'),
            totalChunks: document.getElementById('total-chunks'),
            totalQueries: document.getElementById('total-queries'),
            loadingOverlay: document.getElementById('loading-overlay'),
            loadingTitle: document.getElementById('loading-title'),
            loadingMessage: document.getElementById('loading-message'),
            documentModal: document.getElementById('document-modal'),
            modalClose: document.getElementById('modal-close'),
            modalTitle: document.getElementById('modal-title'),
            modalBody: document.getElementById('modal-body'),
            toastContainer: document.getElementById('toast-container'),
            gettingStarted: document.getElementById('getting-started')
        };
    }

    attachEventListeners() {
        this.elements.uploadBtn.addEventListener('click', () => this.uploadPDF());
        this.elements.uploadArea.addEventListener('click', () => this.uploadPDF());
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        this.elements.chatInput.addEventListener('keydown', (e) => this.handleInputKeydown(e));
        this.elements.chatInput.addEventListener('input', () => this.handleInputResize());
        this.elements.modalClose.addEventListener('click', () => this.closeModal());
        this.elements.documentModal.addEventListener('click', (e) => {
            if (e.target === this.elements.documentModal) {
                this.closeModal();
            }
        });

        this.setupDragAndDrop();
        this.setupExampleQuestions();
        this.setupMenuListeners();
    }

    setupDragAndDrop() {
        const uploadArea = this.elements.uploadArea;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('drag-over');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('drag-over');
            }, false);
        });

        uploadArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type === 'application/pdf') {
                this.processPDFFile(files[0]);
            } else {
                this.showToast('Please drop a PDF file', 'error');
            }
        }, false);
    }

    setupExampleQuestions() {
        document.querySelectorAll('.example-question').forEach(button => {
            button.addEventListener('click', () => {
                const question = button.getAttribute('data-question');
                this.elements.chatInput.value = question;
                this.sendMessage();
            });
        });
    }

    setupMenuListeners() {
        ipcRenderer.on('menu-upload-pdf', () => this.uploadPDF());
        ipcRenderer.on('menu-settings', () => this.showSettingsModal());
        ipcRenderer.on('menu-about', () => this.showAboutModal());
        ipcRenderer.on('menu-check-ollama', () => this.checkOllamaStatus());
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    async checkBackendStatus() {
        try {
            const status = await ipcRenderer.invoke('check-backend-status');
            this.updateStatus(status.ready, status.health);

            if (status.ready) {
                this.backendReady = true;
                this.elements.chatInput.disabled = false;
                this.elements.sendButton.disabled = false;
                await this.loadDocuments();
                await this.updateStatistics();
                this.hideGettingStarted();
            }
        } catch (error) {
            console.error('Backend status check failed:', error);
            this.updateStatus(false, { error: error.message });
        }
    }

    updateStatus(ready, health) {
        const statusDot = this.elements.statusDot;
        const statusText = this.elements.statusText;

        if (ready && health && health.status === 'healthy') {
            statusDot.className = 'status-dot ready';
            statusText.textContent = 'Ready';
        } else if (health && health.status === 'degraded') {
            statusDot.className = 'status-dot error';
            statusText.textContent = 'Degraded - Some services unavailable';
        } else {
            statusDot.className = 'status-dot error';
            statusText.textContent = health?.error || 'Backend not ready';
        }
    }

    async uploadPDF() {
        if (!this.backendReady) {
            this.showToast('Backend not ready yet', 'warning');
            return;
        }

        try {
            const filePath = await ipcRenderer.invoke('upload-pdf');
            if (filePath) {
                const file = await this.createFileFromPath(filePath);
                await this.processPDFFile(file);
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showToast('Failed to upload PDF', 'error');
        }
    }

    async createFileFromPath(filePath) {
        const fs = require('fs');
        const path = require('path');

        const buffer = fs.readFileSync(filePath);
        const fileName = path.basename(filePath);

        const blob = new Blob([buffer], { type: 'application/pdf' });
        const file = new File([blob], fileName, { type: 'application/pdf' });

        return file;
    }

    async processPDFFile(file) {
        this.showLoading('Processing PDF...', 'This may take a few moments depending on the document size.');

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await axios.post(`${this.backendUrl}/upload_pdf`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                timeout: 300000 // 5 minute timeout
            });

            this.hideLoading();
            this.showToast(`Successfully processed ${file.name}`, 'success');

            await this.loadDocuments();
            await this.updateStatistics();
            this.hideGettingStarted();

        } catch (error) {
            this.hideLoading();
            console.error('PDF processing error:', error);

            const errorMessage = error.response?.data?.detail || error.message || 'Failed to process PDF';
            this.showToast(`Error: ${errorMessage}`, 'error');
        }
    }

    async loadDocuments() {
        if (!this.backendReady) return;

        try {
            const response = await axios.get(`${this.backendUrl}/documents`);
            this.documents = response.data.documents || [];
            this.renderDocumentList();
        } catch (error) {
            console.error('Failed to load documents:', error);
            this.showToast('Failed to load documents', 'error');
        }
    }

    renderDocumentList() {
        const container = this.elements.documentList;

        if (this.documents.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">No documents uploaded yet</p>';
            return;
        }

        container.innerHTML = this.documents.map(doc => `
            <div class="document-item" data-filename="${doc.filename}">
                <div class="document-name">${doc.filename}</div>
                <div class="document-meta">
                    <span>${doc.chunks} chunks</span>
                    <span>${doc.pages} pages</span>
                </div>
                <div class="document-actions">
                    <button class="action-btn" onclick="app.viewDocument('${doc.filename}')">View</button>
                    <button class="action-btn" onclick="app.summarizeDocument('${doc.filename}')">Summary</button>
                    <button class="action-btn danger" onclick="app.deleteDocument('${doc.filename}')">Delete</button>
                </div>
            </div>
        `).join('');
    }

    async updateStatistics() {
        if (!this.backendReady) return;

        try {
            const response = await axios.get(`${this.backendUrl}/health`);
            const health = response.data;

            // Update statistics from collection stats
            if (health.services?.vector_store?.document_count !== undefined) {
                this.elements.totalDocuments.textContent = this.documents.length || 0;
                this.elements.totalChunks.textContent = health.services.vector_store.document_count || 0;
            }

            this.elements.totalQueries.textContent = this.queryCount;

        } catch (error) {
            console.error('Failed to update statistics:', error);
        }
    }

    setupAutoRefresh() {
        setInterval(() => {
            if (this.backendReady) {
                this.updateStatistics();
            } else {
                this.checkBackendStatus();
            }
        }, 10000); // Check every 10 seconds
    }

    async sendMessage() {
        const input = this.elements.chatInput;
        const question = input.value.trim();

        if (!question || !this.backendReady) return;

        this.queryCount++;
        input.value = '';
        this.handleInputResize();

        this.addMessage('user', question);

        const assistantMessage = this.addMessage('assistant', '');
        this.showTypingIndicator(assistantMessage);

        try {
            const response = await axios.post(`${this.backendUrl}/query`, {
                question: question,
                max_results: 5
            });

            this.hideTypingIndicator(assistantMessage);
            this.updateAssistantMessage(assistantMessage, response.data.answer, response.data.sources);

            await this.updateStatistics();

        } catch (error) {
            this.hideTypingIndicator(assistantMessage);
            console.error('Query error:', error);

            const errorMessage = error.response?.data?.detail || 'I apologize, but I encountered an error processing your question. Please try again.';
            this.updateAssistantMessage(assistantMessage, errorMessage, []);
        }
    }

    addMessage(sender, content) {
        const messagesContainer = this.elements.chatMessages;
        const messageTime = new Date().toLocaleTimeString();

        // Hide welcome message if it exists
        const welcomeMessage = messagesContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        const avatar = sender === 'user' ? '👤' : '🙏';
        const authorName = sender === 'user' ? 'You' : 'Buddhist RAG';

        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="message-avatar">${avatar}</div>
                <span class="message-author">${authorName}</span>
                <span class="message-time">${messageTime}</span>
            </div>
            <div class="message-content">
                <div class="message-text">${this.formatMessageContent(content)}</div>
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return messageDiv;
    }

    showTypingIndicator(messageElement) {
        const messageText = messageElement.querySelector('.message-text');
        messageText.innerHTML = '<div class="typing-indicator"><div class="spinner"></div> Searching through Buddhist texts...</div>';
    }

    hideTypingIndicator(messageElement) {
        const messageText = messageElement.querySelector('.message-text');
        messageText.innerHTML = '';
    }

    updateAssistantMessage(messageElement, answer, sources) {
        const messageText = messageElement.querySelector('.message-text');
        messageText.innerHTML = this.formatMessageContent(answer);

        if (sources && sources.length > 0) {
            const sourcesSection = this.createSourcesSection(sources);
            messageElement.querySelector('.message-content').appendChild(sourcesSection);
        }
    }

    createSourcesSection(sources) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'sources-section';

        sourcesDiv.innerHTML = `
            <div class="sources-header">
                📖 Sources
            </div>
            ${sources.map((source, index) => `
                <div class="source-item">
                    <div class="source-header">
                        <span class="source-citation">${source.citation}</span>
                        <span class="similarity-score">${(source.similarity_score * 100).toFixed(0)}% match</span>
                    </div>
                    <div class="source-content">
                        "${source.content.substring(0, 200)}${source.content.length > 200 ? '...' : ''}"
                    </div>
                </div>
            `).join('')}
        `;

        return sourcesDiv;
    }

    formatMessageContent(content) {
        if (!content) return '';

        // Basic markdown-like formatting
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>')
            .replace(/\[Source: (.*?)\]/g, '<span class="inline-citation">[$1]</span>');
    }

    handleInputKeydown(e) {
        if (e.key === 'Enter') {
            if (e.shiftKey) {
                // Allow new line
                return;
            } else {
                e.preventDefault();
                this.sendMessage();
            }
        }
    }

    handleInputResize() {
        const input = this.elements.chatInput;
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    }

    async viewDocument(filename) {
        this.showLoading('Loading document details...', '');

        try {
            // Get document chunks for preview
            const response = await axios.get(`${this.backendUrl}/documents`);
            const doc = response.data.documents.find(d => d.filename === filename);

            this.hideLoading();

            if (doc) {
                this.showDocumentModal(filename, doc);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error loading document:', error);
            this.showToast('Failed to load document details', 'error');
        }
    }

    async summarizeDocument(filename) {
        this.showLoading('Generating summary...', 'This may take a moment.');

        try {
            // This would require adding a summary endpoint to the backend
            this.hideLoading();
            this.showToast('Summary feature coming soon!', 'info');
        } catch (error) {
            this.hideLoading();
            this.showToast('Failed to generate summary', 'error');
        }
    }

    async deleteDocument(filename) {
        if (!confirm(`Are you sure you want to delete "${filename}"? This cannot be undone.`)) {
            return;
        }

        this.showLoading('Deleting document...', '');

        try {
            await axios.delete(`${this.backendUrl}/documents/${encodeURIComponent(filename)}`);

            this.hideLoading();
            this.showToast(`Deleted ${filename}`, 'success');

            await this.loadDocuments();
            await this.updateStatistics();

        } catch (error) {
            this.hideLoading();
            console.error('Error deleting document:', error);
            this.showToast('Failed to delete document', 'error');
        }
    }

    showDocumentModal(filename, doc) {
        this.elements.modalTitle.textContent = filename;
        this.elements.modalBody.innerHTML = `
            <div class="document-details">
                <div class="detail-row">
                    <strong>Pages:</strong> ${doc.pages}
                </div>
                <div class="detail-row">
                    <strong>Text Chunks:</strong> ${doc.chunks}
                </div>
                <div class="detail-row">
                    <strong>Added:</strong> ${doc.added_date ? new Date(doc.added_date).toLocaleDateString() : 'Unknown'}
                </div>
                ${doc.detected_language ? `
                    <div class="detail-row">
                        <strong>Detected Language:</strong> ${doc.detected_language}
                    </div>
                ` : ''}
                ${doc.estimated_tradition ? `
                    <div class="detail-row">
                        <strong>Buddhist Tradition:</strong> ${doc.estimated_tradition}
                    </div>
                ` : ''}
            </div>
        `;

        this.elements.documentModal.style.display = 'block';
    }

    closeModal() {
        this.elements.documentModal.style.display = 'none';
    }

    showLoading(title, message) {
        this.elements.loadingTitle.textContent = title;
        this.elements.loadingMessage.textContent = message;
        this.elements.loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        this.elements.loadingOverlay.style.display = 'none';
    }

    hideGettingStarted() {
        if (this.documents.length > 0 && this.elements.gettingStarted) {
            this.elements.gettingStarted.style.display = 'none';
        }
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        this.elements.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 5000);
    }

    async showAboutModal() {
        const appInfo = await ipcRenderer.invoke('get-app-info');

        this.elements.modalTitle.textContent = 'About Buddhist RAG';
        this.elements.modalBody.innerHTML = `
            <div class="about-content">
                <div class="app-logo" style="text-align: center; font-size: 48px; margin-bottom: 20px;">🙏</div>
                <h3 style="text-align: center; margin-bottom: 20px;">Buddhist RAG v${appInfo.version}</h3>

                <p style="margin-bottom: 16px;">
                    A respectful and intelligent way to explore Buddhist texts through semantic search and AI-powered insights.
                </p>

                <div class="feature-list" style="margin: 20px 0;">
                    <h4>Features:</h4>
                    <ul style="margin-left: 20px;">
                        <li>Local AI processing with Qwen 2.5 7B</li>
                        <li>Buddhist text-aware chunking</li>
                        <li>Semantic search through teachings</li>
                        <li>Source citations and references</li>
                        <li>Completely offline operation</li>
                    </ul>
                </div>

                <div class="tech-details" style="font-size: 12px; color: #666; margin-top: 20px;">
                    <strong>Technical Details:</strong><br>
                    Electron ${appInfo.electron} • Node.js ${appInfo.node} • ${appInfo.platform}
                </div>
            </div>
        `;

        this.elements.documentModal.style.display = 'block';
    }

    async checkOllamaStatus() {
        this.showLoading('Checking Ollama status...', '');

        try {
            const response = await axios.get(`${this.backendUrl}/health`);
            this.hideLoading();

            const llmStatus = response.data.services?.llm_client;

            let message = 'Ollama Status:\n\n';
            if (llmStatus?.status === 'healthy') {
                message += '✅ Ollama is running and healthy\n';
                message += `📋 Model: ${llmStatus.model || 'qwen2.5:7b'}\n`;
                message += `🔧 Context Length: ${llmStatus.context_length || 'Unknown'}`;
            } else {
                message += '❌ Ollama appears to be offline or unavailable\n';
                message += `💡 Make sure Ollama is installed and running\n`;
                message += `💡 Try: ollama serve`;
            }

            await ipcRenderer.invoke('show-info-dialog', 'Ollama Status', message);

        } catch (error) {
            this.hideLoading();
            await ipcRenderer.invoke('show-error-dialog', 'Connection Error',
                'Could not connect to backend service to check Ollama status.');
        }
    }

    showSettingsModal() {
        this.elements.modalTitle.textContent = 'Settings';
        this.elements.modalBody.innerHTML = `
            <div class="settings-content">
                <p><em>Settings panel coming soon!</em></p>
                <p>Future settings will include:</p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>Model selection</li>
                    <li>Response length preferences</li>
                    <li>Search result count</li>
                    <li>Citation formatting options</li>
                </ul>
            </div>
        `;

        this.elements.documentModal.style.display = 'block';
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new BuddhistRAGApp();
});

// Handle window close confirmation
window.addEventListener('beforeunload', (e) => {
    // Add any cleanup here if needed
});