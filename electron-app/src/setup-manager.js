const { dialog, shell } = require('electron');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const axios = require('axios');

class SetupManager {
    constructor() {
        this.setupSteps = {
            ollama: false,
            model: false,
            pythonDeps: false
        };
        this.modelName = 'qwen2.5:14b';
    }

    async checkSystemRequirements() {
        const requirements = {
            ollama: await this.checkOllama(),
            python: await this.checkPython(),
            nodejs: await this.checkNodejs(),
            diskSpace: await this.checkDiskSpace(),
            memory: await this.checkMemory()
        };

        return requirements;
    }

    async checkOllama() {
        try {
            const response = await axios.get('http://localhost:11434/api/version', { timeout: 3000 });
            return { available: true, running: true, version: response.data.version };
        } catch (error) {
            // Check if Ollama is installed but not running
            return new Promise((resolve) => {
                exec('ollama --version', (error, stdout) => {
                    if (error) {
                        resolve({ available: false, running: false });
                    } else {
                        resolve({ available: true, running: false, version: stdout.trim() });
                    }
                });
            });
        }
    }

    async checkPython() {
        return new Promise((resolve) => {
            exec('python --version', (error, stdout) => {
                if (error) {
                    exec('python3 --version', (error3, stdout3) => {
                        if (error3) {
                            resolve({ available: false });
                        } else {
                            resolve({ available: true, version: stdout3.trim(), command: 'python3' });
                        }
                    });
                } else {
                    resolve({ available: true, version: stdout.trim(), command: 'python' });
                }
            });
        });
    }

    async checkNodejs() {
        return new Promise((resolve) => {
            exec('node --version', (error, stdout) => {
                if (error) {
                    resolve({ available: false });
                } else {
                    resolve({ available: true, version: stdout.trim() });
                }
            });
        });
    }

    async checkDiskSpace() {
        // Simplified disk space check - would need platform-specific implementation
        return { available: true, freeSpace: 'Unknown' };
    }

    async checkMemory() {
        const totalMemory = require('os').totalmem();
        const freeMemory = require('os').freemem();

        return {
            total: Math.round(totalMemory / (1024 * 1024 * 1024)),
            free: Math.round(freeMemory / (1024 * 1024 * 1024)),
            sufficient: totalMemory >= 8 * 1024 * 1024 * 1024 // 8GB minimum
        };
    }

    async runSetupWizard(mainWindow) {
        const requirements = await this.checkSystemRequirements();

        // Show setup dialog
        const setupNeeded = !requirements.ollama.available ||
                           !requirements.ollama.running ||
                           !requirements.python.available;

        if (setupNeeded) {
            const result = await dialog.showMessageBox(mainWindow, {
                type: 'info',
                title: 'Buddhist RAG Setup',
                message: 'Welcome to Buddhist RAG! 🙏',
                detail: this.generateSetupMessage(requirements),
                buttons: ['Auto Setup', 'Manual Setup', 'Cancel'],
                defaultId: 0
            });

            switch (result.response) {
                case 0: // Auto Setup
                    return await this.runAutoSetup(mainWindow, requirements);
                case 1: // Manual Setup
                    return await this.showManualInstructions(mainWindow);
                case 2: // Cancel
                    return false;
            }
        }

        return true; // All requirements met
    }

    generateSetupMessage(requirements) {
        let message = 'Setup required for the following components:\n\n';

        if (!requirements.ollama.available) {
            message += '❌ Ollama (AI model server) - Not installed\n';
        } else if (!requirements.ollama.running) {
            message += '⚠️  Ollama - Installed but not running\n';
        } else {
            message += '✅ Ollama - Ready\n';
        }

        if (!requirements.python.available) {
            message += '❌ Python - Not found\n';
        } else {
            message += '✅ Python - Ready\n';
        }

        message += `\nMemory: ${requirements.memory.total}GB ${requirements.memory.sufficient ? '✅' : '❌'}\n`;

        if (!requirements.memory.sufficient) {
            message += '\n⚠️  Warning: 8GB+ RAM recommended for optimal performance';
        }

        return message;
    }

    async runAutoSetup(mainWindow, requirements) {
        const progressDialog = this.createProgressDialog(mainWindow);

        try {
            // Step 1: Install Ollama if needed
            if (!requirements.ollama.available) {
                progressDialog.update('Installing Ollama...', 25);
                await this.installOllama();
                progressDialog.update('Ollama installed ✅', 30);
            }

            // Step 2: Start Ollama if needed
            if (!requirements.ollama.running) {
                progressDialog.update('Starting Ollama service...', 40);
                await this.startOllama();
                progressDialog.update('Ollama started ✅', 50);
            }

            // Step 3: Download Qwen model
            progressDialog.update('Downloading AI model (this may take several minutes)...', 60);
            await this.downloadModel(progressDialog);
            progressDialog.update('AI model ready ✅', 80);

            // Step 4: Install Python dependencies
            progressDialog.update('Installing Python dependencies...', 85);
            await this.installPythonDependencies();
            progressDialog.update('Setup complete! ✅', 100);

            progressDialog.close();

            await dialog.showMessageBox(mainWindow, {
                type: 'info',
                title: 'Setup Complete!',
                message: 'Buddhist RAG is now ready to use! 🎉',
                detail: 'You can now upload Buddhist PDF texts and start exploring the teachings.',
                buttons: ['Continue']
            });

            return true;

        } catch (error) {
            progressDialog.close();

            await dialog.showErrorBox(
                'Setup Failed',
                `Setup encountered an error: ${error.message}\n\nPlease try manual setup or check the troubleshooting guide.`
            );

            return false;
        }
    }

    createProgressDialog(mainWindow) {
        // This would create a progress dialog window
        // For now, we'll use console logging and status updates
        return {
            update: (message, percent) => {
                console.log(`Setup Progress (${percent}%): ${message}`);
                mainWindow.webContents.send('setup-progress', { message, percent });
            },
            close: () => {
                mainWindow.webContents.send('setup-complete');
            }
        };
    }

    async installOllama() {
        const platform = process.platform;

        return new Promise((resolve, reject) => {
            let installCommand;

            switch (platform) {
                case 'darwin': // macOS
                    // Try homebrew first
                    installCommand = 'brew install ollama';
                    break;
                case 'linux':
                    installCommand = 'curl -fsSL https://ollama.ai/install.sh | sh';
                    break;
                case 'win32':
                    // Windows - would need to download and run installer
                    reject(new Error('Windows auto-install not yet supported. Please install Ollama manually from https://ollama.ai/download'));
                    return;
                default:
                    reject(new Error('Unsupported platform for auto-install'));
                    return;
            }

            exec(installCommand, (error, stdout, stderr) => {
                if (error) {
                    reject(new Error(`Failed to install Ollama: ${error.message}`));
                } else {
                    resolve();
                }
            });
        });
    }

    async startOllama() {
        return new Promise((resolve, reject) => {
            const ollamaProcess = spawn('ollama', ['serve'], {
                detached: true,
                stdio: 'ignore'
            });

            ollamaProcess.unref();

            // Wait a few seconds then check if it's running
            setTimeout(async () => {
                try {
                    await axios.get('http://localhost:11434/api/version', { timeout: 5000 });
                    resolve();
                } catch (error) {
                    reject(new Error('Failed to start Ollama service'));
                }
            }, 5000);
        });
    }

    async downloadModel(progressDialog) {
        return new Promise((resolve, reject) => {
            const modelProcess = spawn('ollama', ['pull', 'qwen2.5:14b'], {
                stdio: ['pipe', 'pipe', 'pipe']
            });

            let output = '';

            modelProcess.stdout.on('data', (data) => {
                output += data.toString();
                // Parse progress if available
                const progressMatch = output.match(/(\d+)%/);
                if (progressMatch) {
                    const percent = 60 + (parseInt(progressMatch[1]) * 0.2); // Scale to 60-80%
                    progressDialog.update(`Downloading model... ${progressMatch[1]}%`, percent);
                }
            });

            modelProcess.on('close', (code) => {
                if (code === 0) {
                    resolve();
                } else {
                    reject(new Error('Failed to download Qwen model'));
                }
            });

            modelProcess.on('error', (error) => {
                reject(new Error(`Model download failed: ${error.message}`));
            });
        });
    }

    async installPythonDependencies() {
        const backendPath = path.join(__dirname, '../../python-backend');
        const requirementsPath = path.join(backendPath, 'requirements.txt');

        if (!fs.existsSync(requirementsPath)) {
            throw new Error('Python requirements.txt not found');
        }

        return new Promise((resolve, reject) => {
            const pipProcess = spawn('pip', ['install', '-r', requirementsPath], {
                cwd: backendPath,
                stdio: ['pipe', 'pipe', 'pipe']
            });

            pipProcess.on('close', (code) => {
                if (code === 0) {
                    resolve();
                } else {
                    reject(new Error('Failed to install Python dependencies'));
                }
            });

            pipProcess.on('error', (error) => {
                reject(new Error(`Python dependency install failed: ${error.message}`));
            });
        });
    }

    async showManualInstructions(mainWindow) {
        const instructions = `
Manual Setup Instructions:

1. Install Ollama:
   • Visit: https://ollama.ai/download
   • Download and install for your platform

2. Start Ollama and download model:
   • Run: ollama serve
   • Run: ollama pull qwen2.5:14b

3. Install Python dependencies:
   • cd python-backend
   • pip install -r requirements.txt

4. Restart Buddhist RAG

Need help? Check the documentation in the docs/ folder.
        `;

        const result = await dialog.showMessageBox(mainWindow, {
            type: 'info',
            title: 'Manual Setup Instructions',
            message: 'Please follow these steps to set up Buddhist RAG:',
            detail: instructions,
            buttons: ['Open Documentation', 'I\'ll Do It Later', 'Try Auto Setup'],
            defaultId: 0
        });

        if (result.response === 0) {
            // Open documentation
            shell.openPath(path.join(__dirname, '../../docs/SETUP.md'));
        } else if (result.response === 2) {
            // Try auto setup
            const requirements = await this.checkSystemRequirements();
            return await this.runAutoSetup(mainWindow, requirements);
        }

        return false;
    }
}

module.exports = SetupManager;