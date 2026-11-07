// Small extras on top of the no-JS <details> behaviour:
//  - close an open event card when clicking outside it or pressing Escape
//  - remember which sidebar cards are collapsed (localStorage)
// Everything still works without this script.
(function () {
  "use strict";

  // ---- Event cards ----
  function openCards() {
    return document.querySelectorAll("details.event-details[open]");
  }

  document.addEventListener("click", function (e) {
    var inside = e.target.closest("details.event-details");
    openCards().forEach(function (card) {
      if (card !== inside) card.open = false;
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    openCards().forEach(function (card) {
      card.open = false;
      if (card.contains(document.activeElement)) card.querySelector("summary").focus();
    });
  });

  // ---- Collapsed sidebar cards ----
  var KEY = "ravenminders.collapsedCards";

  function loadCollapsed() {
    try {
      var list = JSON.parse(localStorage.getItem(KEY));
      return Array.isArray(list) ? list : [];
    } catch (err) {
      return [];
    }
  }

  function saveCollapsed(list) {
    try {
      localStorage.setItem(KEY, JSON.stringify(list));
    } catch (err) {
      // storage blocked or full: cards just open by default next time
    }
  }

  var collapsed = loadCollapsed();
  document.querySelectorAll("details[data-card]").forEach(function (card) {
    var name = card.dataset.card;
    if (collapsed.indexOf(name) !== -1) card.open = false;
    card.addEventListener("toggle", function () {
      var list = loadCollapsed().filter(function (n) { return n !== name; });
      if (!card.open) list.push(name);
      saveCollapsed(list);
    });
  });
})();
