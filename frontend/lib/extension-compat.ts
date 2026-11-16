const HOST_ID = "firelens-extension-ui";
const CLIPMIND_ID = "clipmind-side-panel-button";
const installations = new WeakMap<Document, () => void>();

// React deliberately leaves this container's contents unmanaged. The empty
// HTML is a constant, never extension or user-supplied HTML.
export const extensionHostProps = {
  id: HOST_ID,
  style: { display: "contents" },
  suppressHydrationWarning: true,
  dangerouslySetInnerHTML: { __html: "" },
};

export function installExtensionCompatibility(document: Document): () => void {
  const existing = installations.get(document);
  if (existing) return existing;
  const Observer = document.defaultView?.MutationObserver;
  if (!Observer) return () => {};

  let host = document.getElementById(HOST_ID);
  const pending = new Set<Element>();

  function move(element: Element) {
    if (host?.contains(element)) return;
    if (host) host.appendChild(element);
    else {
      // Handle injection before the HTML parser has created our container.
      pending.add(element);
      element.remove();
    }
  }

  function inspect(node: Node) {
    if (node.nodeType !== 1) return;
    const element = node as Element;
    if (host?.contains(element)) return;
    if (element.id === CLIPMIND_ID) move(element);
    else element.querySelectorAll(`#${CLIPMIND_ID}`).forEach(move);
  }

  const observer = new Observer((records) => {
    host = document.getElementById(HOST_ID);
    if (host && pending.size) {
      for (const element of pending) host.appendChild(element);
      pending.clear();
    }
    for (const record of records) {
      if (record.type === "attributes") inspect(record.target);
      else record.addedNodes.forEach(inspect);
    }
  });
  observer.observe(document, { childList: true, subtree: true, attributes: true, attributeFilter: ["id"] });
  // This synchronous pass is essential: instrumentation runs before React
  // hydrates, while an extension may already have injected its button.
  document.querySelectorAll(`#${CLIPMIND_ID}`).forEach(move);

  const cleanup = () => {
    observer.disconnect();
    installations.delete(document);
  };
  installations.set(document, cleanup);
  return cleanup;
}
