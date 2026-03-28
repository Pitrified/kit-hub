document.addEventListener("DOMContentLoaded", function () {
  "use strict";

  // Bulma burger toggle
  var burgers = document.querySelectorAll(".navbar-burger");
  burgers.forEach(function (burger) {
    burger.addEventListener("click", function () {
      var targetId = burger.dataset.target;
      var target = document.getElementById(targetId);
      burger.classList.toggle("is-active");
      if (target) target.classList.toggle("is-active");
    });
  });

  // Generic "clear target" buttons (e.g. cancel on HTMX-loaded forms)
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-clear-target]");
    if (!btn) return;
    var target = document.querySelector(btn.dataset.clearTarget);
    if (target) target.innerHTML = "";
  });
});
