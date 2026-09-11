(function () {
  function textFromHtml(html) {
    var el = document.createElement("div");
    el.innerHTML = html || "";
    return (el.textContent || "").trim();
  }

  function textFromDraftail(raw) {
    raw = (raw || "").trim();
    if (!raw || raw === "null" || raw === "undefined") {
      return "";
    }
    try {
      var state = JSON.parse(raw);
      if (!state || !Array.isArray(state.blocks)) {
        return textFromHtml(raw);
      }
      return state.blocks
        .map(function (block) {
          return (block && block.text) || "";
        })
        .join("")
        .trim();
    } catch (e) {
      return textFromHtml(raw);
    }
  }

  function bodyInput() {
    return document.querySelector('[data-draftail-input][name="body"]');
  }

  function dumpButton() {
    return document.querySelector("[data-menu-dump]");
  }

  function sync() {
    var button = dumpButton();
    var input = bodyInput();
    if (!button) {
      return;
    }
    button.hidden = !!(input && textFromDraftail(input.value));
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.addEventListener("input", sync);
    document.addEventListener("change", sync);
    document.addEventListener("w-draftail:init", sync);
    sync();
  });
})();
