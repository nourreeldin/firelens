import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { act, createElement as h } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import ts from "typescript";

const require = createRequire(import.meta.url);
const project = fileURLToPath(new URL("../", import.meta.url));
const modules = new Map();
function load(filename) {
  if (modules.has(filename)) return modules.get(filename).exports;
  const module = { exports: {} };
  modules.set(filename, module);
  const output = ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  function localRequire(id) {
    if (id === "next/link") return ({ href, children, ...props }) => h("a", { href, ...props }, children);
    if (!id.startsWith(".") && !id.startsWith("@/")) return require(id);
    const path = id.startsWith("@/") ? resolve(project, id.slice(2)) : resolve(dirname(filename), id);
    const source = [path, `${path}.tsx`, `${path}.ts`].find((candidate) => existsSync(candidate));
    assert.ok(source, `Cannot resolve ${id}`);
    return load(source);
  }
  new Function("require", "module", "exports", output)(localRequire, module, module.exports);
  return module.exports;
}

const LandingPage = load(resolve(project, "components/landing-page.tsx")).default;
const Sidebar = load(resolve(project, "components/workspace-sidebar.tsx")).default;

function setup(markup) {
  const dom = new JSDOM(`<!doctype html><html><body><div id="app">${markup}</div></body></html>`, { url: "http://localhost/", pretendToBeVisual: true });
  const globals = { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, localStorage: dom.window.localStorage, IS_REACT_ACT_ENVIRONMENT: true };
  const saved = new Map(Object.keys(globals).map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(globals)) Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  return {
    dom, document: dom.window.document,
    restore() {
      dom.window.close();
      for (const [key, descriptor] of saved) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    },
  };
}

test("landing page renders without API access and links into valid dashboard workspaces", () => {
  const fetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error("Landing page must not fetch observations"); };
  let dom;
  try {
    dom = new JSDOM(renderToString(h(LandingPage)));
    const document = dom.window.document;
    assert.equal(document.querySelectorAll("h1").length, 1);
    assert.ok(document.querySelector('svg[role="img"][aria-label*="satellite observing Earth"]'));
    assert.match(document.body.textContent, /Preview graphics are illustrative/);
    assert.ok(document.querySelectorAll('a[href="/dashboard"]').length >= 3);
    const views = new Set(["", "#overview", "#activity", "#map", "#analytics", "#data", "#harmonization", "#validation"]);
    for (const link of document.querySelectorAll('a[href^="/dashboard"]')) {
      const url = new URL(link.getAttribute("href"), "http://localhost/");
      assert.equal(url.pathname, "/dashboard");
      assert.ok(views.has(url.hash));
    }
    for (const link of document.querySelectorAll('a[href^="#"]')) assert.ok(document.getElementById(link.getAttribute("href").slice(1)));
    const ids = [...document.querySelectorAll("[id]")].map((node) => node.id);
    assert.equal(ids.length, new Set(ids).size, "Vector illustration and section IDs must remain unique");
  } finally { dom?.window.close(); globalThis.fetch = fetch; }
});

test("landing page hydrates with a saved dark theme and its theme control updates the shared preference", async () => {
  const element = h(LandingPage);
  const env = setup(renderToString(element));
  env.dom.window.localStorage.setItem("firelens-dark", "1");
  let root;
  try {
    const errors = [];
    await act(async () => { root = hydrateRoot(env.document.getElementById("app"), element, { onRecoverableError: (error) => errors.push(error) }); });
    assert.deepEqual(errors, []);
    assert.ok(env.document.documentElement.classList.contains("dark"));
    const toggle = env.document.querySelector('[aria-label="Switch to light mode"]');
    assert.ok(toggle);
    await act(async () => toggle.click());
    assert.equal(env.document.documentElement.classList.contains("dark"), false);
    assert.equal(env.dom.window.localStorage.getItem("firelens-dark"), "0");
  } finally {
    if (root) await act(async () => root.unmount());
    env.restore();
  }
});

test("sidebar hydrates the satellite footer before adding its new home link", async () => {
  const element = h(Sidebar, { activeView: "overview", open: false, onNavigate() {}, onClose() {} });
  const env = setup(renderToString(element));
  let root;
  try {
    const footer = env.document.querySelector(".sidebar-footer");
    const satellite = footer.firstElementChild;
    assert.ok(satellite.classList.contains("sidebar-satellite"));
    assert.equal(env.document.querySelector(".sidebar-home-link"), null);
    const errors = [];
    await act(async () => { root = hydrateRoot(env.document.getElementById("app"), element, { onRecoverableError: (error) => errors.push(error) }); });
    assert.deepEqual(errors, []);
    assert.equal(env.document.querySelector(".sidebar-footer"), footer, "Hydration must preserve the server footer");
    assert.equal(env.document.querySelector(".sidebar-satellite"), satellite);
    assert.equal(env.document.querySelector(".sidebar-home-link").getAttribute("href"), "/");
  } finally {
    if (root) await act(async () => root.unmount());
    env.restore();
  }
});
