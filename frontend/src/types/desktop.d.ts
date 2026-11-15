interface Window {
  researchLensDesktop?: {
    getRuntimeConfig: () => Promise<{ apiBaseUrl: string; requestKey: string }>;
    getOnboardingState: () => Promise<{ configured: boolean; suggestedLibrary: string }>;
    chooseLibraryFolder: () => Promise<{ path: string; selectionId: string } | null>;
    initializeLibrary: (selection: any, options?: any) => Promise<{ ok: boolean }>;
    getDiagnostics: () => Promise<any>;
  };
}

