const { app, BrowserWindow, Menu, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const axios = require('axios');
const SetupManager = require('./setup-manager');

let mainWindow;
let pythonProcess;
let backendReady = false;
let setupManager;

const isDev = process.env.NODE_ENV === 'development';

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      enableRemoteModule: true,
      webSecurity: false,
      allowRunningInsecureContent: true,
      permissions: ['clipboard-read', 'clipboard-write']
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    icon: path.join(__dirname, '../assets/icon.png')
  });

  await mainWindow.loadFile(path.join(__dirname, 'index.html'));

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  setupApplicationMenu();
}

function setupApplicationMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Upload PDF',
          accelerator: 'CmdOrCtrl+O',
          click: () => {
            mainWindow.webContents.send('menu-upload-pdf');
          }
        },
        { type: 'separator' },
        {
          label: 'Settings',
          click: () => {
            mainWindow.webContents.send('menu-settings');
          }
        },
        { type: 'separator' },
        {
          role: 'quit'
        }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About Buddhist RAG',
          click: () => {
            mainWindow.webContents.send('menu-about');
          }
        },
        {
          label: 'User Guide',
          click: () => {
            shell.openExternal('https://github.com/your-repo/buddhist-rag-app/docs/USER_GUIDE.md');
          }
        },
        { type: 'separator' },
        {
          label: 'Check Ollama Status',
          click: () => {
            mainWindow.webContents.send('menu-check-ollama');
          }
        }
      ]
    }
  ];

  if (process.platform === 'darwin') {
    template.unshift({
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    });
  }

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

async function startPythonBackend() {
  return new Promise((resolve, reject) => {
    const pythonScriptPath = isDev
      ? path.join(__dirname, '../../python-backend/app/main.py')
      : path.join(process.resourcesPath, 'python-backend/main.py');

    console.log('Starting Python backend at:', pythonScriptPath);

    pythonProcess = spawn('python', [pythonScriptPath], {
      cwd: isDev ? path.join(__dirname, '../../python-backend') : path.join(process.resourcesPath, 'python-backend'),
      env: { ...process.env, PYTHONPATH: isDev ? path.join(__dirname, '../../python-backend') : path.join(process.resourcesPath, 'python-backend') }
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`Python backend stdout: ${data}`);
      if (data.toString().includes('Uvicorn running')) {
        console.log('Python backend is ready');
        backendReady = true;
        resolve();
      }
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`Python backend stderr: ${data}`);
    });

    pythonProcess.on('close', (code) => {
      console.log(`Python backend exited with code ${code}`);
      backendReady = false;
    });

    pythonProcess.on('error', (error) => {
      console.error('Failed to start Python backend:', error);
      reject(error);
    });

    setTimeout(() => {
      if (!backendReady) {
        reject(new Error('Python backend failed to start within timeout'));
      }
    }, 30000);
  });
}

async function checkBackendHealth() {
  try {
    const response = await axios.get('http://127.0.0.1:8000/health', { timeout: 15000 });
    return response.data;
  } catch (error) {
    console.error('Backend health check failed:', error.message);
    return null;
  }
}

ipcMain.handle('upload-pdf', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'PDF Files', extensions: ['pdf'] }
    ]
  });

  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }

  return null;
});

ipcMain.handle('check-backend-status', async () => {
  const health = await checkBackendHealth();
  return {
    ready: backendReady && health !== null,
    health: health
  };
});

ipcMain.handle('get-app-info', () => {
  return {
    name: app.getName(),
    version: app.getVersion(),
    electron: process.versions.electron,
    node: process.versions.node,
    platform: process.platform
  };
});

ipcMain.handle('open-external', async (event, url) => {
  await shell.openExternal(url);
});

ipcMain.handle('show-error-dialog', async (event, title, content) => {
  await dialog.showErrorBox(title, content);
});

ipcMain.handle('show-info-dialog', async (event, title, content) => {
  const result = await dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: title,
    message: content,
    buttons: ['OK']
  });
  return result.response;
});

app.whenReady().then(async () => {
  console.log('Buddhist RAG starting up...');

  setupManager = new SetupManager();

  await createWindow();

  // Check if backend is already running
  const existingBackend = await checkBackendHealth();

  if (existingBackend && existingBackend.status === 'healthy') {
    console.log('Backend already running - skipping setup and backend start');
    backendReady = true;
  } else {
    // Run setup wizard
    const setupComplete = await setupManager.runSetupWizard(mainWindow);

    if (setupComplete) {
      try {
        await startPythonBackend();
        console.log('Buddhist RAG ready!');
      } catch (error) {
        console.error('Failed to start backend:', error);
        dialog.showErrorBox(
          'Startup Error',
          'Backend failed to start after setup. Please check the troubleshooting guide.\n\n' +
          'Error: ' + error.message
        );
      }
    } else {
      console.log('Setup cancelled or failed');
    }
  }

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }

  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    console.log('Terminating Python backend...');
    pythonProcess.kill();
  }
});

process.on('exit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

process.on('SIGTERM', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  process.exit(0);
});

process.on('SIGINT', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  process.exit(0);
});