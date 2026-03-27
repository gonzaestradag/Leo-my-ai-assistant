import { useState, useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { label: "Dashboard",  to: "/" },
  { label: "Salud",      to: "/salud" },
  { label: "Agentes IA", to: "/agentes" },
  { label: "Chat",       to: "/chat" },
  { label: "Inversiones",to: "/inversiones" },
];

// ─── MOCK DATA (replace each section with your Flask API calls) ───────────────
const API_BASE = "https://leo-my-ai-assistant.onrender.com"; // tu Render URL

const MOCK = {
  user: { name: "Gonzalo", avatar: "GE", location: "Monterrey, MX" },
  weather: { temp: 28, condition: "Soleado", icon: "☀️", humidity: 45, wind: 14 },
  time: new Date(),
  calendar: [
    { id: 1, time: "09:00", title: "Llamada con equipo", color: "#2563EB" },
    { id: 2, time: "11:30", title: "Clase de Finanzas", color: "#7C3AED" },
    { id: 3, time: "14:00", title: "Entrenamiento Hyrox", color: "#059669" },
    { id: 4, time: "17:00", title: "Revisión de gastos", color: "#D97706" },
  ],
  todos: [
    { id: 1, text: "Terminar caso de estudio", done: false, priority: "alta" },
    { id: 2, text: "Llamar a dentista", done: true, priority: "media" },
    { id: 3, text: "Revisar inversiones", done: false, priority: "alta" },
    { id: 4, text: "Pagar tarjeta AMEX", done: false, priority: "media" },
    { id: 5, text: "Preparar presentación", done: false, priority: "baja" },
  ],
  health: {
    sleep: 7.2, sleepGoal: 8,
    calories: 1840, caloriesGoal: 2200,
    mood: 4, moodMax: 5,
    steps: 6800, stepsGoal: 10000,
    water: 1.8, waterGoal: 3,
  },
  gmail: [
    { id: 1, from: "Profesor García", subject: "Entrega Caso #3 - Viernes", unread: true, time: "8:42" },
    { id: 2, from: "BBVA Bancomer", subject: "Resumen de cuenta disponible", unread: true, time: "7:15" },
    { id: 3, from: "GitHub", subject: "Security alert on leo-my-ai", unread: false, time: "Ayer" },
    { id: 4, from: "Papá", subject: "Re: Cena del domingo", unread: false, time: "Ayer" },
  ],
  expenses: {
    total: 8450, budget: 12000,
    categories: [
      { name: "Comida", amount: 2100, color: "#2563EB" },
      { name: "Transporte", amount: 980, color: "#7C3AED" },
      { name: "Escuela", amount: 3200, color: "#059669" },
      { name: "Ocio", amount: 1470, color: "#D97706" },
      { name: "Otros", amount: 700, color: "#6B7280" },
    ],
  },
  goals: [
    { id: 1, title: "Fondo de emergencia", current: 45000, target: 60000, color: "#2563EB" },
    { id: 2, title: "Hyrox Sub-1:15", current: 82, target: 100, unit: "%", color: "#059669" },
    { id: 3, title: "Portafolio inversión", current: 28500, target: 50000, color: "#7C3AED" },
  ],
  briefing: "Buenos días Gonzalo. Tienes 4 eventos hoy. El clima está despejado a 28°C. Entrega de caso de estudio el viernes — recuerda revisar las finanzas de la empresa. Tu entrenamiento Hyrox está programado a las 2 PM.",
};

// ─── HELPERS ─────────────────────────────────────────────────────────────────
function useTime() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  return now;
}

function pad(n) { return String(n).padStart(2, "0"); }

function Ring({ value, max, size = 56, stroke = 5, color = "#2563EB", children }) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(value / max, 1);
  return (
    <svg width={size} height={size} style={{ display: "block" }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(148,163,184,.2)" strokeWidth={stroke}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={`${circ * pct} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: "stroke-dasharray .6s cubic-bezier(.4,0,.2,1)" }}
      />
      {children && (
        <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
          style={{ fontSize: 11, fontWeight: 600, fill: color, fontFamily: "inherit" }}>
          {children}
        </text>
      )}
    </svg>
  );
}

function Bar({ value, max, color = "#2563EB", height = 6 }) {
  const pct = Math.min(value / max, 1) * 100;
  return (
    <div style={{ background: "rgba(148,163,184,.15)", borderRadius: 9, height, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 9,
        transition: "width .6s cubic-bezier(.4,0,.2,1)" }}/>
    </div>
  );
}

// ─── PANELS ──────────────────────────────────────────────────────────────────

function PanelWrapper({ title, icon, children, accent = "#2563EB", onExpand, style = {} }) {
  return (
    <div onClick={onExpand} style={{
      background: "#FFFFFF",
      border: "1px solid #E2E8F0",
      borderRadius: 16,
      padding: "20px 22px",
      cursor: onExpand ? "pointer" : "default",
      transition: "box-shadow .2s, transform .2s",
      position: "relative",
      overflow: "hidden",
      ...style,
    }}
      onMouseEnter={e => { if (onExpand) { e.currentTarget.style.boxShadow = "0 8px 32px rgba(37,99,235,.10)"; e.currentTarget.style.transform = "translateY(-2px)"; }}}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.transform = "none"; }}
    >
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: accent, borderRadius: "16px 0 0 16px" }}/>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 15 }}>{icon}</span>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".08em", color: "#94A3B8", textTransform: "uppercase" }}>{title}</span>
        {onExpand && <span style={{ marginLeft: "auto", fontSize: 11, color: "#94A3B8" }}>↗ expandir</span>}
      </div>
      {children}
    </div>
  );
}

function HeaderPanel({ data, now }) {
  const days = ["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"];
  const months = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
  return (
    <div style={{
      background: "linear-gradient(135deg, #0F172A 0%, #1E3A5F 60%, #1e40af 100%)",
      borderRadius: 20, padding: "28px 32px",
      color: "#fff", display: "flex", alignItems: "center", justifyContent: "space-between",
      gap: 24, marginBottom: 20,
    }}>
      <div>
        <div style={{ fontSize: 13, color: "#93C5FD", marginBottom: 6, letterSpacing: ".05em" }}>
          {days[now.getDay()]}, {now.getDate()} de {months[now.getMonth()]} {now.getFullYear()}
        </div>
        <div style={{ fontSize: 42, fontWeight: 700, letterSpacing: "-.02em", lineHeight: 1,
          fontFamily: "'SF Mono', 'Fira Code', monospace" }}>
          {pad(now.getHours())}:{pad(now.getMinutes())}
          <span style={{ fontSize: 22, color: "#93C5FD", marginLeft: 4 }}>{pad(now.getSeconds())}</span>
        </div>
        <div style={{ marginTop: 10, fontSize: 14, color: "#BFDBFE", maxWidth: 480, lineHeight: 1.5 }}>
          {data.briefing}
        </div>
      </div>
      <div style={{ textAlign: "center", flexShrink: 0 }}>
        <div style={{ fontSize: 48 }}>{data.weather.icon}</div>
        <div style={{ fontSize: 30, fontWeight: 700, lineHeight: 1 }}>{data.weather.temp}°C</div>
        <div style={{ fontSize: 13, color: "#93C5FD" }}>{data.weather.condition}</div>
        <div style={{ fontSize: 12, color: "#60A5FA", marginTop: 4 }}>
          💧{data.weather.humidity}% · 💨{data.weather.wind}km/h
        </div>
      </div>
    </div>
  );
}

function CalendarPanel({ events, onExpand }) {
  return (
    <PanelWrapper title="Agenda hoy" icon="📅" accent="#2563EB" onExpand={onExpand}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {events.map(ev => (
          <div key={ev.id} style={{ display: "flex", alignItems: "center", gap: 10,
            padding: "8px 10px", borderRadius: 8, background: "#F8FAFC" }}>
            <div style={{ width: 3, height: 32, borderRadius: 4, background: ev.color, flexShrink: 0 }}/>
            <div>
              <div style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600 }}>{ev.time}</div>
              <div style={{ fontSize: 13, color: "#1E293B", fontWeight: 500 }}>{ev.title}</div>
            </div>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function TodoPanel({ todos, onExpand }) {
  const pending = todos.filter(t => !t.done).length;
  const colors = { alta: "#EF4444", media: "#F59E0B", baja: "#10B981" };
  return (
    <PanelWrapper title="To-do list" icon="✅" accent="#7C3AED" onExpand={onExpand}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: "#1E293B" }}>{pending}</span>
        <span style={{ fontSize: 13, color: "#94A3B8" }}>pendientes de {todos.length}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {todos.slice(0, 4).map(t => (
          <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 8, opacity: t.done ? .45 : 1 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: colors[t.priority], flexShrink: 0 }}/>
            <span style={{ fontSize: 13, color: "#334155", textDecoration: t.done ? "line-through" : "none",
              flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.text}</span>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function HealthPanel({ health, onExpand }) {
  const metrics = [
    { label: "Sueño", value: health.sleep, max: health.sleepGoal, unit: "h", color: "#7C3AED" },
    { label: "Calorías", value: health.calories, max: health.caloriesGoal, unit: "kcal", color: "#EF4444" },
    { label: "Pasos", value: health.steps, max: health.stepsGoal, unit: "", color: "#10B981" },
    { label: "Agua", value: health.water, max: health.waterGoal, unit: "L", color: "#2563EB" },
  ];
  return (
    <PanelWrapper title="Salud" icon="💪" accent="#10B981" onExpand={onExpand}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {metrics.map(m => (
          <div key={m.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Ring value={m.value} max={m.max} size={48} stroke={5} color={m.color}>
              {Math.round((m.value/m.max)*100)}%
            </Ring>
            <div>
              <div style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600 }}>{m.label}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#1E293B" }}>{m.value}{m.unit}</div>
              <div style={{ fontSize: 11, color: "#CBD5E1" }}>/ {m.max}{m.unit}</div>
            </div>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function GmailPanel({ emails, onExpand }) {
  return (
    <PanelWrapper title="Gmail" icon="📧" accent="#EF4444" onExpand={onExpand}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {emails.map(e => (
          <div key={e.id} style={{ display: "flex", alignItems: "center", gap: 10,
            padding: "7px 0", borderBottom: "1px solid #F1F5F9" }}>
            {e.unread && <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#2563EB", flexShrink: 0 }}/>}
            {!e.unread && <div style={{ width: 7, height: 7, flexShrink: 0 }}/>}
            <div style={{ flex: 1, overflow: "hidden" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, fontWeight: e.unread ? 700 : 400, color: "#334155",
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.from}</span>
                <span style={{ fontSize: 11, color: "#94A3B8", flexShrink: 0, marginLeft: 8 }}>{e.time}</span>
              </div>
              <div style={{ fontSize: 12, color: "#94A3B8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.subject}</div>
            </div>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function ExpensesPanel({ expenses, onExpand }) {
  const pct = Math.round((expenses.total / expenses.budget) * 100);
  return (
    <PanelWrapper title="Gastos" icon="💳" accent="#D97706" onExpand={onExpand}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 26, fontWeight: 700, color: "#1E293B" }}>
          ${expenses.total.toLocaleString()}
        </span>
        <span style={{ fontSize: 13, color: "#94A3B8" }}>/ ${expenses.budget.toLocaleString()}</span>
      </div>
      <Bar value={expenses.total} max={expenses.budget} color="#D97706" height={8}/>
      <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 6, marginBottom: 14 }}>{pct}% del presupuesto</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {expenses.categories.map(c => (
          <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: c.color, flexShrink: 0 }}/>
            <span style={{ fontSize: 12, color: "#475569", flex: 1 }}>{c.name}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#1E293B" }}>${c.amount.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function GoalsPanel({ goals, onExpand }) {
  return (
    <PanelWrapper title="Metas" icon="🎯" accent="#059669" onExpand={onExpand}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
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
                <span style={{ fontSize: 11, color: "#94A3B8" }}>
                  {g.unit === "%" ? `${g.current}%` : `$${g.current.toLocaleString()}`}
                </span>
                <span style={{ fontSize: 11, color: "#CBD5E1" }}>
                  {g.unit === "%" ? `${g.target}%` : `$${g.target.toLocaleString()}`}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </PanelWrapper>
  );
}

// ─── MODAL (zoom al hacer clic) ───────────────────────────────────────────────
function Modal({ panel, onClose }) {
  if (!panel) return null;
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(15,23,42,.65)", backdropFilter: "blur(4px)",
      zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: "#fff", borderRadius: 20, padding: "28px 32px",
        width: "100%", maxWidth: 520, boxShadow: "0 32px 80px rgba(15,23,42,.25)",
        animation: "zoomIn .2s cubic-bezier(.4,0,.2,1)",
        maxHeight: "85vh", overflowY: "auto",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#0F172A" }}>{panel.title}</span>
          <button onClick={onClose} style={{
            background: "#F1F5F9", border: "none", borderRadius: 8, padding: "4px 10px",
            cursor: "pointer", fontSize: 13, color: "#64748B"
          }}>✕ cerrar</button>
        </div>
        {panel.content}
      </div>
    </div>
  );
}

// ─── MODAL CONTENT ─────────────────────────────────────────────────────────
function CalendarExpanded({ events }) {
  return (
    <div>
      {events.map(ev => (
        <div key={ev.id} style={{ display: "flex", gap: 14, padding: "14px 0", borderBottom: "1px solid #F1F5F9" }}>
          <div style={{ width: 4, borderRadius: 4, background: ev.color, flexShrink: 0 }}/>
          <div>
            <div style={{ fontSize: 12, color: "#94A3B8", fontWeight: 700, marginBottom: 2 }}>{ev.time}</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "#1E293B" }}>{ev.title}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TodoExpanded({ todos }) {
  const colors = { alta: "#EF4444", media: "#F59E0B", baja: "#10B981" };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {todos.map(t => (
        <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 10,
          padding: "10px 12px", borderRadius: 8,
          background: t.done ? "#F8FAFC" : "#fff",
          border: "1px solid #E2E8F0",
          opacity: t.done ? .6 : 1 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: colors[t.priority], flexShrink: 0 }}/>
          <span style={{ flex: 1, fontSize: 14, color: "#334155",
            textDecoration: t.done ? "line-through" : "none" }}>{t.text}</span>
          <span style={{ fontSize: 11, color: colors[t.priority], fontWeight: 700,
            background: `${colors[t.priority]}18`, padding: "2px 8px", borderRadius: 6 }}>{t.priority}</span>
        </div>
      ))}
    </div>
  );
}

// ─── MAIN DASHBOARD ─────────────────────────────────────────────────────────
export default function JarvisDashboard() {
  const now = useTime();
  const location = useLocation();
  const [modal, setModal] = useState(null);
  const data = MOCK;

  const open = (title, content) => setModal({ title, content });

  return (
    <div style={{
      minHeight: "100vh",
      background: "#F0F4F8",
      fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
      padding: "24px",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        @keyframes zoomIn { from { opacity:0; transform:scale(.94) } to { opacity:1; transform:scale(1) } }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
      `}</style>

      {/* Header */}
      <div style={{ maxWidth: 1280, margin: "0 auto" }}>
        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 10,
              background: "linear-gradient(135deg, #1E3A5F, #2563EB)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 16, fontWeight: 800, color: "#fff", letterSpacing: "-.02em"
            }}>J</div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#0F172A", lineHeight: 1 }}>Jarvis</div>
              <div style={{ fontSize: 12, color: "#94A3B8" }}>Personal AI · {data.user.location}</div>
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

        {/* Header cockpit banner */}
        <HeaderPanel data={data} now={now}/>

        {/* Main grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          <CalendarPanel events={data.calendar}
            onExpand={() => open("📅 Agenda completa", <CalendarExpanded events={data.calendar}/>)}/>
          <TodoPanel todos={data.todos}
            onExpand={() => open("✅ To-do list completa", <TodoExpanded todos={data.todos}/>)}/>
          <HealthPanel health={data.health}
            onExpand={() => open("💪 Panel de salud", <div style={{fontSize:14,color:"#64748B"}}>Vista detallada de salud — conectar a API Flask /health</div>)}/>
          <GmailPanel emails={data.gmail}
            onExpand={() => open("📧 Gmail", <div style={{fontSize:14,color:"#64748B"}}>Vista completa de Gmail — conectar a API Flask /gmail</div>)}/>
          <ExpensesPanel expenses={data.expenses}
            onExpand={() => open("💳 Control de gastos", <div style={{fontSize:14,color:"#64748B"}}>Vista detallada de gastos — conectar a API Flask /expenses</div>)}/>
          <GoalsPanel goals={data.goals}
            onExpand={() => open("🎯 Metas y objetivos", <div style={{fontSize:14,color:"#64748B"}}>Vista detallada de metas — conectar a API Flask /goals</div>)}/>
        </div>

        {/* Footer */}
        <div style={{ textAlign: "center", marginTop: 24, fontSize: 12, color: "#CBD5E1" }}>
          Jarvis Dashboard · Última sync: {pad(now.getHours())}:{pad(now.getMinutes())} ·
          <span style={{ color: "#10B981", marginLeft: 6 }}>● Conectado</span>
        </div>
      </div>

      {/* Modal zoom */}
      <Modal panel={modal} onClose={() => setModal(null)}/>
    </div>
  );
}
