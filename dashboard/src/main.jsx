import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Ban,
  Braces,
  CalendarDays,
  Check,
  Clock3,
  Coins,
  Fingerprint,
  FlaskConical,
  GitCommit,
  KeyRound,
  ListTree,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const ADMIN_KEY = import.meta.env.VITE_LOGLLAMA_ADMIN_KEY || "llama-admin-key";
const DEFAULT_RANGE = { amount: 24, unit: "hours" };
const RANGE_PRESETS = [
  { label: "5m", minutes: 5 },
  { label: "30m", minutes: 30 },
  { label: "1h", minutes: 60 },
  { label: "6h", minutes: 360 },
  { label: "24h", minutes: 1440 },
  { label: "7d", minutes: 10080 },
];
function formatMoney(value) {
  return `$${Number(value || 0).toFixed(6)}`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function compactNumber(value) {
  return new Intl.NumberFormat(undefined, { notation: "compact" }).format(Number(value || 0));
}

function display(value, fallback = "unknown") {
  return value || fallback;
}

function toMinutes(range) {
  const amount = Number(range.amount) || 1;
  if (range.unit === "minutes") return amount;
  if (range.unit === "hours") return amount * 60;
  return amount * 24 * 60;
}

function formatRangeLabel(minutes) {
  if (minutes < 60) return `Last ${minutes} min`;
  if (minutes % (24 * 60) === 0) {
    const days = minutes / (24 * 60);
    return `Last ${days} ${days === 1 ? "day" : "days"}`;
  }
  if (minutes % 60 === 0) {
    const hours = minutes / 60;
    return `Last ${hours} ${hours === 1 ? "hour" : "hours"}`;
  }
  return `Last ${minutes} min`;
}

function privacyState(payload) {
  if (!payload) return "not captured";
  if (payload._logllama_capture === "disabled") return "disabled";
  if (payload._logllama_capture === "truncated") return "truncated";
  return "captured";
}

function BrandMark() {
  return (
    <div className="brandMark" aria-hidden="true">
      <span>LL</span>
    </div>
  );
}

function StatusPill({ status }) {
  return <span className={`status ${status}`}>{status}</span>;
}

function MetricCard({ icon: Icon, label, value, detail, tone }) {
  return (
    <section className={`metric ${tone || ""}`}>
      <div className="metricLabel">
        <Icon size={16} />
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </section>
  );
}

function SelectFilter({ label, value, options, onChange }) {
  return (
    <label className={`filterSelect ${value ? "active" : ""}`}>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function DurationControl({ value, onChange }) {
  const minutes = toMinutes(value);
  const setAmount = (nextValue) => {
    const parsed = Number(nextValue);
    if (Number.isNaN(parsed)) return;
    const max = value.unit === "days" ? 30 : value.unit === "hours" ? 24 * 30 : 60 * 24 * 30;
    onChange({ ...value, amount: Math.min(max, Math.max(1, parsed)) });
  };
  const setUnit = (unit) => {
    const max = unit === "days" ? 30 : unit === "hours" ? 24 * 30 : 60 * 24 * 30;
    onChange({ amount: Math.min(max, Math.max(1, Number(value.amount) || 1)), unit });
  };

  return (
    <div className="durationControl" aria-label="Time range">
      <label htmlFor="timeRangeAmount">
        <CalendarDays size={15} />
        <span>Last</span>
        <input
          id="timeRangeAmount"
          min="1"
          type="number"
          value={value.amount}
          onChange={(event) => setAmount(event.target.value)}
        />
        <select aria-label="Time unit" value={value.unit} onChange={(event) => setUnit(event.target.value)}>
          <option value="minutes">min</option>
          <option value="hours">hours</option>
          <option value="days">days</option>
        </select>
      </label>
      <div className="durationPresets" aria-label="Quick ranges">
        {RANGE_PRESETS.map((preset) => (
          <button key={preset.label} className={minutes === preset.minutes ? "active" : ""} type="button" onClick={() => onChange(minutesToRange(preset.minutes))}>
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function minutesToRange(minutes) {
  if (minutes % (24 * 60) === 0) return { amount: minutes / (24 * 60), unit: "days" };
  if (minutes % 60 === 0) return { amount: minutes / 60, unit: "hours" };
  return { amount: minutes, unit: "minutes" };
}

function RequestRow({ request, selected, onSelect }) {
  return (
    <button className={`requestRow ${selected ? "selected" : ""}`} onClick={() => onSelect(request)}>
      <span>
        <StatusPill status={request.status} />
      </span>
      <span className="modelCell">{display(request.service_name || request.model)}</span>
      <span className="routeCell">{display(request.route || request.operation)}</span>
      <span>{display(request.environment, "env n/a")}</span>
      <span>{display(request.tenant_id, "tenant n/a")}</span>
      <span>{request.latency_ms} ms</span>
      <span>{formatDate(request.captured_at)}</span>
    </button>
  );
}

function JsonBlock({ title, value, defaultOpen = false }) {
  return (
    <details className="jsonBlock" open={defaultOpen}>
      <summary className="jsonTitle">
        <Braces size={14} />
        <h3>{title}</h3>
      </summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function FieldGrid({ items }) {
  return (
    <dl className="fieldGrid">
      {items.map(({ label, value, mono }) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd className={mono ? "monoValue" : ""}>{display(value, "not set")}</dd>
        </div>
      ))}
    </dl>
  );
}

function TagList({ tags }) {
  if (!tags?.length) return <span className="mutedText">No tags</span>;
  return (
    <div className="tagList">
      {tags.map((tag) => (
        <span key={tag}>{tag}</span>
      ))}
    </div>
  );
}

function RequestDetail({ request }) {
  if (!request) {
    return (
      <aside className="detailPane empty">
        <Server size={22} />
        <h2>No trace selected</h2>
        <p>Select a request to inspect correlation, privacy, usage, prompt, response, and metadata.</p>
      </aside>
    );
  }

  return (
    <aside className="detailPane">
      <div className="detailHeader">
        <div>
          <span className="eyebrow">Inspector</span>
          <h2>{display(request.route || request.operation)}</h2>
          <p>
            {display(request.service_name, "service n/a")} / {display(request.model)}
          </p>
        </div>
        <StatusPill status={request.status} />
      </div>

      <dl className="details">
        <div>
          <dt>Latency</dt>
          <dd>{request.latency_ms} ms</dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>{compactNumber(request.total_tokens)}</dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd>{formatMoney(request.cost_usd)}</dd>
        </div>
      </dl>

      {request.error_message && (
        <section className="errorBox">
          <strong>{request.error_type || "Error"}</strong>
          <p>{request.error_message}</p>
        </section>
      )}

      <section className="detailSection">
        <div className="sectionTitle">
          <Fingerprint size={15} />
          <h3>Correlation</h3>
        </div>
        <FieldGrid
          items={[
            { label: "Tenant", value: request.tenant_id },
            { label: "User", value: request.user_id },
            { label: "Session", value: request.session_id, mono: true },
            { label: "Conversation", value: request.conversation_id, mono: true },
            { label: "Request", value: request.request_id, mono: true },
            { label: "Trace", value: request.trace_id, mono: true },
            { label: "Span", value: request.span_id, mono: true },
          ]}
        />
      </section>

      <section className="detailSection">
        <div className="sectionTitle">
          <GitCommit size={15} />
          <h3>Runtime</h3>
        </div>
        <FieldGrid
          items={[
            { label: "Service", value: request.service_name },
            { label: "Environment", value: request.environment },
            { label: "Version", value: request.version },
            { label: "Git SHA", value: request.git_sha, mono: true },
            { label: "Prompt", value: request.prompt_template },
            { label: "Prompt version", value: request.prompt_version },
          ]}
        />
        <div className="tagsBlock">
          <span>Tags</span>
          <TagList tags={request.tags} />
        </div>
      </section>

      <section className="detailSection">
        <div className="sectionTitle">
          <ShieldCheck size={15} />
          <h3>Privacy</h3>
        </div>
        <div className="privacyGrid">
          <span>Prompt: {privacyState(request.prompt)}</span>
          <span>Response: {privacyState(request.response)}</span>
          <span>Sampling: {request.privacy?.sample_rate ?? 1}</span>
        </div>
      </section>

      <JsonBlock title="Prompt" value={request.prompt} defaultOpen />
      <JsonBlock title="Response" value={request.response} />
      <JsonBlock title="Custom Metadata" value={request.custom_metadata || {}} />
    </aside>
  );
}

async function adminFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-LogLlama-Admin-Key": ADMIN_KEY,
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Admin API returned ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function ProviderCredentialsAdmin() {
  const [credentials, setCredentials] = React.useState([]);
  const [backend, setBackend] = React.useState("");
  const [provider, setProvider] = React.useState("openai");
  const [name, setName] = React.useState("default");
  const [apiKey, setApiKey] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    try {
      const payload = await adminFetch("/api/admin/provider-credentials");
      setCredentials(payload.credentials || []);
      setBackend(payload.secret_backend || "");
      setError("");
    } catch (err) {
      setError(err.message || "Unable to load provider credentials");
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await adminFetch("/api/admin/provider-credentials", {
        method: "POST",
        body: JSON.stringify({ provider, name, api_key: apiKey }),
      });
      setApiKey("");
      await load();
    } catch (err) {
      setError(err.message || "Unable to save credential");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (credential) => {
    if (!window.confirm(`Remove the ${credential.provider} credential "${credential.name}"?`)) return;
    setBusy(true);
    try {
      await adminFetch(`/api/admin/provider-credentials/${credential.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err.message || "Unable to remove credential");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="adminWorkspace">
      {error && <div className="banner">{error}</div>}
      <div className="adminIntro">
        <div>
          <span className="eyebrow">Secret backend: {backend || "loading"}</span>
          <h2>Provider credentials</h2>
          <p>Keys are write-only here. The database keeps a reference and fingerprint, not the key value.</p>
        </div>
        <button className="iconCommand" type="button" onClick={load} aria-label="Refresh credentials" title="Refresh credentials">
          <RefreshCw size={16} />
        </button>
      </div>

      <form className="credentialForm" onSubmit={save}>
        <label>
          <span>Provider</span>
          <select value={provider} onChange={(event) => setProvider(event.target.value)}>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
          </select>
        </label>
        <label>
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} maxLength="120" required />
        </label>
        <label className="secretInput">
          <span>API key / PAT</span>
          <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} minLength="8" autoComplete="new-password" required />
        </label>
        <button className="primaryCommand" type="submit" disabled={busy || apiKey.length < 8}>
          <KeyRound size={16} />
          <span>{busy ? "Saving" : "Store key"}</span>
        </button>
      </form>

      <div className="adminTable">
        <div className="adminTableHeader credentialColumns">
          <span>Provider</span><span>Name</span><span>Fingerprint</span><span>Version</span><span>Status</span><span />
        </div>
        {credentials.map((credential) => (
          <div className="adminTableRow credentialColumns" key={credential.id}>
            <strong>{credential.provider}</strong>
            <span>{credential.name}</span>
            <code>{credential.fingerprint}</code>
            <span>v{credential.version}</span>
            <StatusPill status={credential.status} />
            <button className="dangerIcon" type="button" onClick={() => remove(credential)} disabled={busy} aria-label={`Remove ${credential.provider} credential`} title="Remove credential">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
        {!credentials.length && <div className="emptyList">No managed provider credentials</div>}
      </div>
    </section>
  );
}

function TestPlansAdmin() {
  const [plans, setPlans] = React.useState([]);
  const [busyId, setBusyId] = React.useState("");
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    try {
      const payload = await adminFetch("/api/admin/test-plans");
      setPlans(payload.test_plans || []);
      setError("");
    } catch (err) {
      setError(err.message || "Unable to load test plans");
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const decide = async (plan, decision) => {
    setBusyId(plan.id);
    try {
      await adminFetch(`/api/admin/test-plans/${plan.id}/${decision}`, {
        method: "POST",
        body: JSON.stringify({
          expires_in_hours: 24,
          reason: decision === "reject" ? "Rejected by administrator" : null,
        }),
      });
      await load();
    } catch (err) {
      setError(err.message || `Unable to ${decision} test plan`);
    } finally {
      setBusyId("");
    }
  };

  return (
    <section className="adminWorkspace">
      {error && <div className="banner">{error}</div>}
      <div className="adminIntro">
        <div>
          <span className="eyebrow">Cost control</span>
          <h2>Provider comparison approvals</h2>
          <p>Approval applies to the exact prompt, provider/model targets, and output limit shown below.</p>
        </div>
        <button className="iconCommand" type="button" onClick={load} aria-label="Refresh test plans" title="Refresh test plans">
          <RefreshCw size={16} />
        </button>
      </div>

      <div className="testPlanList">
        {plans.map((plan) => (
          <article className="testPlan" key={plan.id}>
            <header>
              <div>
                <span className="eyebrow">{formatDate(plan.created_at)}</span>
                <h3>{plan.targets.map((target) => target.provider).join(" vs ")}</h3>
              </div>
              <StatusPill status={plan.status} />
            </header>
            <pre className="promptPreview">{plan.prompt}</pre>
            <div className="targetList">
              {plan.targets.map((target) => (
                <span key={`${target.provider}:${target.model}`}>
                  <strong>{target.provider}</strong>
                  <code>{target.model}</code>
                </span>
              ))}
            </div>
            <footer>
              <span>Maximum output: {plan.max_output_tokens} tokens per provider / runs: {plan.run_count} of {plan.max_runs}</span>
              {plan.status === "pending" && (
                <div className="decisionActions">
                  <button className="rejectCommand" type="button" onClick={() => decide(plan, "reject")} disabled={busyId === plan.id}>
                    <Ban size={15} /><span>Reject</span>
                  </button>
                  <button className="approveCommand" type="button" onClick={() => decide(plan, "approve")} disabled={busyId === plan.id}>
                    <Check size={15} /><span>Approve 24h</span>
                  </button>
                </div>
              )}
            </footer>
          </article>
        ))}
        {!plans.length && <div className="emptyList">No comparison requests awaiting review</div>}
      </div>
    </section>
  );
}

function App() {
  const [view, setView] = React.useState("traces");
  const [summary, setSummary] = React.useState(null);
  const [requests, setRequests] = React.useState([]);
  const [facets, setFacets] = React.useState({});
  const [selected, setSelected] = React.useState(null);
  const [query, setQuery] = React.useState("");
  const deferredQuery = React.useDeferredValue(query.trim());
  const [timeRange, setTimeRange] = React.useState(DEFAULT_RANGE);
  const [filters, setFilters] = React.useState({
    environment: "",
    service_name: "",
    tenant_id: "",
    route: "",
    model: "",
    status: "",
  });
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rangeMinutes = toMinutes(timeRange);
      const params = new URLSearchParams({ limit: "100", minutes: String(rangeMinutes) });
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      if (deferredQuery) params.set("q", deferredQuery);

      const summaryParams = new URLSearchParams(params);
      summaryParams.delete("limit");

      const facetParams = new URLSearchParams(params);
      facetParams.delete("limit");

      const [summaryResponse, requestResponse, facetsResponse] = await Promise.all([
        fetch(`${API_BASE}/api/metrics/summary?${summaryParams.toString()}`),
        fetch(`${API_BASE}/api/requests?${params.toString()}`),
        fetch(`${API_BASE}/api/metadata/facets?${facetParams.toString()}`),
      ]);
      if (!summaryResponse.ok || !requestResponse.ok || !facetsResponse.ok) {
        throw new Error("Backend returned an error");
      }
      const summaryJson = await summaryResponse.json();
      const requestJson = await requestResponse.json();
      const facetsJson = await facetsResponse.json();
      const nextRequests = requestJson.requests || [];
      setSummary(summaryJson);
      setRequests(nextRequests);
      setFacets(facetsJson);
      setSelected((current) => nextRequests.find((request) => request.id === current?.id) || nextRequests[0] || null);
    } catch (err) {
      setError(err.message || "Unable to load LogLlama data");
    } finally {
      setLoading(false);
    }
  }, [deferredQuery, filters, timeRange]);

  React.useEffect(() => {
    if (view !== "traces") return undefined;
    load();
    const interval = window.setInterval(load, 10000);
    return () => window.clearInterval(interval);
  }, [load, view]);

  const filtered = requests;
  const activeFilterCount = Object.values(filters).filter(Boolean).length + (deferredQuery ? 1 : 0);
  const setFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const resetFilters = () => {
    setQuery("");
    setTimeRange(DEFAULT_RANGE);
    setFilters({
      environment: "",
      service_name: "",
      tenant_id: "",
      route: "",
      model: "",
      status: "",
    });
  };
  const rangeMinutes = toMinutes(timeRange);
  const rangeLabel = formatRangeLabel(rangeMinutes);

  return (
    <main className="appShell">
      <section className="content">
        <header className="topbar">
          <div className="topbarLead">
            <div className="brand compact">
              <BrandMark />
              <div>
                <strong>LogLlama</strong>
                <span>AI correlation console</span>
              </div>
            </div>
            <div>
              <span className="eyebrow">Live local capture</span>
              <h1>{view === "traces" ? "Traces" : view === "credentials" ? "Providers" : "Test approvals"}</h1>
              <nav className="viewTabs" aria-label="Console views">
                <button className={view === "traces" ? "active" : ""} type="button" onClick={() => setView("traces")}><ListTree size={15} /><span>Traces</span></button>
                <button className={view === "credentials" ? "active" : ""} type="button" onClick={() => setView("credentials")}><KeyRound size={15} /><span>Providers</span></button>
                <button className={view === "tests" ? "active" : ""} type="button" onClick={() => setView("tests")}><FlaskConical size={15} /><span>Tests</span></button>
              </nav>
            </div>
          </div>
          {view === "traces" && <div className="topbarActions">
            <DurationControl value={timeRange} onChange={setTimeRange} />
            <button className="refreshButton" onClick={load} aria-label="Refresh data">
              <RefreshCw size={16} />
              <span>{loading ? "Syncing" : "Refresh"}</span>
            </button>
          </div>}
        </header>

        {view === "traces" && (
          <>
            {error && <div className="banner">{error}</div>}

            <section className="metricsGrid">
              <MetricCard icon={Activity} label="Requests" value={summary?.total_requests ?? 0} detail={rangeLabel} />
              <MetricCard icon={Coins} label="Spend" value={formatMoney(summary?.total_cost_usd)} detail={`${rangeLabel} estimated cost`} />
              <MetricCard icon={Clock3} label="Latency" value={`${Math.round(summary?.avg_latency_ms || 0)} ms`} detail={`${rangeLabel} average`} />
              <MetricCard
                icon={AlertTriangle}
                label="Error rate"
                value={`${Math.round((summary?.error_rate || 0) * 100)}%`}
                detail={`${rangeLabel} failures`}
                tone={summary?.error_rate ? "warning" : ""}
              />
            </section>

            <section className="workspace">
          <div className="requestPanel">
            <div className="panelHeader">
              <div>
                <h2>Request stream</h2>
                <p>
                  {filtered.length} traces shown, {rangeLabel.toLowerCase()}
                </p>
              </div>
              <label className="search">
                <Search size={15} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search like GCP: trace, tenant, route, model, prompt" />
              </label>
            </div>

            <div className="filterBar">
              <div className="filterSummary" title="Filters apply to metrics, facets, and request rows">
                <SlidersHorizontal size={15} />
                <div>
                  <strong>{activeFilterCount ? `${activeFilterCount} active` : "All traces"}</strong>
                  <span>Dashboard scope</span>
                </div>
              </div>
              <SelectFilter label="Env" value={filters.environment} options={facets.environments || []} onChange={(value) => setFilter("environment", value)} />
              <SelectFilter label="Service" value={filters.service_name} options={facets.service_names || []} onChange={(value) => setFilter("service_name", value)} />
              <SelectFilter label="Tenant" value={filters.tenant_id} options={facets.tenant_ids || []} onChange={(value) => setFilter("tenant_id", value)} />
              <SelectFilter label="Route" value={filters.route} options={facets.routes || []} onChange={(value) => setFilter("route", value)} />
              <SelectFilter label="Model" value={filters.model} options={facets.models || []} onChange={(value) => setFilter("model", value)} />
              <SelectFilter label="Status" value={filters.status} options={facets.statuses || []} onChange={(value) => setFilter("status", value)} />
              <button className="clearFilters" type="button" onClick={resetFilters} disabled={!activeFilterCount && rangeMinutes === toMinutes(DEFAULT_RANGE)}>
                <X size={14} />
                <span>Reset</span>
              </button>
            </div>

            <div className="requestHeader">
              <span>Status</span>
              <span>Service / Model</span>
              <span>Route</span>
              <span>Env</span>
              <span>Tenant</span>
              <span>Latency</span>
              <span>Captured</span>
            </div>
            <div className="requestList">
              {filtered.map((request) => (
                <RequestRow key={request.id} request={request} selected={selected?.id === request.id} onSelect={setSelected} />
              ))}
              {!filtered.length && <div className="emptyList">No matching traces</div>}
            </div>
          </div>
          <RequestDetail request={selected} />
            </section>
          </>
        )}
        {view === "credentials" && <ProviderCredentialsAdmin />}
        {view === "tests" && <TestPlansAdmin />}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
