if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch((error) => {
      console.error("FareWise could not register its offline support.", error);
    });
  });
}

let installPrompt;
const installButton = document.querySelector("#install-app");
const installHelp = document.querySelector("#install-help");

if (
  window.matchMedia("(display-mode: standalone)").matches ||
  navigator.standalone === true
) {
  installButton.hidden = true;
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
});

installButton?.addEventListener("click", async () => {
  if (installPrompt) {
    const prompt = installPrompt;
    installPrompt = undefined;
    await prompt.prompt();
    const choice = await prompt.userChoice;
    if (choice.outcome === "accepted") {
      installButton.hidden = true;
    }
    return;
  }

  if (installHelp) {
    installHelp.open = true;
    installButton.setAttribute("aria-expanded", "true");
    installHelp.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
});

installHelp?.addEventListener("toggle", () => {
  installButton?.setAttribute("aria-expanded", String(installHelp.open));
});

window.addEventListener("appinstalled", () => {
  installPrompt = undefined;
  if (installButton) installButton.hidden = true;
});
