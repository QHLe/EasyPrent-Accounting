(function () {
  const helpers = window.EasyPrentFrontendHelpers || {};
  const loadScriptOnce = helpers.loadScriptOnce;
  const renderLoadError = helpers.renderLoadError;

  if (typeof loadScriptOnce !== "function") {
    if (typeof renderLoadError === "function") {
      renderLoadError("Frontend-Helfer konnten nicht initialisiert werden.");
    }
    return;
  }

  loadScriptOnce("/static/app_domain.js")
    .then(function () {
      return loadScriptOnce("/static/app_charts.js");
    })
    .then(function () {
      return loadScriptOnce("/static/app_sections.js");
    })
    .then(function () {
      return loadScriptOnce("/static/app_forms.js");
    })
    .then(function () {
      return loadScriptOnce("/static/app_previews.js");
    })
    .then(function () {
      return loadScriptOnce("/static/app_main.js");
    })
    .catch(function (error) {
      if (typeof renderLoadError === "function") {
        renderLoadError((error && error.message) || "Frontend-Modul konnte nicht geladen werden.");
      }
    });
})();
