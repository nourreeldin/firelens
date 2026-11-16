import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { act, createElement as h, Suspense } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { JSDOM } from "jsdom";
import ts from "typescript";

const source = await readFile(new URL("../lib/extension-compat.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
});
const { extensionHostProps, installExtensionCompatibility } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function fixture() {
  return h("html", { lang: "en" },
    h("head", null, h("title", null, "FireLens")),
    h("body", null,
      h("div", extensionHostProps),
      h("main", { id: "dashboard" }, "Fire activity"),
      h("div", { hidden: true, id: "metadata-boundary" },
        h(Suspense, { fallback: null }, h("span", null, "Metadata"))),
    ));
}

function setup() {
  const dom = new JSDOM(`<!doctype html>${renderToString(fixture())}`, { pretendToBeVisual: true });
  const values = { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true };
  const saved = new Map(Object.keys(values).map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(values)) Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  return {
    dom,
    document: dom.window.document,
    restore() {
      dom.window.close();
      for (const [key, descriptor] of saved) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    },
  };
}

function inject(document, id = "clipmind-side-panel-button") {
  const element = document.createElement("div");
  element.id = id;
  element.style.position = "fixed";
  element.appendChild(document.createElement("button")).textContent = "Clipmind";
  document.body.insertBefore(element, document.getElementById("metadata-boundary"));
  return element;
}

test("reproduces the reported metadata hydration failure without the compatibility pass", async () => {
  const env = setup();
  let root;
  try {
    inject(env.document);
    const errors = [];
    await act(async () => { root = hydrateRoot(env.document, fixture(), { onRecoverableError: (error) => errors.push(error) }); });
    assert.ok(errors.some((error) => /hydration|hydrated/i.test(error.message)));
  } finally {
    if (root) await act(async () => root.unmount());
    env.restore();
  }
});

test("existing Clipmind injection hydrates without recovery and retains the original button and handlers", async () => {
  const env = setup();
  let root, cleanup;
  try {
    const dashboard = env.document.getElementById("dashboard");
    const extension = inject(env.document);
    const button = extension.querySelector("button");
    let clicks = 0;
    button.addEventListener("click", () => clicks++);
    cleanup = installExtensionCompatibility(env.document);
    // Must happen synchronously, before hydrateRoot starts.
    assert.equal(extension.parentElement.id, extensionHostProps.id);
    const errors = [];
    await act(async () => { root = hydrateRoot(env.document, fixture(), { onRecoverableError: (error) => errors.push(error) }); });
    assert.deepEqual(errors, []);
    assert.equal(env.document.getElementById("dashboard"), dashboard);
    assert.equal(env.document.getElementById(extension.id), extension);
    assert.equal(extension.querySelector("button"), button);
    button.click();
    assert.equal(clicks, 1);
  } finally {
    cleanup?.();
    if (root) await act(async () => root.unmount());
    env.restore();
  }
});

test("late injection and reinsertion are moved into the unmanaged host", async () => {
  const env = setup();
  let root, cleanup;
  try {
    cleanup = installExtensionCompatibility(env.document);
    assert.equal(installExtensionCompatibility(env.document), cleanup);
    const errors = [];
    let extension;
    await act(async () => {
      extension = inject(env.document);
      await Promise.resolve();
      root = hydrateRoot(env.document, fixture(), { onRecoverableError: (error) => errors.push(error) });
    });
    assert.deepEqual(errors, []);
    assert.equal(extension.parentElement.id, extensionHostProps.id);
    env.document.body.appendChild(extension);
    await Promise.resolve();
    assert.equal(extension.parentElement.id, extensionHostProps.id);
    const replacement = env.document.createElement("div");
    env.document.body.appendChild(replacement);
    replacement.id = "clipmind-side-panel-button";
    await Promise.resolve();
    assert.equal(replacement.parentElement.id, extensionHostProps.id);
  } finally {
    cleanup?.();
    if (root) await act(async () => root.unmount());
    env.restore();
  }
});

test("early injection is retained until the parser creates the compatibility host", async () => {
  const dom = new JSDOM("<!doctype html><html><head></head><body></body></html>");
  const { document } = dom.window;
  const element = document.createElement("div");
  element.id = "clipmind-side-panel-button";
  document.body.appendChild(element);
  const cleanup = installExtensionCompatibility(document);
  try {
    assert.equal(element.isConnected, false);
    const host = document.createElement("div");
    host.id = extensionHostProps.id;
    document.body.appendChild(host);
    await Promise.resolve();
    assert.equal(host.firstChild, element);
  } finally {
    cleanup();
    dom.window.close();
  }
});

test("unrelated DOM mismatches still produce hydration errors", async () => {
  const env = setup();
  let root, cleanup;
  try {
    const unrelated = inject(env.document, "unrelated-injected-element");
    cleanup = installExtensionCompatibility(env.document);
    assert.equal(unrelated.parentElement, env.document.body);
    const errors = [];
    await act(async () => { root = hydrateRoot(env.document, fixture(), { onRecoverableError: (error) => errors.push(error) }); });
    assert.ok(errors.length > 0);
  } finally {
    cleanup?.();
    if (root) await act(async () => root.unmount());
    env.restore();
  }
});
