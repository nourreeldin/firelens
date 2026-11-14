(() => {
  const script = document.currentScript;
  const openapiUrl = script?.dataset.openapi || "/openapi.json";
  const el = (id) => document.getElementById(id);
  const state = { spec: null, endpoints: [], selected: null, lastResponse: "" };
  const endpointList = el("endpoint-list");
  const operationPanel = el("operation-panel");

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function schemaType(schema = {}) {
    if (schema.enum) return schema.enum.join(" | ");
    if (Array.isArray(schema.type)) return schema.type.join(" | ");
    if (schema.type === "array") return `${schemaType(schema.items || {})}[]`;
    return schema.type || (schema.$ref ? schema.$ref.split("/").pop() : "value");
  }

  function parameterDefault(parameter) {
    if (parameter.example !== undefined) return parameter.example;
    if (parameter.schema?.example !== undefined) return parameter.schema.example;
    if (parameter.schema?.default !== undefined) return parameter.schema.default;
    if (parameter.schema?.enum?.length) return parameter.schema.enum[0];
    const examples = Object.values(parameter.examples || {});
    if (examples[0]?.value !== undefined) return examples[0].value;
    return "";
  }

  function endpointUrl(endpoint) {
    let path = endpoint.path;
    for (const parameter of endpoint.parameters) {
      if (parameter.in !== "path") continue;
      const input = document.querySelector(`[data-parameter="${CSS.escape(parameter.name)}"]`);
      const value = input?.value.trim() ?? String(parameterDefault(parameter));
      if (value) path = path.replace(`{${parameter.name}}`, encodeURIComponent(value));
    }
    const url = new URL(path, window.location.origin);
    for (const parameter of endpoint.parameters) {
      if (parameter.in !== "query") continue;
      const input = document.querySelector(`[data-parameter="${CSS.escape(parameter.name)}"]`);
      const value = input?.value.trim() ?? String(parameterDefault(parameter));
      if (value !== "") url.searchParams.set(parameter.name, value);
    }
    return url;
  }

  function updateRequestPreview() {
    if (!state.selected) return;
    const url = endpointUrl(state.selected);
    const relative = `${url.pathname}${url.search}`;
    const curl = `curl -X GET '${url.href}' -H 'Accept: application/json'`;
    el("request-path").textContent = relative;
    el("request-code").textContent = curl;
    const unresolved = state.selected.parameters.some((parameter) => {
      if (parameter.in !== "path" || !parameter.required) return false;
      const input = document.querySelector(`[data-parameter="${CSS.escape(parameter.name)}"]`);
      return !input?.value.trim();
    });
    el("run-request").disabled = unresolved;
    el("request-help").textContent = unresolved
      ? "Fill in the required path parameter to run this request."
      : "This request uses the current endpoint parameters.";
  }

  function renderEndpoints() {
    endpointList.innerHTML = state.endpoints.map((endpoint, index) => `
      <button class="endpoint-item" type="button" data-endpoint-index="${index}" aria-current="false">
        <span class="endpoint-method">GET</span>
        <span class="endpoint-path">${escapeHtml(endpoint.path)}</span>
        <span class="endpoint-summary">${escapeHtml(endpoint.summary)}</span>
      </button>`).join("");
    el("endpoint-count").textContent = `${state.endpoints.length} endpoints · All paths are read-only.`;
    endpointList.querySelectorAll("[data-endpoint-index]").forEach((button) => {
      button.addEventListener("click", () => selectEndpoint(Number(button.dataset.endpointIndex)));
    });
  }

  function parameterMarkup(parameter) {
    const schema = parameter.schema || {};
    const defaultValue = parameterDefault(parameter);
    const location = parameter.in === "path" ? "path" : "query";
    const required = parameter.required ? "required" : "optional";
    const description = parameter.description || "No additional description.";
    const choices = schema.enum;
    const control = choices?.length
      ? `<select aria-label="${escapeHtml(parameter.name)}" data-parameter="${escapeHtml(parameter.name)}" data-location="${location}" ${parameter.required ? "required" : ""}>${choices.map((choice) => `<option value="${escapeHtml(choice)}" ${String(choice) === String(defaultValue) ? "selected" : ""}>${escapeHtml(choice)}</option>`).join("")}</select>`
      : `<input aria-label="${escapeHtml(parameter.name)}" data-parameter="${escapeHtml(parameter.name)}" data-location="${location}" type="${schema.format === "date" ? "date" : "text"}" value="${escapeHtml(defaultValue)}" placeholder="${parameter.required ? "Required" : "Optional"}" ${parameter.required ? "required" : ""} />`;
    return `<div class="parameter-row">
      <span class="parameter-name">${escapeHtml(parameter.name)}</span>
      <span class="parameter-meta">${escapeHtml(schemaType(schema))} · ${required}</span>
      <span class="parameter-description">${escapeHtml(description)}</span>
      <label class="parameter-control"><span class="eyebrow">${location.toUpperCase()}</span>${control}</label>
    </div>`;
  }

  function renderOperation(endpoint) {
    const parameters = endpoint.parameters;
    const responses = Object.entries(endpoint.operation.responses || {});
    const parametersContent = parameters.length
      ? parameters.map(parameterMarkup).join("")
      : '<p class="no-parameters">This endpoint does not require any parameters.</p>';
    const responseContent = responses.map(([code, response]) => `
      <span class="response-ref-code">${escapeHtml(code)}</span>
      <span class="response-ref-description">${escapeHtml(response.description || "Response")}</span>`).join("");
    const description = endpoint.operation.description || "Review the request parameters and response status codes below.";
    operationPanel.innerHTML = `
      <div class="panel-heading">
        <div><h2 class="operation-title"><span class="operation-method">GET</span>${escapeHtml(endpoint.path)}</h2>
        <p>${escapeHtml(endpoint.summary)}</p></div>
        <span class="status-pill">READ-ONLY</span>
      </div>
      <p class="operation-description">${escapeHtml(description)}</p>
      <h3 class="section-title">Request parameters</h3>
      ${parametersContent}
      <h3 class="section-title">Response status</h3>
      <div class="response-reference">${responseContent || '<span class="response-ref-description">Schema does not list response codes.</span>'}</div>`;
    operationPanel.querySelectorAll("[data-parameter]").forEach((input) => {
      input.addEventListener("input", updateRequestPreview);
      input.addEventListener("change", updateRequestPreview);
    });
  }

  function selectEndpoint(index) {
    const endpoint = state.endpoints[index];
    if (!endpoint) return;
    state.selected = endpoint;
    endpointList.querySelectorAll("[data-endpoint-index]").forEach((button) => {
      const selected = Number(button.dataset.endpointIndex) === index;
      button.setAttribute("aria-current", String(selected));
    });
    renderOperation(endpoint);
    updateRequestPreview();
    el("response-caption").textContent = "No request sent";
    el("response-status").textContent = "—";
    el("response-status").className = "status-code";
    el("response-state").textContent = "Awaiting request";
    el("response-code").textContent = "Run a request to see its response here.";
    state.lastResponse = "";
    document.querySelectorAll(".copy-button").forEach((button) => {
      if (button.dataset.copy === "response-code") button.disabled = true;
    });
  }

  async function runRequest() {
    if (!state.selected) return;
    const url = endpointUrl(state.selected);
    const button = el("run-request");
    button.disabled = true;
    button.textContent = "Sending request…";
    el("response-caption").textContent = "Request in progress";
    el("response-state").textContent = "Waiting for response";
    el("response-code").textContent = "Loading…";
    el("response-status").textContent = "…";
    el("response-status").className = "status-code";
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      const raw = await response.text();
      let body;
      try { body = raw ? JSON.parse(raw) : null; } catch { body = raw; }
      const formatted = typeof body === "string" ? body : JSON.stringify(body, null, 2);
      state.lastResponse = formatted || "(empty response)";
      el("response-code").textContent = state.lastResponse;
      el("response-caption").textContent = `Response · ${url.pathname}`;
      el("response-status").textContent = response.status;
      el("response-status").className = `status-code ${response.ok ? "success" : "failure"}`;
      el("response-state").textContent = response.statusText || (response.ok ? "Success" : "Request failed");
      document.querySelector('[data-copy="response-code"]').disabled = false;
    } catch (error) {
      state.lastResponse = JSON.stringify({ error: error.message || "Network request failed" }, null, 2);
      el("response-code").textContent = state.lastResponse;
      el("response-caption").textContent = "Request failed";
      el("response-status").textContent = "ERR";
      el("response-status").className = "status-code failure";
      el("response-state").textContent = "Could not reach this API";
      document.querySelector('[data-copy="response-code"]').disabled = false;
    } finally {
      button.innerHTML = 'Run request <span aria-hidden="true">→</span>';
      updateRequestPreview();
    }
  }

  async function copyText(id) {
    try {
      await navigator.clipboard.writeText(el(id).textContent);
      const toast = el("toast");
      toast.textContent = "Copied to clipboard";
      toast.classList.add("visible");
      window.setTimeout(() => toast.classList.remove("visible"), 1500);
    } catch {
      el(id).focus?.();
    }
  }

  function render(spec) {
    state.spec = spec;
    el("api-version").textContent = `Version ${spec.info?.version || "1"}`;
    el("sidebar-version").textContent = `V${spec.info?.version || "1"}`;
    el("api-description").textContent = spec.info?.description || "Explore read-only endpoints for FireLens data.";
    const paths = Object.entries(spec.paths || {});
    state.endpoints = paths.flatMap(([path, pathItem]) => Object.entries(pathItem || {})
      .filter(([method]) => method.toLowerCase() === "get")
      .map(([, operation]) => ({
        path,
        operation,
        summary: operation.summary || operation.operationId || "Read endpoint",
        parameters: [...(pathItem.parameters || []), ...(operation.parameters || [])],
      })));
    state.endpoints.sort((a, b) => a.path.localeCompare(b.path));
    renderEndpoints();
    const routePrefixes = state.endpoints.map(({ path }) => path.split("/").filter(Boolean));
    let prefix = [];
    if (routePrefixes.length) {
      for (let i = 0; routePrefixes.every((parts) => parts[i] && parts[i] === routePrefixes[0][i]); i++) prefix.push(routePrefixes[0][i]);
    }
    el("base-path").textContent = prefix.length ? `/${prefix.join("/")}` : "Relative to the API host";
    el("loading").hidden = true;
    el("docs-layout").hidden = false;
    if (state.endpoints.length) selectEndpoint(0);
    el("overview-button").addEventListener("click", () => {
      el("overview-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  el("run-request").addEventListener("click", runRequest);
  document.querySelectorAll(".copy-button").forEach((button) => {
    button.addEventListener("click", () => copyText(button.dataset.copy));
  });

  fetch(openapiUrl, { headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) throw new Error(`OpenAPI schema returned ${response.status}`);
      return response.json();
    })
    .then(render)
    .catch((error) => {
      el("loading").hidden = true;
      el("load-error").textContent = `The API reference could not load. ${error.message}`;
      el("load-error").hidden = false;
    });
})();
