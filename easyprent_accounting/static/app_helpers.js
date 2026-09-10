(function () {
  function loadScriptOnce(src) {
    const normalizedSrc = String(src || "").trim();
    if (!normalizedSrc) {
      return Promise.reject(new Error("Script-Quelle fehlt."));
    }

    const existingScript = document.querySelector(
      'script[data-easyprent-module-src="' + normalizedSrc + '"]'
    );
    if (existingScript) {
      if (existingScript.dataset.easyprentLoaded === "true") {
        return Promise.resolve();
      }
      return new Promise(function (resolve, reject) {
        existingScript.addEventListener("load", resolve, { once: true });
        existingScript.addEventListener(
          "error",
          function () {
            reject(new Error("Frontend-Modul konnte nicht geladen werden: " + normalizedSrc));
          },
          { once: true }
        );
      });
    }

    return new Promise(function (resolve, reject) {
      const scriptTag = document.createElement("script");
      scriptTag.src = normalizedSrc;
      scriptTag.async = false;
      scriptTag.dataset.easyprentModuleSrc = normalizedSrc;
      scriptTag.addEventListener(
        "load",
        function () {
          scriptTag.dataset.easyprentLoaded = "true";
          resolve();
        },
        { once: true }
      );
      scriptTag.addEventListener(
        "error",
        function () {
          reject(new Error("Frontend-Modul konnte nicht geladen werden: " + normalizedSrc));
        },
        { once: true }
      );
      document.head.appendChild(scriptTag);
    });
  }

  function renderLoadError(message) {
    const rootNode = document.getElementById("root");
    if (!rootNode) {
      return;
    }
    const safeMessage = String(message || "Frontend-Modul konnte nicht geladen werden.");
    rootNode.innerHTML = "";
    const errorNode = document.createElement("p");
    errorNode.className = "status error";
    errorNode.textContent = safeMessage;
    rootNode.appendChild(errorNode);
  }

  window.EasyPrentFrontendHelpers = {
    loadScriptOnce: loadScriptOnce,
    renderLoadError: renderLoadError,
  };
})();
