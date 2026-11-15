const bridge = window.researchLensDesktop;
const title = document.getElementById("title");
const lead = document.getElementById("lead");
const stepLabel = document.getElementById("step-label");
const pathLabel = document.getElementById("library-path");
const diskSpace = document.getElementById("disk-space");
const readyPathSummary = document.getElementById("ready-path-summary");
const errorBox = document.getElementById("error");
const nextButton = document.getElementById("next");
const backButton = document.getElementById("back");
const panels = [...document.querySelectorAll(".step-panel")];

let step = 1;
const TOTAL_STEPS = 6;
let selection = null;
let storageMode = "copy";
let profile = "low";
let suggestedPath = "";

const copy = {
  1: ["Welcome to ResearchLens", "Find the evidence. Understand the research."],
  2: ["Choose your research library", "Your projects, source files and indexes stay together in a folder you choose."],
  3: ["Document handling", "Choose how files are added to your research library."],
  4: ["Resource profile", "Set a comfortable processing pace for this computer."],
  5: ["Privacy defaults", "ResearchLens keeps its core research workflow strictly on this computer."],
  6: ["Ready to initialize", "Review your workspace setup and launch ResearchLens."],
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
    if (readyPathSummary) {
      readyPathSummary.textContent = selection?.path || suggestedPath || "Default Library";
    }
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

// Storage Mode toggle
const modeCopy = document.getElementById("mode-copy");
const modeLink = document.getElementById("mode-link");

if (modeCopy && modeLink) {
  modeCopy.addEventListener("click", () => {
    storageMode = "copy";
    modeCopy.classList.add("selected");
    modeLink.classList.remove("selected");
  });

  modeLink.addEventListener("click", () => {
    storageMode = "link";
    modeLink.classList.add("selected");
    modeCopy.classList.remove("selected");
  });
}

// Profile buttons
document.querySelectorAll("[data-profile]").forEach((button) => {
  button.addEventListener("click", () => {
    profile = button.dataset.profile;
    document.querySelectorAll("[data-profile]").forEach((item) => {
      item.classList.toggle("selected", item === button);
    });
  });
});

backButton.addEventListener("click", () => {
  if (step > 1) {
    step -= 1;
    showStep();
  }
});

nextButton.addEventListener("click", async () => {
  if (step < TOTAL_STEPS) {
    // If on Step 2 and user hasn't browsed, use the suggested path
    if (step === 2 && !selection && suggestedPath) {
      selection = { path: suggestedPath, selectionId: "default-suggested" };
    }
    step += 1;
    showStep();
    return;
  }

  // Final step: Initialize
  const targetSelection = selection || { path: suggestedPath, selectionId: "default-suggested" };
  if (!targetSelection.path) {
    showError("Please select or confirm a folder for your research library.");
    return;
  }

  nextButton.disabled = true;
  nextButton.textContent = "Initializing local library & starting services…";
  try {
    await bridge.initializeLibrary(targetSelection, { profile, storageMode });
  } catch (error) {
    showError(error.message || "ResearchLens could not initialize this library.");
    nextButton.disabled = false;
    nextButton.innerHTML = "Initialize &amp; Launch <span>→</span>";
  }
});

bridge.getOnboardingState().then((state) => {
  if (state?.suggestedLibrary) {
    suggestedPath = state.suggestedLibrary;
    pathLabel.textContent = suggestedPath;
    if (diskSpace) diskSpace.textContent = "Local Windows user storage";
  }
}).catch(() => {
  pathLabel.textContent = "Choose a local folder";
});

showStep();
