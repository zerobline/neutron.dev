export interface PreviewFile {
  file_path: string;
  content: string;
}

function findCssFile(files: PreviewFile[]): PreviewFile | undefined {
  return (
    files.find((file) => file.file_path === "styles.css") ??
    files.find((file) => file.file_path.endsWith(".css"))
  );
}

function findJsFile(files: PreviewFile[]): PreviewFile | undefined {
  return (
    files.find((file) => file.file_path === "app.js") ??
    files.find((file) => file.file_path.endsWith(".js"))
  );
}

export function escapeStyleContent(css: string): string {
  return css.replace(/<\/style/gi, "<\\/style");
}

export function escapeScriptContent(js: string): string {
  return js.replace(/<\/script/gi, "<\\/script");
}

const PREVIEW_BASE_TAG = '<base href="about:srcdoc">';

/** Collect inline script bodies before stripping so crew nav logic is not lost. */
export function extractInlineScripts(html: string): string[] {
  const scripts: string[] = [];
  const pattern = /<script\b(?![^>]*\bsrc\s*=)[^>]*>([\s\S]*?)<\/script>/gi;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(html)) !== null) {
    const body = match[1]?.trim();
    if (body) scripts.push(body);
  }
  return scripts;
}

/** Remove linked/inline assets so preview uses canonical styles.css + app.js. */
export function stripPreviewAssets(html: string): string {
  return html
    .replace(/<link\b[^>]*rel=["']stylesheet["'][^>]*>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<script\b[^>]*\bsrc=["'][^"']+["'][^>]*>\s*<\/script>/gi, "")
    .replace(/<script\b(?![^>]*\bsrc\s*=)[^>]*>[\s\S]*?<\/script>/gi, "");
}

/** Rewrite in-app links so tab clicks stay inside the preview document. */
export function rewriteRootLinks(html: string): string {
  return html
    .replace(/\bhref=["']\/["']/gi, 'href="#" data-neutron-tab="dashboard"')
    .replace(/\bhref=["']\/([^"'#?]+)["']/gi, 'href="#$1" data-neutron-tab="$1"');
}

/** Normalize root-relative data-* routing attributes on nav controls. */
export function rewriteRootDataAttrs(html: string): string {
  return html
    .replace(
      /\bdata-(tab|page|view|route|href|panel)=["']\/["']/gi,
      'data-$1="dashboard"'
    )
    .replace(
      /\bdata-(tab|page|view|route|href|panel)=["']\/([^"']+)["']/gi,
      'data-$1="$2"'
    );
}

function hashFromRootPath(path: string): string {
  const segment = path.replace(/^\//, "").split("/").filter(Boolean)[0];
  return `#${segment || "dashboard"}`;
}

function rewriteRootPathNavigation(js: string): string {
  return js
    .replace(
      /(?:window\.|document\.)?location(?:\.href)?\s*=\s*(['"])(\/[^'"]*)\1/g,
      (_match, _quote, path: string) => `location.hash = "${hashFromRootPath(path)}"`
    )
    .replace(
      /location\.assign\(\s*(['"])(\/[^'"]*)\1\s*\)/g,
      (_match, _quote, path: string) => `location.hash = "${hashFromRootPath(path)}"`
    )
    .replace(
      /location\.replace\(\s*(['"])(\/[^'"]*)\1\s*\)/g,
      (_match, _quote, path: string) => `location.hash = "${hashFromRootPath(path)}"`
    )
    .replace(
      /history\.pushState\(\s*([^,]+),\s*([^,]+),\s*(['"])(\/[^'"]*)\3\s*\)/g,
      (_match, state: string, title: string, _quote, path: string) =>
        `history.pushState(${state}, ${title}, "${hashFromRootPath(path)}")`
    )
    .replace(
      /history\.replaceState\(\s*([^,]+),\s*([^,]+),\s*(['"])(\/[^'"]*)\3\s*\)/g,
      (_match, state: string, title: string, _quote, path: string) =>
        `history.replaceState(${state}, ${title}, "${hashFromRootPath(path)}")`
    );
}

/** Rewrite generated path navigation so preview tabs do not load the Neutron shell. */
export function sanitizeAppJsForPreview(js: string): string {
  return rewriteRootPathNavigation(js);
}

/** Prevent root-relative iframe targets from loading the Neutron shell. */
export function neutralizeNestedFrames(html: string): string {
  return html.replace(
    /<iframe\b([^>]*)\bsrc=["'](\/[^"']*)["']/gi,
    '<iframe$1src="about:blank" data-neutron-frame-path="$2"'
  );
}

/** Keep srcdoc previews from inheriting the parent app origin for "/" links. */
export function injectPreviewBase(html: string): string {
  if (/<base\b/i.test(html)) {
    return html.replace(/<base\b[^>]*>/i, PREVIEW_BASE_TAG);
  }
  if (/<head\b/i.test(html)) {
    return html.replace(/<head([^>]*)>/i, `<head$1>${PREVIEW_BASE_TAG}`);
  }
  return `${PREVIEW_BASE_TAG}${html}`;
}

export function getPreviewNavigationGuardScript(): string {
  return `<script>
(function() {
  function tabFromPath(path) {
    if (typeof path !== "string") return null;
    if (path.charAt(0) !== "/" || path.charAt(1) === "/") return null;
    var segment = path.slice(1).split("/").filter(Boolean)[0];
    return segment || "dashboard";
  }

  function activateTab(segment) {
    if (!segment) segment = "dashboard";
    var handlers = ["showTab", "switchTab", "navigateTo", "openTab", "setActiveTab", "loadView"];
    for (var i = 0; i < handlers.length; i++) {
      var fn = window[handlers[i]];
      if (typeof fn === "function") {
        try { fn(segment); return true; } catch (err) {}
      }
    }
    var panel = document.getElementById(segment)
      || document.getElementById(segment + "-panel")
      || document.getElementById(segment + "-view")
      || document.getElementById(segment + "-content")
      || document.getElementById("page-" + segment)
      || document.querySelector('[data-panel="' + segment + '"]')
      || document.querySelector('[data-view="' + segment + '"]')
      || document.querySelector('[data-tab-panel="' + segment + '"]')
      || document.querySelector('[role="tabpanel"][id="' + segment + '"]')
      || document.querySelector('.tab-content[id="' + segment + '"]');
    if (panel) {
      var panels = document.querySelectorAll(
        "[data-panel], [data-view], [data-tab-panel], [role=tabpanel], .tab-panel, .tab-content, .page-view, .view-panel, section.page, .page, .view"
      );
      for (var j = 0; j < panels.length; j++) {
        panels[j].hidden = true;
        panels[j].style.display = "none";
        panels[j].classList.remove("active", "is-active", "visible", "show");
      }
      panel.hidden = false;
      panel.style.display = "";
      panel.classList.add("active", "visible");
      panel.removeAttribute("hidden");
    }
    var navItems = document.querySelectorAll("[data-tab], [data-view], [data-page], .nav-link, .tab-btn, .tab, nav button, nav a");
    for (var k = 0; k < navItems.length; k++) {
      var item = navItems[k];
      var key = item.getAttribute("data-tab") || item.getAttribute("data-view") || item.getAttribute("data-page")
        || (item.getAttribute("href") || "").replace(/^[#\\/]+/, "").split("/")[0];
      var active = key === segment;
      item.classList.toggle("active", active);
      item.classList.toggle("is-active", active);
      if (item.getAttribute("aria-selected") !== null) item.setAttribute("aria-selected", active ? "true" : "false");
    }
    try { window.location.hash = "#" + segment; } catch (err) {}
    return !!panel;
  }

  function intercept(url) {
    var segment = tabFromPath(url);
    if (segment === null) return false;
    activateTab(segment);
    return true;
  }

  document.addEventListener("click", function(e) {
    var link = e.target.closest('a[href], button, [role="tab"], [data-href], [data-route], [data-page]');
    if (!link) return;
    var href = link.getAttribute("href") || link.getAttribute("data-href") || link.getAttribute("data-route") || link.getAttribute("data-page") || "";
    if (!intercept(href)) return;
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);

  document.addEventListener("click", function(e) {
    var tabEl = e.target.closest("[data-tab], [data-view], [data-page]");
    if (!tabEl) return;
    var segment = tabEl.getAttribute("data-tab") || tabEl.getAttribute("data-view") || tabEl.getAttribute("data-page");
    if (segment) activateTab(segment.replace(/^[#\\/]+/, ""));
  }, true);

  window.addEventListener("hashchange", function() {
    var segment = window.location.hash.replace(/^#/, "");
    if (segment) activateTab(segment);
  });

  var historyObj = window.history;
  if (historyObj && historyObj.pushState) {
    var pushState = historyObj.pushState.bind(historyObj);
    var replaceState = historyObj.replaceState.bind(historyObj);
    historyObj.pushState = function(state, title, url) {
      if (intercept(String(url || ""))) return;
      return pushState(state, title, url);
    };
    historyObj.replaceState = function(state, title, url) {
      if (intercept(String(url || ""))) return;
      return replaceState(state, title, url);
    };
  }

  var locationObj = window.location;
  if (locationObj && locationObj.assign) {
    var assign = locationObj.assign.bind(locationObj);
    var replace = locationObj.replace.bind(locationObj);
    locationObj.assign = function(url) { if (intercept(String(url))) return; return assign(url); };
    locationObj.replace = function(url) { if (intercept(String(url))) return; return replace(url); };
  }

  try {
    var hrefDesc = Object.getOwnPropertyDescriptor(window.Location.prototype, "href");
    if (hrefDesc && hrefDesc.set) {
      Object.defineProperty(locationObj, "href", {
        configurable: true,
        get: hrefDesc.get ? hrefDesc.get.bind(locationObj) : function() { return locationObj.toString(); },
        set: function(url) {
          if (intercept(String(url))) return;
          hrefDesc.set.call(locationObj, url);
        }
      });
    }
  } catch (err) {}

  function boot() {
    var initial = window.location.hash.replace(/^#/, "");
    if (initial) activateTab(initial);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
</script>`;
}

export function buildSrcDocPreview(html: string, files: PreviewFile[]): string {
  const cssFile = findCssFile(files);
  const jsFile = findJsFile(files);
  const inlineScripts = extractInlineScripts(html);
  const mergedJs = jsFile ? jsFile.content : inlineScripts.join("\n");

  let result = injectPreviewBase(
    neutralizeNestedFrames(rewriteRootDataAttrs(rewriteRootLinks(stripPreviewAssets(html))))
  );

  if (cssFile) {
    result = result.replace(
      "</head>",
      `<style>${escapeStyleContent(cssFile.content)}</style></head>`
    );
  }

  const bodyInjection = [
    getPreviewNavigationGuardScript(),
    mergedJs ? `<script>${escapeScriptContent(sanitizeAppJsForPreview(mergedJs))}</script>` : "",
  ].join("");

  result = result.replace("</body>", `${bodyInjection}</body>`);

  return result;
}
