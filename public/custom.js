// Amos — UX hooks for the Chainlit shell.
// Strategy notes:
//  - Chainlit's class names are hashed, so we use multiple selectors and
//    text-content matching to locate the empty-state DOM nodes.
//  - We re-run on every MutationObserver tick because Chainlit hydrates
//    asynchronously and re-renders some elements.

(function () {
  const WELCOME_TEXT =
    "Hello! I'm Amos, your guide to the Bolt iQ ultrasonic measurement system. " +
    "How can I help you with tension measurement, device operation, or DNV certification today?";

  // Keywords that uniquely identify our starter card labels.
  const STARTER_LABEL_PATTERN = /(What is Bolt iQ|Why choose Predictant|Bi-wave vs|DNV-certified)/i;

  // ---------------------------------------------------------------
  // 1) Inject the welcome banner above the starter cards.
  // ---------------------------------------------------------------
  function findStartersContainer() {
    // Find any element whose text contains a known starter label
    const labelEls = Array.from(document.querySelectorAll("button, [role='button'], a, div"))
      .filter((el) => STARTER_LABEL_PATTERN.test(el.textContent || ""));
    if (labelEls.length === 0) return null;

    // The smallest element matching is the card itself. Climb until we find
    // a parent that contains multiple matches (the grid/row container).
    let card = labelEls[0];
    // Pick the smallest matching element (the card, not its parents)
    for (const el of labelEls) {
      if (el.contains(card) === false && card.contains(el) === false) continue;
      if (el.children.length < card.children.length || card === labelEls[0]) {
        // pick smaller
        if ((el.textContent || "").length < (card.textContent || "").length) card = el;
      }
    }
    // Climb to the parent that contains at least 2 starter labels
    let container = card.parentElement;
    while (container && container !== document.body) {
      const matches = Array.from(container.querySelectorAll("*")).filter((el) =>
        STARTER_LABEL_PATTERN.test(el.textContent || "")
      );
      if (matches.length >= 2) return container;
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
  // 3) Patch the chat-input placeholder.
  // ---------------------------------------------------------------
  function patchPlaceholder() {
    const target = "How can I help you today?";
    document.querySelectorAll("textarea, input[type='text']").forEach((el) => {
      const cur = el.getAttribute("placeholder");
      if (cur && cur !== target) el.setAttribute("placeholder", target);
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
