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

        // Settings modal event listeners
        const settingsBtn = document.getElementById('settings-btn');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => this.showSettingsModal());
        }

        const settingsModalClose = document.getElementById('settings-modal-close');
        if (settingsModalClose) {
            settingsModalClose.addEventListener('click', () => this.closeSettingsModal());
        }

        const settingsModal = document.getElementById('settings-modal');
        if (settingsModal) {
            settingsModal.addEventListener('click', (e) => {
                if (e.target === settingsModal) {
                    this.closeSettingsModal();
                }
            });
        }

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
                    ${this.createAnchorsSection(source.buddhist_anchors)}
                </div>
            `).join('')}
        `;

        return sourcesDiv;
    }

    createAnchorsSection(anchors) {
        if (!anchors || anchors.length === 0) {
            return '';
        }

        return `
            <div class="anchors-section">
                <div class="anchors-header">
                    🏷️ Buddhist Terms
                </div>
                <div class="anchors-list">
                    ${anchors.map(anchor => `
                        <div class="anchor-item" title="${anchor.definition || 'No definition available'}">
                            <span class="anchor-term">${anchor.term}</span>
                            <span class="anchor-category">${anchor.category}</span>
                            <span class="anchor-confidence">${(anchor.confidence * 100).toFixed(0)}%</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
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

    closeSettingsModal() {
        const settingsModal = document.getElementById('settings-modal');
        if (settingsModal) {
            settingsModal.style.display = 'none';
        }
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
                        <li>Local AI processing with Qwen 2.5 14B</li>
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
                message += `📋 Model: ${llmStatus.model || 'qwen2.5:14b'}\n`;
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

    async showSettingsModal() {
        const settingsModal = document.getElementById('settings-modal');
        const settingsContent = document.getElementById('settings-content');

        if (!settingsModal || !settingsContent) {
            console.error('Settings modal elements not found');
            return;
        }

        try {
            // Get current model status
            const response = await axios.get(`${this.backendUrl}/models/status`);
            const status = response.data;

            settingsContent.innerHTML = `
                <div class="settings-content">
                    <form id="settings-form" class="settings-form">
                        <!-- Model Provider Selection -->
                        <div class="setting-group">
                            <h3>🤖 Model Provider</h3>
                            <div class="radio-group">
                                <label class="radio-item">
                                    <input type="radio" name="provider" value="local" ${status.current_provider === 'local' ? 'checked' : ''}>
                                    <span>Local (Qwen 2.5 14B) - Private & Free</span>
                                </label>
                                <label class="radio-item">
                                    <input type="radio" name="provider" value="openai" ${status.current_provider === 'openai' ? 'checked' : ''}>
                                    <span>OpenAI GPT-4 - Requires API Key</span>
                                </label>
                                <label class="radio-item">
                                    <input type="radio" name="provider" value="anthropic" ${status.current_provider === 'anthropic' ? 'checked' : ''}>
                                    <span>Anthropic Claude - Requires API Key</span>
                                </label>
                                <label class="radio-item">
                                    <input type="radio" name="provider" value="google" ${status.current_provider === 'google' ? 'checked' : ''}>
                                    <span>Google Gemini - Requires API Key</span>
                                </label>
                            </div>
                        </div>

                        <!-- API Keys Section -->
                        <div class="setting-group api-keys-section">
                            <h3>🔑 API Keys</h3>
                            <p class="privacy-note">⚠️ API keys are stored locally and never transmitted except to their respective services</p>

                            <div class="api-key-group">
                                <label>OpenAI API Key:</label>
                                <input type="password" id="openai-key" placeholder="sk-..." />
                                <span class="key-status" id="openai-status">${this.getKeyStatus(status.frontier_model, 'openai')}</span>
                            </div>

                            <div class="api-key-group">
                                <label>Anthropic API Key:</label>
                                <input type="password" id="anthropic-key" placeholder="sk-ant-..." />
                                <span class="key-status" id="anthropic-status">${this.getKeyStatus(status.frontier_model, 'anthropic')}</span>
                            </div>

                            <div class="api-key-group">
                                <label>Google AI API Key:</label>
                                <input type="password" id="google-key" placeholder="AIza..." />
                                <span class="key-status" id="google-status">${this.getKeyStatus(status.frontier_model, 'google')}</span>
                            </div>
                        </div>

                        <!-- Privacy & Fallback -->
                        <div class="setting-group">
                            <h3>🔒 Privacy & Fallback</h3>
                            <label class="checkbox-item">
                                <input type="checkbox" id="enable-fallback" ${status.fallback_enabled ? 'checked' : ''}>
                                <span>Enable fallback to local model if API fails</span>
                            </label>
                            <label class="checkbox-item">
                                <input type="checkbox" id="allow-transmission" ${status.privacy_summary?.data_leaves_system ? 'checked' : ''}>
                                <span>Allow data transmission to API providers (required for cloud models)</span>
                            </label>
                            <div class="privacy-info">
                                <p><strong>Current Privacy Level:</strong> ${status.privacy_summary?.privacy_level || 'Unknown'}</p>
                                <p><strong>Local Processing:</strong> ${status.privacy_summary?.local_processing ? 'Yes' : 'No'}</p>
                            </div>
                        </div>

                        <!-- Model Parameters -->
                        <div class="setting-group">
                            <h3>⚙️ Model Parameters</h3>
                            <div class="parameter-group">
                                <label>Response Temperature: <span id="temp-value">0.3</span></label>
                                <input type="range" id="temperature" min="0" max="1" step="0.1" value="0.3">
                                <small>Lower = more focused, Higher = more creative</small>
                            </div>
                        </div>

                        <!-- Usage Stats (if available) -->
                        ${this.renderUsageStats(status.frontier_model)}

                        <div class="settings-actions">
                            <button type="button" id="test-connection" class="action-btn">Test Connection</button>
                            <button type="button" id="save-settings" class="action-btn primary">Save Settings</button>
                            <button type="button" id="cancel-settings" class="action-btn">Cancel</button>
                        </div>
                    </form>
                </div>
            `;

            // Add event listeners
            this.setupSettingsEventListeners();

        } catch (error) {
            console.error('Error loading settings:', error);
            settingsContent.innerHTML = `
                <div class="settings-content">
                    <p>Error loading settings. Please make sure the backend is running.</p>
                    <button onclick="app.closeSettingsModal()">Close</button>
                </div>
            `;
        }

        settingsModal.style.display = 'block';
    }

    getKeyStatus(frontierModel, provider) {
        if (!frontierModel || frontierModel.status === 'unavailable') {
            return '<span class="status-inactive">Not configured</span>';
        }

        if (frontierModel.status === 'healthy') {
            return '<span class="status-active">✓ Connected</span>';
        }

        return '<span class="status-error">⚠ Error</span>';
    }

    renderUsageStats(frontierModel) {
        if (!frontierModel || !frontierModel.usage_summary) {
            return '';
        }

        const stats = frontierModel.usage_summary;
        return `
            <div class="setting-group">
                <h3>📊 Usage Statistics</h3>
                <div class="usage-stats">
                    <div class="stat-item">
                        <strong>Requests Today:</strong> ${stats.requests || 0}
                    </div>
                    <div class="stat-item">
                        <strong>Tokens Used:</strong> ${stats.tokens_used || 0}
                    </div>
                    <div class="stat-item">
                        <strong>Estimated Cost:</strong> $${(stats.estimated_cost || 0).toFixed(4)}
                    </div>
                    ${stats.approaching_limit ? '<div class="warning">⚠️ Approaching daily limit</div>' : ''}
                </div>
            </div>
        `;
    }

    setupSettingsEventListeners() {
        // Temperature slider
        const tempSlider = document.getElementById('temperature');
        const tempValue = document.getElementById('temp-value');
        if (tempSlider && tempValue) {
            tempSlider.addEventListener('input', (e) => {
                tempValue.textContent = e.target.value;
            });
        }

        // Enable paste functionality for API key inputs
        const apiKeyInputs = ['openai-key', 'anthropic-key', 'google-key'];
        apiKeyInputs.forEach(inputId => {
            const input = document.getElementById(inputId);
            if (input) {
                // Make input focusable and selectable
                input.setAttribute('contenteditable', 'true');
                input.setAttribute('spellcheck', 'false');

                // Enable right-click context menu
                input.addEventListener('contextmenu', (e) => {
                    e.stopPropagation();
                    // Allow right-click menu
                });

                // Handle keyboard shortcuts
                input.addEventListener('keydown', async (e) => {
                    if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
                        e.preventDefault();
                        e.stopPropagation();

                        try {
                            // Use clipboard API if available
                            if (navigator.clipboard && navigator.clipboard.readText) {
                                const clipboardText = await navigator.clipboard.readText();
                                input.value = clipboardText.trim();
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                            } else {
                                // Fallback: try document.execCommand
                                document.execCommand('paste');
                            }
                        } catch (error) {
                            console.log('Paste using clipboard API failed, trying document.execCommand');
                            try {
                                document.execCommand('paste');
                            } catch (fallbackError) {
                                console.error('All paste methods failed:', fallbackError);
                                // Show user-friendly message
                                alert('Paste failed. Please try right-clicking and selecting paste, or type the API key manually.');
                            }
                        }
                    }
                });

                // Enable focus and selection
                input.addEventListener('focus', () => {
                    input.select();
                });

                // Handle paste events
                input.addEventListener('paste', (e) => {
                    e.stopPropagation();
                    // Allow paste event to proceed normally
                });
            }
        });

        // Test connection button
        const testBtn = document.getElementById('test-connection');
        if (testBtn) {
            testBtn.addEventListener('click', () => this.testConnection());
        }

        // Save settings button
        const saveBtn = document.getElementById('save-settings');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveSettings());
        }

        // Cancel button
        const cancelBtn = document.getElementById('cancel-settings');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeSettingsModal());
        }
    }

    async testConnection() {
        const testBtn = document.getElementById('test-connection');
        const originalText = testBtn.textContent;

        try {
            testBtn.textContent = 'Testing...';
            testBtn.disabled = true;

            console.log('Testing API connections...');

            // First collect the API keys from the form
            const openaiKey = document.getElementById('openai-key')?.value?.trim();
            const anthropicKey = document.getElementById('anthropic-key')?.value?.trim();
            const googleKey = document.getElementById('google-key')?.value?.trim();

            console.log('Keys available:', {
                openai: !!openaiKey,
                anthropic: !!anthropicKey,
                google: !!googleKey
            });

            // Send test request with the keys
            const response = await axios.post(`${this.backendUrl}/models/validate`, {
                openai_api_key: openaiKey,
                anthropic_api_key: anthropicKey,
                google_api_key: googleKey
            });

            const results = response.data;
            console.log('Test results:', results);

            let message = 'API Connection Test Results:\n\n';
            let hasAnyKeys = false;

            // Show base key validation
            if (results.openai !== undefined) {
                hasAnyKeys = true;
                const status = results.openai_connection || (results.openai ? 'No test performed' : 'No key provided');
                message += `OpenAI: ${this.formatConnectionStatus(results.openai, status)}\n`;
            }

            if (results.anthropic !== undefined) {
                hasAnyKeys = true;
                const status = results.anthropic_connection || (results.anthropic ? 'No test performed' : 'No key provided');
                message += `Anthropic: ${this.formatConnectionStatus(results.anthropic, status)}\n`;
            }

            if (results.google !== undefined) {
                hasAnyKeys = true;
                const status = results.google_connection || (results.google ? 'No test performed' : 'No key provided');
                message += `Google AI: ${this.formatConnectionStatus(results.google, status)}\n`;
            }

            if (!hasAnyKeys) {
                message = 'No API keys provided for testing.\n\nPlease enter API keys in the form above and try again.';
            }

            alert(message);

        } catch (error) {
            console.error('Connection test failed:', error);
            let errorMsg = 'Connection test failed.\n\n';

            if (error.response) {
                errorMsg += `Server error: ${error.response.status} - ${error.response.data?.detail || error.response.statusText}`;
            } else if (error.request) {
                errorMsg += 'No response from server. Please check if the backend is running.';
            } else {
                errorMsg += `Error: ${error.message}`;
            }

            alert(errorMsg);
        } finally {
            testBtn.textContent = originalText;
            testBtn.disabled = false;
        }
    }

    formatConnectionStatus(hasKey, connectionResult) {
        if (!hasKey) {
            return '⚪ No API key provided';
        }

        if (connectionResult === 'valid') {
            return '✅ Connected successfully';
        } else if (connectionResult && connectionResult.startsWith('error:')) {
            return `❌ Connection failed: ${connectionResult.replace('error: ', '')}`;
        } else {
            return '🟡 API key provided (not tested)';
        }
    }

    async saveSettings() {
        const saveBtn = document.getElementById('save-settings');
        const originalText = saveBtn.textContent;

        try {
            saveBtn.textContent = 'Saving...';
            saveBtn.disabled = true;

            // Collect form data
            const provider = document.querySelector('input[name="provider"]:checked')?.value;
            const openaiKey = document.getElementById('openai-key')?.value;
            const anthropicKey = document.getElementById('anthropic-key')?.value;
            const googleKey = document.getElementById('google-key')?.value;
            const enableFallback = document.getElementById('enable-fallback')?.checked;
            const temperature = parseFloat(document.getElementById('temperature')?.value || 0.3);

            // Prepare config data
            const configData = {
                provider: provider,
                enable_fallback: enableFallback,
                temperature: temperature
            };

            // Add API keys if provided
            if (openaiKey && openaiKey.trim()) {
                configData.openai_api_key = openaiKey.trim();
            }
            if (anthropicKey && anthropicKey.trim()) {
                configData.anthropic_api_key = anthropicKey.trim();
            }
            if (googleKey && googleKey.trim()) {
                configData.google_api_key = googleKey.trim();
            }

            // Save configuration
            const response = await axios.post(`${this.backendUrl}/models/config`, configData);

            this.showToast('Settings saved successfully!', 'success');

            // Update UI to reflect new provider
            await this.updateModelStatus();

            // Close modal after short delay
            setTimeout(() => {
                this.closeModal();
            }, 1000);

        } catch (error) {
            console.error('Save settings failed:', error);
            this.showToast('Failed to save settings. Please check your configuration.', 'error');
        } finally {
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }
    }

    async updateModelStatus() {
        try {
            const response = await axios.get(`${this.backendUrl}/models/status`);
            const status = response.data;

            // Update the model info display
            const modelInfo = document.getElementById('model-info');
            if (modelInfo) {
                const displayName = this.getProviderDisplayName(status.current_provider);
                modelInfo.textContent = `Powered by ${displayName}`;
            }

            // Update status if available
            await this.checkBackendStatus();

        } catch (error) {
            console.error('Failed to update model status:', error);
        }
    }

    getProviderDisplayName(provider) {
        const providers = {
            'local': 'Qwen 2.5 14B',
            'openai': 'OpenAI GPT-4',
            'anthropic': 'Anthropic Claude',
            'google': 'Google Gemini'
        };
        return providers[provider] || 'Unknown Model';
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