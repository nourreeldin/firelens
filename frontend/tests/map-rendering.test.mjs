import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { act, createElement as h, StrictMode } from "react";
import { JSDOM } from "jsdom";
import ts from "typescript";

test("real map markers and popups survive updates and repeated sidebar mount cycles without a canvas context", async () => {
  const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', { pretendToBeVisual: true, url: "http://localhost/" });
  const errors = [];
  let canvasRequests = 0;
  const observers = [];
  // Modern browsers support SVG. jsdom needs this feature probe supplied.
  dom.window.SVGSVGElement.prototype.createSVGRect = () => ({});
  dom.window.HTMLCanvasElement.prototype.getContext = () => { canvasRequests++; return null; };
  Object.defineProperty(dom.window.HTMLElement.prototype, "clientWidth", { configurable: true, get: () => 800 });
  Object.defineProperty(dom.window.HTMLElement.prototype, "clientHeight", { configurable: true, get: () => 430 });
  class ResizeObserver {
    constructor() { this.disconnected = false; observers.push(this); }
    observe() {}
    disconnect() { this.disconnected = true; }
  }
  const values = {
    window: dom.window, document: dom.window.document, navigator: dom.window.navigator,
    HTMLElement: dom.window.HTMLElement, SVGElement: dom.window.SVGElement,
    getComputedStyle: dom.window.getComputedStyle.bind(dom.window), ResizeObserver,
    IS_REACT_ACT_ENVIRONMENT: true,
  };
  const saved = new Map(Object.keys(values).map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(values)) Object.defineProperty(globalThis, key, { value, writable: true, configurable: true });
  dom.window.addEventListener("error", (event) => { errors.push(event.error); event.preventDefault(); });
  let root;
  try {
    // Use the real React Leaflet and Leaflet packages, not the navigation
    // test's placeholder map. Only the CSS import is omitted in Node.
    const source = await readFile(new URL("../components/fire-map.tsx", import.meta.url), "utf8");
    const { outputText } = ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX },
    });
    const executable = outputText
      .replace(/^import ["']leaflet\/dist\/leaflet\.css["'];?\s*$/gm, "")
      .replace(/from (["'])([^"']+)\1/g, (_, quote, specifier) => `from ${JSON.stringify(import.meta.resolve(specifier))}`);
    const { default: FireMap } = await import(`data:text/javascript;base64,${Buffer.from(executable).toString("base64")}`);
    const { createRoot } = await import("react-dom/client");
    root = createRoot(dom.window.document.getElementById("app"), { onUncaughtError: (error) => errors.push(error) });
    const detection = { id: 42, latitude: 30.04, longitude: 31.23, acq_date: "2020-07-15", sensor: "VIIRS", confidence: "high", country_code: "EGY", frp: 1.25 };
    const waitForFrames = () => new Promise((done) => setTimeout(done, 50));

    for (let cycle = 0; cycle < 3; cycle++) {
      await act(async () => root.render(h(StrictMode, null, h(FireMap, { fires: [detection], dark: false }))));
      await act(waitForFrames);
      assert.deepEqual(errors, []);
      const marker = dom.window.document.querySelector(".leaflet-overlay-pane svg path.leaflet-interactive");
      assert.ok(marker, "A detection must be rendered and interactive");
      await act(async () => marker.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true, clientX: 400, clientY: 215 })));
      assert.match(dom.window.document.querySelector(".leaflet-popup-content").textContent, /FIRE DETECTION #42/);

      // Updating filters/theme schedules renderer work; navigate away before
      // the next animation frame, then allow all queued work to settle.
      await act(async () => root.render(h(StrictMode, null, h(FireMap, { fires: [{ ...detection, id: 43, latitude: 30.1 }], dark: true }))));
      assert.equal(dom.window.document.querySelectorAll(".leaflet-overlay-pane svg path.leaflet-interactive").length, 1);
      await act(async () => root.render(h(StrictMode, null)));
      await act(waitForFrames);
      assert.deepEqual(errors, []);
      assert.equal(dom.window.document.querySelector(".leaflet-container"), null);
      assert.ok(observers.every((observer) => observer.disconnected));
    }
    assert.equal(canvasRequests, 0, "Map rendering must not depend on a canvas context");
  } finally {
    if (root) await act(async () => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
