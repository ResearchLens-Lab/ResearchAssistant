const bridge = window.researchLensDesktop;
const title = document.getElementById("title");
const lead = document.getElementById("lead");
const stepLabel = document.getElementById("step-label");
const pathLabel = document.getElementById("library-path");
const diskSpace = document.getElementById("disk-space");
const errorBox = document.getElementById("error");
const nextButton = document.getElementById("next");
const backButton = document.getElementById("back");
const locationNotice = document.getElementById("location-notice");
const panels = [...document.querySelectorAll(".step-panel")];

let step = 1;
const TOTAL_STEPS = 2;
let selection = null;
let suggestedPath = "";

const copy = {
  1: ["Welcome to ResearchLens", "Find the evidence. Understand the research."],
  2: ["Choose your research library", "Your projects, source files and indexes stay together in a folder you choose."],
};

function showStep() {
  panels.forEach((panel) => {
    panel.hidden = Number(panel.dataset.step) !== step;
  });
  document.querySelectorAll("[data-step-dot]").forEach((dot) => {
    dot.classList.toggle("active", Number(dot.dataset.stepDot) === step);
  });
  title.textContent = copy[step][0];
  lead.textContent = copy[step][1];
  stepLabel.textContent = `STEP ${step} OF ${TOTAL_STEPS}`;
  backButton.hidden = step === 1;

  if (step === TOTAL_STEPS) {
    nextButton.innerHTML = "Initialize &amp; Launch <span>→</span>";
  } else {
    nextButton.innerHTML = "Continue <span>→</span>";
  }
  errorBox.hidden = true;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

document.getElementById("choose-folder").addEventListener("click", async () => {
  try {
    const result = await bridge.chooseLibraryFolder();
    if (result) {
      selection = result;
      pathLabel.textContent = result.path;
      if (diskSpace) diskSpace.textContent = "Location verified and ready";
    }
  } catch (error) {
    showError(error.message);
  }
});

backButton.addEventListener("click", () => {
  if (step > 1) {
    step -= 1;
    showStep();
  }
});

nextButton.addEventListener("click", async () => {
  if (step < TOTAL_STEPS) {
    step += 1;
    showStep();
    return;
  }

  // Step 2: Initialize & Launch
  const targetSelection = selection || { path: suggestedPath, selectionId: "default-suggested" };
  if (!targetSelection.path) {
    showError("Please select or confirm a folder for your research library.");
    return;
  }

  nextButton.disabled = true;
  nextButton.textContent = "Initializing local library & starting services…";
  try {
    await bridge.initializeLibrary(targetSelection, { profile: "standard", storageMode: "copy" });
  } catch (error) {
    showError(error.message || "ResearchLens could not initialize this library.");
    nextButton.disabled = false;
    nextButton.innerHTML = "Initialize &amp; Launch <span>→</span>";
  }
});

if (bridge && typeof bridge.getOnboardingState === "function") {
  bridge.getOnboardingState().then((state) => {
    if (state?.suggestedLibrary) {
      suggestedPath = state.suggestedLibrary;
      pathLabel.textContent = suggestedPath;
      if (diskSpace) diskSpace.textContent = "Local Windows user storage";
      if (state.isOneDriveSynced && locationNotice) {
        locationNotice.textContent = "Notice: Your Documents folder is synced with OneDrive. Cloud-synced folders can cause database locking and corruption. We recommend this local AppData location instead.";
        locationNotice.hidden = false;
      }
    }
  }).catch(() => {
    pathLabel.textContent = "Documents\\ResearchLens Library";
  });
}
