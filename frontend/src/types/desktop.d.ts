interface Window {
  researchLensDesktop?: {
    getRuntimeConfig: () => Promise<{ apiBaseUrl: string; requestKey: string }>;
    getOnboardingState: () => Promise<{ configured: boolean; suggestedLibrary: string }>;
    chooseLibraryFolder: () => Promise<{ path: string; selectionId: string } | null>;
    initializeLibrary: (selection: any, options?: any) => Promise<{ ok: boolean }>;
    getDiagnostics: () => Promise<any>;
    createBackup?: (dest: string) => Promise<{ ok: boolean; path?: string }>;
    saveSession: (sessionData: { accessToken: string; refreshToken?: string | null }) => Promise<{ ok: boolean }>;
    getSession: () => Promise<{ accessToken: string; refreshToken?: string | null } | null>;
    clearSession: () => Promise<{ ok: boolean }>;
    getProfile: () => Promise<{ lastUsername: string; rememberMe: boolean }>;
    saveProfile: (data: { lastUsername?: string; rememberMe?: boolean }) => Promise<{ ok: boolean }>;
    getIntelligenceStatus?: () => Promise<any>;
    pullIntelligenceModel?: () => Promise<any>;
    onIntelligenceProgress?: (callback: (data: any) => void) => () => void;
    getExternalLookups?: () => Promise<boolean>;
    setExternalLookups?: (enabled: boolean) => Promise<{ ok: boolean }>;
    restartApp?: () => Promise<{ ok: boolean }>;
  };
}

