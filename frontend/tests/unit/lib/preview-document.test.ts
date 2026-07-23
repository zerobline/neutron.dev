import { describe, expect, it } from "vitest";
import {
  buildSrcDocPreview,
  escapeScriptContent,
  escapeStyleContent,
  extractInlineScripts,
  getPreviewNavigationGuardScript,
  injectPreviewBase,
  neutralizeNestedFrames,
  rewriteRootDataAttrs,
  rewriteRootLinks,
  sanitizeAppJsForPreview,
  stripPreviewAssets,
} from "@/lib/preview-document";

const files = [
  { file_path: "index.html", content: "" },
  { file_path: "styles.css", content: "body{color:red}" },
  { file_path: "app.js", content: "console.log('ready')" },
];

describe("preview-document", () => {
  it("strips linked and inline assets then inlines canonical css and js", () => {
    const html = [
      "<html><head>",
      '<link rel="stylesheet" href="./styles.css">',
      "<style>body{color:old}</style>",
      "</head><body>",
      '<script src="./app.js"></script>',
      "<script>window.OLD = true</script>",
      "</body></html>",
    ].join("");

    const preview = buildSrcDocPreview(html, files);

    expect(preview).not.toContain('href="./styles.css"');
    expect(preview).not.toContain('src="./app.js"');
    expect(preview).not.toContain("color:old");
    expect(preview).not.toContain("window.OLD");
    expect(preview).toContain("<style>body{color:red}</style>");
    expect(preview).toContain("<script>console.log('ready')</script>");
  });

  it("escapes closing tags inside injected assets", () => {
    const html = "<html><head></head><body></body></html>";
    const preview = buildSrcDocPreview(html, [
      { file_path: "styles.css", content: "body::before{content:'</style>'}" },
      { file_path: "app.js", content: "const end = '</script>';" },
    ]);

    expect(preview).toContain("content:'<\\/style>'");
    expect(preview).toContain("const end = '<\\/script>';");
  });

  it("prefers canonical file names when multiple assets exist", () => {
    const html = "<html><head></head><body></body></html>";
    const preview = buildSrcDocPreview(html, [
      { file_path: "theme.css", content: "theme" },
      { file_path: "helper.js", content: "helper" },
      { file_path: "styles.css", content: "canonical-css" },
      { file_path: "app.js", content: "canonical-js" },
    ]);

    expect(preview).toContain("canonical-css");
    expect(preview).toContain("canonical-js");
    expect(preview).not.toContain("theme");
    expect(preview).not.toContain("helper");
  });

  it("isolates preview navigation from the parent app shell", () => {
    const html = [
      "<html><head></head><body>",
      "<nav><a href=\"/\">Home</a><a href=\"/transactions\">Transactions</a></nav>",
      "<iframe src=\"/dashboard\"></iframe>",
      "</body></html>",
    ].join("");
    const preview = buildSrcDocPreview(html, files);

    expect(preview).toContain('<base href="about:srcdoc">');
    expect(preview).toContain('href="#" data-neutron-tab="dashboard"');
    expect(preview).toContain('href="#transactions" data-neutron-tab="transactions"');
    expect(preview).toContain('src="about:blank" data-neutron-frame-path="/dashboard"');
    expect(preview).toContain("activateTab(segment)");
    expect(preview).toContain(getPreviewNavigationGuardScript().slice(0, 40));
    expect(preview.indexOf("activateTab(segment)")).toBeLessThan(preview.indexOf("console.log('ready')"));
    expect(preview).not.toMatch(/<iframe[^>]*\bsrc=["']\/dashboard["']/i);
  });

  it("rewrites generated path navigation in html and javascript", () => {
    const html = '<button data-page="/transactions">Tx</button>';
    const js = 'location.href = "/transactions"; history.pushState({}, "", "/settings");';
    const preview = buildSrcDocPreview(
      `<html><head></head><body>${html}</body></html>`,
      [{ file_path: "styles.css", content: "body{}" }, { file_path: "app.js", content: js }]
    );

    expect(rewriteRootDataAttrs(html)).toBe('<button data-page="transactions">Tx</button>');
    expect(sanitizeAppJsForPreview(js)).toContain('location.hash = "#transactions"');
    expect(sanitizeAppJsForPreview(js)).toContain('history.pushState({}, "", "#settings")');
    expect(preview).toContain('data-page="transactions"');
    expect(preview).toContain('location.hash = "#transactions"');
  });

  it("preserves inline navigation scripts when app.js is missing", () => {
    const html = [
      "<html><head></head><body>",
      "<button data-tab=\"transactions\">Tx</button>",
      "<script>function showTx(){document.getElementById('transactions').hidden=false;}</script>",
      "</body></html>",
    ].join("");
    const preview = buildSrcDocPreview(html, [{ file_path: "styles.css", content: "body{}" }]);

    expect(extractInlineScripts(html)).toEqual([
      "function showTx(){document.getElementById('transactions').hidden=false;}",
    ]);
    expect(stripPreviewAssets(html)).not.toContain("showTx");
    expect(preview).toContain("function showTx()");
  });

  it("ignores empty inline scripts", () => {
    expect(extractInlineScripts("<script>   </script><script>run()</script>"))
      .toEqual(["run()"]);
  });

  it("prefers app.js over inline scripts when both are present", () => {
    const html = [
      "<html><head></head><body>",
      "<script>window.INLINE = true</script>",
      "</body></html>",
    ].join("");
    const preview = buildSrcDocPreview(html, [
      { file_path: "styles.css", content: "body{}" },
      { file_path: "app.js", content: "window.APP = true" },
    ]);

    expect(preview).toContain("window.APP = true");
    expect(preview).not.toContain("window.INLINE");
  });

  it("rewrites window.location assignments in generated javascript", () => {
    const js = 'window.location = "/transactions"; document.location.href = "/settings";';
    expect(sanitizeAppJsForPreview(js)).toContain('location.hash = "#transactions"');
    expect(sanitizeAppJsForPreview(js)).toContain('location.hash = "#settings"');
    expect(getPreviewNavigationGuardScript()).toContain("Object.defineProperty(locationObj, \"href\"");
  });

  it("rewrites location methods and replacement history paths", () => {
    const js = [
      'location.assign("/analytics/daily");',
      'location.replace("/");',
      'history.replaceState({ tab: 1 }, "Analytics", "/analytics");',
    ].join(" ");

    const sanitized = sanitizeAppJsForPreview(js);

    expect(sanitized).toContain('location.hash = "#analytics"');
    expect(sanitized).toContain('location.hash = "#dashboard"');
    expect(sanitized).toContain('history.replaceState({ tab: 1 }, "Analytics", "#analytics")');
  });

  it("exposes escape helpers and asset stripping", () => {
    expect(escapeStyleContent("</style>")).toBe("<\\/style>");
    expect(escapeScriptContent("</script>")).toBe("<\\/script>");
    expect(stripPreviewAssets('<link rel="stylesheet" href="./a.css"><style>a{}</style><script src="./a.js"></script><script>inline()</script>'))
      .toBe("");
    expect(neutralizeNestedFrames('<iframe src="/transactions"></iframe>'))
      .toBe('<iframe src="about:blank" data-neutron-frame-path="/transactions"></iframe>');
    expect(rewriteRootLinks('<a href="/">Home</a><a href="/transactions">Tx</a>'))
      .toBe('<a href="#" data-neutron-tab="dashboard">Home</a><a href="#transactions" data-neutron-tab="transactions">Tx</a>');
    expect(injectPreviewBase("<html><head><base href=\"/\"></head><body></body></html>"))
      .toContain('<base href="about:srcdoc">');
    expect(getPreviewNavigationGuardScript()).toContain("locationObj.assign");
  });
});
