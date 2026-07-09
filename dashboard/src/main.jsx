import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Braces,
  Clock3,
  Coins,
  Gauge,
  Layers3,
  RefreshCw,
  Search,
  Server,
  Sparkles,
  TerminalSquare,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

function RequestRow({ request, selected, onSelect }) {
  return (
    <button className={`requestRow ${selected ? "selected" : ""}`} onClick={() => onSelect(request)}>
      <span>
        <StatusPill status={request.status} />
      </span>
      <span className="modelCell">{request.model || "unknown"}</span>
      <span className="routeCell">{request.request_metadata?.route || request.operation}</span>
      <span>{request.latency_ms} ms</span>
      <span>{compactNumber(request.total_tokens)}</span>
      <span>{formatMoney(request.cost_usd)}</span>
      <span>{formatDate(request.captured_at)}</span>
    </button>
  );
}

function JsonBlock({ title, value }) {
  return (
    <section className="jsonBlock">
      <div className="jsonTitle">
        <Braces size={14} />
        <h3>{title}</h3>
      </div>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

function RequestDetail({ request }) {
  if (!request) {
    return (
      <aside className="detailPane empty">
        <Server size={22} />
        <h2>No trace selected</h2>
        <p>Select a request to inspect prompt, response, usage, timing, and metadata.</p>
      </aside>
    );
  }

  return (
    <aside className="detailPane">
      <div className="detailHeader">
        <div>
          <span className="eyebrow">Inspector</span>
          <h2>{request.model || "Unknown model"}</h2>
          <p>
            {request.provider} / {request.operation}
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
          <dd>{request.total_tokens}</dd>
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

      <JsonBlock title="Prompt" value={request.prompt} />
      <JsonBlock title="Response" value={request.response} />
      <JsonBlock title="Metadata" value={request.request_metadata || {}} />
    </aside>
  );
}

function App() {
  const [summary, setSummary] = React.useState(null);
  const [requests, setRequests] = React.useState([]);
  const [selected, setSelected] = React.useState(null);
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summaryResponse, requestResponse] = await Promise.all([
        fetch(`${API_BASE}/api/metrics/summary?hours=24`),
        fetch(`${API_BASE}/api/requests?limit=100`),
      ]);
      if (!summaryResponse.ok || !requestResponse.ok) {
        throw new Error("Backend returned an error");
      }
      const summaryJson = await summaryResponse.json();
      const requestJson = await requestResponse.json();
      setSummary(summaryJson);
      setRequests(requestJson.requests || []);
      setSelected((current) => current || requestJson.requests?.[0] || null);
    } catch (err) {
      setError(err.message || "Unable to load LogLlama data");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
    const interval = window.setInterval(load, 10000);
    return () => window.clearInterval(interval);
  }, [load]);

  const filtered = requests.filter((request) => {
    const haystack = [
      request.model,
      request.operation,
      request.status,
      request.request_metadata?.route,
      request.request_metadata?.user_id,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query.toLowerCase());
  });

  return (
    <main className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <BrandMark />
          <div>
            <strong>LogLlama</strong>
            <span>AI debug console</span>
          </div>
        </div>

        <nav className="navRail" aria-label="Primary">
          <a className="active" href="/">
            <TerminalSquare size={16} />
            Traces
          </a>
          <a href="/">
            <Gauge size={16} />
            Metrics
          </a>
          <a href="/">
            <Layers3 size={16} />
            Prompts
          </a>
          <a href="/">
            <Sparkles size={16} />
            Diagnosis
          </a>
        </nav>

        <div className="sidebarMeta">
          <span>Project</span>
          <strong>Development</strong>
          <code>llama-dev-key</code>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <span className="eyebrow">Live local capture</span>
            <h1>Traces</h1>
            <p>Monitor OpenAI requests, latency, cost, tokens, prompts, and responses.</p>
          </div>
          <button className="refreshButton" onClick={load} aria-label="Refresh data">
            <RefreshCw size={16} />
            <span>{loading ? "Syncing" : "Refresh"}</span>
          </button>
        </header>

        {error && <div className="banner">{error}</div>}

        <section className="metricsGrid">
          <MetricCard
            icon={Activity}
            label="Requests"
            value={summary?.total_requests ?? 0}
            detail="Last 24 hours"
          />
          <MetricCard
            icon={Coins}
            label="Spend"
            value={formatMoney(summary?.total_cost_usd)}
            detail="Estimated model cost"
          />
          <MetricCard
            icon={Clock3}
            label="Latency"
            value={`${Math.round(summary?.avg_latency_ms || 0)} ms`}
            detail="Average response time"
          />
          <MetricCard
            icon={AlertTriangle}
            label="Error rate"
            value={`${Math.round((summary?.error_rate || 0) * 100)}%`}
            detail="Failed requests"
            tone={summary?.error_rate ? "warning" : ""}
          />
        </section>

        <section className="workspace">
          <div className="requestPanel">
            <div className="panelHeader">
              <div>
                <h2>Request stream</h2>
                <p>{filtered.length} traces shown</p>
              </div>
              <label className="search">
                <Search size={15} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search model, route, user"
                />
              </label>
            </div>

            <div className="requestHeader">
              <span>Status</span>
              <span>Model</span>
              <span>Route</span>
              <span>Latency</span>
              <span>Tokens</span>
              <span>Cost</span>
              <span>Captured</span>
            </div>
            <div className="requestList">
              {filtered.map((request) => (
                <RequestRow
                  key={request.id}
                  request={request}
                  selected={selected?.id === request.id}
                  onSelect={setSelected}
                />
              ))}
              {!filtered.length && <div className="emptyList">No matching traces</div>}
            </div>
          </div>
          <RequestDetail request={selected} />
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
