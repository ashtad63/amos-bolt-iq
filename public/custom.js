// Amos — small UX hooks for the Chainlit shell.

(function () {
  const WELCOME_TEXT =
    "Hello! I'm Amos, your guide to the Bolt iQ ultrasonic measurement system. " +
    "How can I help you with tension measurement, device operation, or DNV certification today?";

  // 1) Inject the welcome banner above the starters on the empty state.
  function injectWelcome() {
    if (document.getElementById("amos-welcome")) return;
    // Match common Chainlit starter class names (hashed in builds, so substring match)
    const starters = document.querySelector(
      '[class*="Starter" i], [class*="starter" i], .starters'
    );
    if (!starters) return;
    const parent = starters.parentElement;
    if (!parent) return;
    if (parent.querySelector("#amos-welcome")) return;
    const welcome = document.createElement("div");
    welcome.id = "amos-welcome";
    welcome.textContent = WELCOME_TEXT;
    parent.insertBefore(welcome, starters);
  }

  // 2) Make the top-left brand area clickable → home (Chainlit's header
  //    isn't an anchor by default).
  function wireLogoToHome() {
    const header = document.querySelector("header");
    if (!header || header.dataset.amosWired) return;
    header.dataset.amosWired = "1";
    header.addEventListener("click", (e) => {
      const target = e.target.closest("img,svg,a");
      if (!target) return;
      const src = (target.getAttribute("src") || "").toLowerCase();
      const alt = (target.getAttribute("alt") || "").toLowerCase();
      const inTopLeftZone =
        target.tagName === "IMG" && target.getBoundingClientRect().left < 280;
      const isLogo =
        src.includes("logo") ||
        alt.includes("logo") ||
        alt.includes("amos") ||
        alt.includes("predictant") ||
        inTopLeftZone;
      if (isLogo) {
        e.preventDefault();
        e.stopPropagation();
        if (window.location.pathname !== "/") {
          window.location.href = "/";
        } else {
          window.location.reload();
        }
      }
    });
  }

  // 3) Patch the chat-input placeholder. en-US.json override is in the
  //    image, but Chainlit's bundle is aggressively cached on the client,
  //    so we also patch the DOM as belt-and-suspenders.
  function patchPlaceholder() {
    const target = "How can I help you today?";
    document
      .querySelectorAll("textarea, input[type='text']")
      .forEach((el) => {
        const cur = el.getAttribute("placeholder");
        if (cur && cur !== target) el.setAttribute("placeholder", target);
      });
  }

  function init() {
    wireLogoToHome();
    patchPlaceholder();
    injectWelcome();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Chainlit mounts most things asynchronously; rerun on DOM changes.
  const obs = new MutationObserver(() => {
    patchPlaceholder();
    injectWelcome();
    wireLogoToHome();
  });
  obs.observe(document.body, { childList: true, subtree: true });
})();
