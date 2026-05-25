// Amos — small UX hooks for the Chainlit shell.

(function () {
  // 1) Make the top-left brand area clickable → home.
  // Chainlit's header isn't an anchor by default. We attach a delegated
  // click handler to any image/element in the header that looks like the logo.
  function wireLogoToHome() {
    const header = document.querySelector("header");
    if (!header) return;
    header.addEventListener("click", (e) => {
      const target = e.target.closest("img,svg,a");
      if (!target) return;
      const src = (target.getAttribute("src") || "").toLowerCase();
      const alt = (target.getAttribute("alt") || "").toLowerCase();
      const isLogo =
        src.includes("logo") ||
        alt.includes("logo") ||
        alt.includes("amos") ||
        alt.includes("predictant") ||
        // Fallback: any image inside the first ~200px of the header (top-left zone)
        (target.tagName === "IMG" && target.getBoundingClientRect().left < 240);
      if (isLogo) {
        e.preventDefault();
        e.stopPropagation();
        // Navigate to root, force a fresh chat
        if (window.location.pathname !== "/") {
          window.location.href = "/";
        } else {
          // Already on root — reload to reset the session/conversation
          window.location.reload();
        }
      }
    });
  }

  // 2) Tweak the chat input placeholder to a friendlier prompt.
  // Chainlit's i18n key is "components.organisms.chat.inputBox.input.placeholder"
  // (we override it in en-US.json), but the bundle is cached aggressively, so
  // we also patch the DOM as a belt-and-suspenders.
  function patchPlaceholder() {
    const newText = "How can I help you today?";
    const updateOne = (el) => {
      if (el && el.getAttribute("placeholder") && el.getAttribute("placeholder") !== newText) {
        el.setAttribute("placeholder", newText);
      }
    };
    document.querySelectorAll("textarea, input[type='text']").forEach(updateOne);
  }

  const init = () => {
    wireLogoToHome();
    patchPlaceholder();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // The header + input mount asynchronously; re-run on DOM mutations.
  const obs = new MutationObserver(() => {
    patchPlaceholder();
  });
  obs.observe(document.body, { childList: true, subtree: true });
})();
