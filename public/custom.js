// Amos — UX hooks for the Chainlit shell.
// Strategy notes:
//  - Chainlit's class names are hashed, so we use multiple selectors and
//    text-content matching to locate the empty-state DOM nodes.
//  - We re-run on every MutationObserver tick because Chainlit hydrates
//    asynchronously and re-renders some elements.

(function () {
  const WELCOME_TEXT =
    "Hi, I'm Amos! Ask me anything about Bolt iQ, ultrasonic tension measurement, or DNV certification.";

  // ---------------------------------------------------------------
  // 1) Inject the welcome banner above the starter cards.
  //    Chainlit's starter buttons have ids like `starter-what-is-bolt-iq?`.
  //    Using the IDs (not text content) avoids false positives in the
  //    sidebar chat-history where prior starter labels also appear.
  // ---------------------------------------------------------------
  function findStartersContainer() {
    const cards = Array.from(document.querySelectorAll('button[id^="starter-"]'));
    if (cards.length === 0) return null;
    // The starter cards are siblings inside a MuiGrid container (one
    // ancestor up from the card → grid-item; two ancestors up → grid).
    const card = cards[0];
    // Walk up until the ancestor contains all `cards.length` starter buttons.
    let container = card.parentElement;
    while (container && container !== document.body) {
      const inside = container.querySelectorAll('button[id^="starter-"]');
      if (inside.length === cards.length) return container;
      container = container.parentElement;
    }
    return card.parentElement;
  }

  function injectWelcome() {
    if (document.getElementById("amos-welcome")) return;
    const startersContainer = findStartersContainer();
    if (!startersContainer) return;

    const parent = startersContainer.parentElement;
    if (!parent) return;

    // Build a wrapper so we can vertically center the whole group
    let wrap = document.getElementById("amos-empty-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "amos-empty-wrap";
      parent.insertBefore(wrap, startersContainer);
      wrap.appendChild(startersContainer);
    }

    const welcome = document.createElement("div");
    welcome.id = "amos-welcome";
    welcome.textContent = WELCOME_TEXT;
    wrap.insertBefore(welcome, startersContainer);
  }

  // ---------------------------------------------------------------
  // 2) Logo click -> home.
  // ---------------------------------------------------------------
  function wireLogoToHome() {
    const header = document.querySelector("header");
    if (!header || header.dataset.amosWired) return;
    header.dataset.amosWired = "1";
    header.addEventListener("click", (e) => {
      const target = e.target.closest("img, svg, a");
      if (!target) return;
      const src = (target.getAttribute("src") || "").toLowerCase();
      const alt = (target.getAttribute("alt") || "").toLowerCase();
      const inTopLeft =
        target.tagName === "IMG" && target.getBoundingClientRect().left < 360;
      const isLogo =
        src.includes("logo") ||
        alt.includes("logo") ||
        alt.includes("amos") ||
        alt.includes("predictant") ||
        inTopLeft;
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

  // ---------------------------------------------------------------
  // 3) Patch placeholders.
  //    Chat <textarea> gets the friendly chat prompt.
  //    The login form's email input shares the same i18n key as the chat
  //    placeholder in Chainlit 1.3, so React renders "How can I help you
  //    today?" on it too. We explicitly override it to "Username" — the
  //    @cl.password_auth_callback accepts any string.
  // ---------------------------------------------------------------
  function patchPlaceholder() {
    const chatTarget = "How can I help you today?";
    document.querySelectorAll("textarea").forEach((el) => {
      const cur = el.getAttribute("placeholder");
      if (cur && cur !== chatTarget) el.setAttribute("placeholder", chatTarget);
    });
    const emailTarget = "Username";
    document.querySelectorAll("input[type='text'][name='email']").forEach((el) => {
      const cur = el.getAttribute("placeholder");
      if (cur !== emailTarget) el.setAttribute("placeholder", emailTarget);
    });
  }

  // ---------------------------------------------------------------
  // Boot + observe
  // ---------------------------------------------------------------
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

  const obs = new MutationObserver(() => {
    wireLogoToHome();
    patchPlaceholder();
    injectWelcome();
  });
  obs.observe(document.body, { childList: true, subtree: true });
})();
