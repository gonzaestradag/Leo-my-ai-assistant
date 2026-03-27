import { useState, useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { label: "Dashboard",  to: "/" },
  { label: "Salud",      to: "/salud" },
  { label: "Agentes IA", to: "/agentes" },
  { label: "Chat",       to: "/chat" },
  { label: "Inversiones",to: "/inversiones" },
];

const API_BASE = "https://leo-my-ai-assistant.onrender.com";

function pad(n) { return String(n).padStart(2, "0"); }
function fmt(n) { return n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function fmtPct(n) { return (n >= 0 ? "+" : "") + n.toFixed(2) + "%"; }

function useTime() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  return now;
}

// ─── MOCK DATA ────────────────────────────────────────────────────────────────
// Basado en la tabla portfolio (ticker, shares, avg_price) + precios simulados
const HOLDINGS = [
  {
    ticker: "CETES",
    nombre: "CETES 90 días",
    tipo: "Renta Fija",
    shares: 1,
    avg_price: 12000,
    current_price: 12540,
    color: "#2563EB",
    icon: "🏛️",
  },
  {
    ticker: "VOO",
    nombre: "Vanguard S&P 500 ETF",
    tipo: "ETF USA",
    shares: 2.5,
    avg_price: 3280,
    current_price: 3610,
    color: "#7C3AED",
    icon: "📈",
  },
  {
    ticker: "NVDA",
    nombre: "NVIDIA Corporation",
    tipo: "Acción",
    shares: 1,
    avg_price: 4500,
    current_price: 5810,
    color: "#10B981",
    icon: "💻",
  },
  {
    ticker: "AAPL",
    nombre: "Apple Inc.",
    tipo: "Acción",
    shares: 2,
    avg_price: 1750,
    current_price: 1680,
    color: "#6366F1",
    icon: "🍎",
  },
  {
    ticker: "GBM+",
    nombre: "GBM+ Portafolio Flex",
    tipo: "Fondo",
    shares: 1,
    avg_price: 2800,
    current_price: 3020,
    color: "#D97706",
    icon: "💼",
  },
];

const GOALS = [
  { id: 1, title: "Portafolio inversión", current: 28500, target: 50000, color: "#7C3AED" },
  { id: 2, title: "Fondo de emergencia", current: 45000, target: 60000, color: "#2563EB" },
  { id: 3, title: "CETES meta anual", current: 12540, target: 20000, color: "#059669" },
];

const HISTORY = [
  { mes: "Oct", valor: 24100 },
  { mes: "Nov", valor: 25400 },
  { mes: "Dic", valor: 23800 },
  { mes: "Ene", valor: 26200 },
  { mes: "Feb", valor: 27500 },
  { mes: "Mar", valor: 28500 },
];

const INSIGHTS = [
  { icon: "📊", text: "NVDA lidera tu portafolio con +29.1% desde tu entrada. Considera tomar utilidades parciales." },
  { icon: "⚠️", text: "AAPL está en negativo (-4.0%). Evalúa si mantener o promediar a la baja." },
  { icon: "💡", text: "Tu exposición a renta fija (CETES) es 44%. Considera aumentar renta variable para tu horizonte a largo plazo." },
  { icon: "🎯", text: "Vas en 57% de tu meta de portafolio ($50,000). A este ritmo la alcanzarás en ~8 meses." },
];

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function getStats(holdings) {
  const totalInvertido = holdings.reduce((s, h) => s + h.shares * h.avg_price, 0);
  const totalActual = holdings.reduce((s, h) => s + h.shares * h.current_price, 0);
  const ganancia = totalActual - totalInvertido;
  const pct = (ganancia / totalInvertido) * 100;
  return { totalInvertido, totalActual, ganancia, pct };
}

// ─── COMPONENTS ──────────────────────────────────────────────────────────────

function Bar({ value, max, color = "#2563EB", height = 6 }) {
  const pct = Math.min(value / max, 1) * 100;
  return (
    <div style={{ background: "rgba(148,163,184,.15)", borderRadius: 9, height, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 9,
        transition: "width .6s cubic-bezier(.4,0,.2,1)" }}/>
    </div>
  );
}

function PanelWrapper({ title, icon, children, accent = "#2563EB", style = {} }) {
  return (
    <div style={{
      background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 16,
      padding: "20px 22px", position: "relative", overflow: "hidden", ...style,
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%",
        background: accent, borderRadius: "16px 0 0 16px" }}/>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <span style={{ fontSize: 15 }}>{icon}</span>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".08em",
          color: "#94A3B8", textTransform: "uppercase" }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

function StatCard({ icon, label, value, sub, accent = "#2563EB", positive }) {
  return (
    <div style={{
      background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 14,
      padding: "16px 20px", position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%",
        background: accent, borderRadius: "14px 0 0 14px" }}/>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div style={{ width: 36, height: 36, borderRadius: 9, background: `${accent}14`,
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>{icon}</div>
        <span style={{ fontSize: 11, fontWeight: 700, color: "#94A3B8",
          textTransform: "uppercase", letterSpacing: ".07em" }}>{label}</span>
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: "#0F172A", lineHeight: 1 }}>{value}</div>
      {sub !== undefined && (
        <div style={{ fontSize: 12, marginTop: 4,
          color: positive === true ? "#059669" : positive === false ? "#EF4444" : "#94A3B8",
          fontWeight: positive !== undefined ? 600 : 400 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function Sparkline({ data, color = "#2563EB" }) {
  const w = 260, h = 60, pad = 8;
  const vals = data.map(d => d.valor);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const xs = vals.map((_, i) => pad + (i / (vals.length - 1)) * (w - pad * 2));
  const ys = vals.map(v => h - pad - ((v - min) / range) * (h - pad * 2));
  const path = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ");
  const fill = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ")
    + ` L${xs[xs.length - 1]},${h - pad} L${xs[0]},${h - pad} Z`;

  return (
    <svg width={w} height={h} style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id="spGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.18"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={fill} fill="url(#spGrad)"/>
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      {xs.map((x, i) => (
        <circle key={i} cx={x} cy={ys[i]} r={i === vals.length - 1 ? 4 : 2.5}
          fill={i === vals.length - 1 ? color : "#fff"}
          stroke={color} strokeWidth="1.5"/>
      ))}
    </svg>
  );
}

function HoldingsTable({ holdings }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Header */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
        gap: 8, padding: "6px 10px", marginBottom: 4 }}>
        {["Activo", "Tipo", "Invertido", "Valor actual", "P&L"].map(h => (
          <span key={h} style={{ fontSize: 10, fontWeight: 700, color: "#94A3B8",
            textTransform: "uppercase", letterSpacing: ".07em" }}>{h}</span>
        ))}
      </div>
      {holdings.map(h => {
        const invertido = h.shares * h.avg_price;
        const actual = h.shares * h.current_price;
        const pnl = actual - invertido;
        const pnlPct = (pnl / invertido) * 100;
        const pos = pnl >= 0;
        return (
          <div key={h.ticker} style={{
            display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
            gap: 8, padding: "10px 10px", borderRadius: 9,
            transition: "background .15s",
          }}
            onMouseEnter={e => { e.currentTarget.style.background = "#F8FAFC"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
          >
            {/* Activo */}
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: `${h.color}14`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 14, flexShrink: 0 }}>{h.icon}</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#1E293B" }}>{h.ticker}</div>
                <div style={{ fontSize: 11, color: "#94A3B8",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  maxWidth: 120 }}>{h.nombre}</div>
              </div>
            </div>
            {/* Tipo */}
            <div style={{ display: "flex", alignItems: "center" }}>
              <span style={{ fontSize: 11, fontWeight: 500, color: h.color,
                background: `${h.color}14`, padding: "2px 8px", borderRadius: 6 }}>{h.tipo}</span>
            </div>
            {/* Invertido */}
            <div style={{ display: "flex", alignItems: "center" }}>
              <span style={{ fontSize: 13, color: "#475569" }}>${fmt(invertido)}</span>
            </div>
            {/* Valor actual */}
            <div style={{ display: "flex", alignItems: "center" }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#1E293B" }}>${fmt(actual)}</span>
            </div>
            {/* P&L */}
            <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
              <span style={{ fontSize: 13, fontWeight: 700,
                color: pos ? "#059669" : "#EF4444" }}>
                {pos ? "+" : ""}${fmt(Math.abs(pnl))}
              </span>
              <span style={{ fontSize: 11, color: pos ? "#059669" : "#EF4444" }}>
                {fmtPct(pnlPct)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AllocationPanel({ holdings }) {
  const totalActual = holdings.reduce((s, h) => s + h.shares * h.current_price, 0);
  return (
    <PanelWrapper title="Distribución" icon="🥧" accent="#7C3AED">
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {holdings.map(h => {
          const val = h.shares * h.current_price;
          const pct = (val / totalActual) * 100;
          return (
            <div key={h.ticker}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <span style={{ fontSize: 13 }}>{h.icon}</span>
                  <span style={{ fontSize: 13, fontWeight: 500, color: "#334155" }}>{h.ticker}</span>
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                  <span style={{ fontSize: 12, color: "#94A3B8" }}>${fmt(val)}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: h.color }}>{pct.toFixed(1)}%</span>
                </div>
              </div>
              <Bar value={val} max={totalActual} color={h.color} height={5}/>
            </div>
          );
        })}
      </div>
    </PanelWrapper>
  );
}

function GoalsPanel({ goals }) {
  return (
    <PanelWrapper title="Metas financieras" icon="🎯" accent="#059669">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {goals.map(g => {
          const pct = Math.round((g.current / g.target) * 100);
          return (
            <div key={g.id}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "#334155" }}>{g.title}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: g.color }}>{pct}%</span>
              </div>
              <Bar value={g.current} max={g.target} color={g.color} height={6}/>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                <span style={{ fontSize: 11, color: "#94A3B8" }}>${g.current.toLocaleString()}</span>
                <span style={{ fontSize: 11, color: "#CBD5E1" }}>${g.target.toLocaleString()}</span>
              </div>
            </div>
          );
        })}
      </div>
    </PanelWrapper>
  );
}

function InsightsPanel() {
  return (
    <PanelWrapper title="Insights de Jarvis" icon="🤖" accent="#2563EB">
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {INSIGHTS.map((ins, i) => (
          <div key={i} style={{
            display: "flex", gap: 10, padding: "10px 12px",
            background: "#F8FAFC", borderRadius: 9, border: "1px solid #F1F5F9",
          }}>
            <span style={{ fontSize: 16, flexShrink: 0 }}>{ins.icon}</span>
            <span style={{ fontSize: 13, color: "#334155", lineHeight: 1.55 }}>{ins.text}</span>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hola Gonzalo 👋 Pregúntame sobre tu portafolio, rendimientos o estrategia de inversión.", time: "" },
  ]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    const t = `${pad(new Date().getHours())}:${pad(new Date().getMinutes())}`;
    setInput("");
    setMessages(prev => [...prev, { role: "user", text, time: t }]);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: "inversiones_web" }),
      });
      const data = await res.json();
      const reply = data.reply || data.error || "Sin respuesta.";
      setMessages(prev => [...prev, {
        role: "assistant", text: reply,
        time: `${pad(new Date().getHours())}:${pad(new Date().getMinutes())}`,
      }]);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", text: "Error de conexión.", time: "" }]);
    } finally {
      setLoading(false);
    }
  }

  const SUGGESTIONS = ["¿Cómo va mi portafolio?", "¿Debería vender AAPL?", "¿Cuánto he ganado este mes?", "Recomiéndame una estrategia"];

  return (
    <PanelWrapper title="Consultar a Jarvis" icon="💬" accent="#2563EB"
      style={{ display: "flex", flexDirection: "column", minHeight: 360 }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", maxHeight: 220, marginBottom: 12,
        display: "flex", flexDirection: "column", gap: 8 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "85%", padding: "8px 12px", borderRadius: m.role === "user"
                ? "12px 12px 3px 12px" : "12px 12px 12px 3px",
              background: m.role === "user"
                ? "linear-gradient(135deg,#1E3A5F,#2563EB)" : "#F1F5F9",
              color: m.role === "user" ? "#fff" : "#1E293B",
              fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap",
            }}>
              {m.text}
              {m.time && <div style={{ fontSize: 10, marginTop: 3, opacity: .55, textAlign: "right" }}>{m.time}</div>}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", gap: 5, padding: "8px 12px", background: "#F1F5F9",
            borderRadius: "12px 12px 12px 3px", width: "fit-content" }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{ width: 5, height: 5, borderRadius: "50%", background: "#94A3B8",
                animation: "bounce .9s infinite", animationDelay: `${i * 0.18}s` }}/>
            ))}
          </div>
        )}
        <div ref={bottomRef}/>
      </div>

      {/* Suggestions */}
      {messages.length === 1 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {SUGGESTIONS.map(s => (
            <button key={s} onClick={() => setInput(s)} style={{
              padding: "4px 10px", borderRadius: 20, border: "1px solid #E2E8F0",
              background: "#F8FAFC", color: "#475569", fontSize: 11, cursor: "pointer",
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "#2563EB"; e.currentTarget.style.color = "#2563EB"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "#E2E8F0"; e.currentTarget.style.color = "#475569"; }}
            >{s}</button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{ display: "flex", gap: 8 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") send(); }}
          placeholder="Pregunta sobre inversiones…"
          style={{ flex: 1, padding: "8px 12px", borderRadius: 9, border: "1px solid #E2E8F0",
            fontSize: 13, color: "#1E293B", fontFamily: "inherit", outline: "none" }}
          onFocus={e => { e.target.style.borderColor = "#2563EB"; }}
          onBlur={e => { e.target.style.borderColor = "#E2E8F0"; }}
        />
        <button onClick={send} disabled={!input.trim() || loading} style={{
          padding: "8px 16px", borderRadius: 9, border: "none",
          background: input.trim() && !loading ? "#2563EB" : "#E2E8F0",
          color: input.trim() && !loading ? "#fff" : "#94A3B8",
          fontSize: 13, fontWeight: 600, cursor: input.trim() && !loading ? "pointer" : "not-allowed",
        }}>
          {loading ? "…" : "→"}
        </button>
      </div>
    </PanelWrapper>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function JarvisInversiones() {
  const now = useTime();
  const location = useLocation();
  const stats = getStats(HOLDINGS);
  const totalActual = HOLDINGS.reduce((s, h) => s + h.shares * h.current_price, 0);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#F0F4F8",
      fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
      padding: "24px",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; }
        @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)} }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
      `}</style>

      <div style={{ maxWidth: 1280, margin: "0 auto" }}>

        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: "linear-gradient(135deg, #1E3A5F, #2563EB)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 16, fontWeight: 800, color: "#fff",
            }}>J</div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#0F172A", lineHeight: 1 }}>Jarvis</div>
              <div style={{ fontSize: 12, color: "#94A3B8" }}>Personal AI · Monterrey, MX</div>
            </div>
          </div>
          <nav style={{ display: "flex", gap: 6 }}>
            {NAV_ITEMS.map(({ label, to }) => {
              const active = location.pathname === to;
              return (
                <Link key={label} to={to} style={{
                  padding: "6px 14px", borderRadius: 8, border: "1px solid",
                  borderColor: active ? "#2563EB" : "#E2E8F0",
                  background: active ? "#2563EB" : "#fff",
                  color: active ? "#fff" : "#64748B",
                  fontSize: 13, fontWeight: 500, cursor: "pointer",
                  transition: "all .15s",
                  textDecoration: "none",
                }}>{label}</Link>
              );
            })}
          </nav>
        </div>

        {/* Header banner */}
        <div style={{
          background: "linear-gradient(135deg, #0F172A 0%, #1E3A5F 60%, #1e40af 100%)",
          borderRadius: 20, padding: "28px 32px",
          color: "#fff", display: "flex", alignItems: "center", justifyContent: "space-between",
          gap: 24, marginBottom: 20,
        }}>
          <div>
            <div style={{ fontSize: 13, color: "#93C5FD", marginBottom: 4, letterSpacing: ".05em" }}>
              Portafolio de inversión
            </div>
            <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: "-.02em", lineHeight: 1,
              fontFamily: "'SF Mono','Fira Code',monospace" }}>
              ${fmt(stats.totalActual)}
              <span style={{ fontSize: 16, color: "#93C5FD", marginLeft: 6 }}>MXN</span>
            </div>
            <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 16 }}>
              <span style={{
                fontSize: 15, fontWeight: 700,
                color: stats.ganancia >= 0 ? "#4ADE80" : "#F87171",
              }}>
                {stats.ganancia >= 0 ? "▲" : "▼"} ${fmt(Math.abs(stats.ganancia))} ({fmtPct(stats.pct)})
              </span>
              <span style={{ fontSize: 13, color: "#BFDBFE" }}>vs costo base ${fmt(stats.totalInvertido)}</span>
            </div>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <Sparkline data={HISTORY} color="#60A5FA"/>
            <div style={{ fontSize: 11, color: "#93C5FD", marginTop: 6 }}>Últimos 6 meses</div>
          </div>
        </div>

        {/* Stat cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
          <StatCard icon="💰" label="Valor actual" value={`$${fmt(stats.totalActual)}`} accent="#2563EB"/>
          <StatCard icon="📈" label="Ganancia total"
            value={`${stats.ganancia >= 0 ? "+" : ""}$${fmt(stats.ganancia)}`}
            sub={fmtPct(stats.pct)}
            accent="#059669" positive={stats.ganancia >= 0}/>
          <StatCard icon="📦" label="Posiciones" value={HOLDINGS.length} accent="#7C3AED"/>
          <StatCard icon="🏆" label="Mejor posición"
            value="NVDA"
            sub="+29.1% · $1,310 ganados"
            accent="#10B981" positive/>
        </div>

        {/* Holdings table — full width */}
        <PanelWrapper title="Mis posiciones" icon="📋" accent="#2563EB" style={{ marginBottom: 16 }}>
          <HoldingsTable holdings={HOLDINGS}/>
        </PanelWrapper>

        {/* 3-col grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
          <AllocationPanel holdings={HOLDINGS}/>
          <GoalsPanel goals={GOALS}/>
          <InsightsPanel/>
        </div>

        {/* Chat — full width */}
        <ChatPanel/>

        {/* Footer */}
        <div style={{ textAlign: "center", marginTop: 20, fontSize: 12, color: "#CBD5E1" }}>
          Jarvis Dashboard · Última sync: {pad(now.getHours())}:{pad(now.getMinutes())} ·
          <span style={{ color: "#10B981", marginLeft: 6 }}>● Conectado</span>
          <span style={{ marginLeft: 12, color: "#CBD5E1" }}>Datos simulados — conectar a API Flask /portfolio</span>
        </div>
      </div>
    </div>
  );
}
