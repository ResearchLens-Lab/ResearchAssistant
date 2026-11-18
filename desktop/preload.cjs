const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("researchLensDesktop", Object.freeze({
  getOnboardingState: () => ipcRenderer.invoke("onboarding:state"),
  chooseLibraryFolder: () => ipcRenderer.invoke("onboarding:choose-library"),
  initializeLibrary: (selection, options) => ipcRenderer.invoke("onboarding:initialize", selection, options),
  getRuntimeConfig: () => ipcRenderer.invoke("desktop:runtime-config"),
  getDiagnostics: () => ipcRenderer.invoke("desktop:diagnostics"),
  createBackup: (dest) => ipcRenderer.invoke("desktop:create-backup", dest),
  saveSession: (sessionData) => ipcRenderer.invoke("desktop:save-session", sessionData),
  getSession: () => ipcRenderer.invoke("desktop:get-session"),
  clearSession: () => ipcRenderer.invoke("desktop:clear-session"),
  getProfile: () => ipcRenderer.invoke("desktop:get-profile"),
  saveProfile: (data) => ipcRenderer.invoke("desktop:save-profile", data),
  getIntelligenceStatus: () => ipcRenderer.invoke("intelligence:status"),
  pullIntelligenceModel: () => ipcRenderer.invoke("intelligence:pull-model"),
  getExternalLookups: () => ipcRenderer.invoke("desktop:get-external-lookups"),
  setExternalLookups: (enabled) => ipcRenderer.invoke("desktop:set-external-lookups", enabled),
  restartApp: () => ipcRenderer.invoke("desktop:restart-app"),
  getPinStatus: () => ipcRenderer.invoke("desktop:pin-status"),
  setPin: (pin) => ipcRenderer.invoke("desktop:set-pin", pin),
  verifyPin: (pin) => ipcRenderer.invoke("desktop:verify-pin", pin),
  removePin: (pin) => ipcRenderer.invoke("desktop:remove-pin", pin),
  onIntelligenceProgress: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on("intelligence:progress", handler);
    return () => ipcRenderer.removeListener("intelligence:progress", handler);
  },
}));

contextBridge.exposeInMainWorld("startupBridge", Object.freeze({
  onProgress: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on("startup:progress", handler);
    return () => ipcRenderer.removeListener("startup:progress", handler);
  },
  onError: (callback) => {
    const handler = (_event, errorData) => callback(errorData);
    ipcRenderer.on("startup:error", handler);
    return () => ipcRenderer.removeListener("startup:error", handler);
  },
  retry: () => ipcRenderer.invoke("startup:retry"),
  openLogs: () => ipcRenderer.invoke("startup:open-logs"),
  copyDetails: (details) => ipcRenderer.invoke("startup:copy-details", details),
  selectLibrary: () => ipcRenderer.invoke("startup:select-library"),
}));
