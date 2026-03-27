import { useState, useEffect } from "react";

const API_BASE = "https://leo-my-ai-assistant.onrender.com";

function pad(n) { return String(n).padStart(2, "0"); }

function useTime() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  return now;
}

// ─── AGENT DEFINITIONS ───────────────────────────────────────────────────────
const AGENTS = [
  {
    id: "briefing",
    name: "Morning Briefing",
    icon: "🌅",
    accent: "#2563EB",
    status: "auto",
    statusLabel: "Automático · 07:00",
    description: "Resume tu día cada mañana: clima, agenda, correos urgentes y tareas pendientes vía WhatsApp.",
    tools: ["Resumen diario automático", "Agenda del día", "Correos urgentes", "Tareas pendientes"],
    trigger: "Cron diario",
  },
  {
    id: "calendario",
    name: "Agente Calendario",
    icon: "📅",
    accent: "#2563EB",
    status: "activo",
    statusLabel: "Activo",
    description: "Consulta y crea eventos en Google Calendar usando lenguaje natural.",
    tools: ["get_todays_events · Ver agenda hoy", "create_event · Crear evento"],
    trigger: "Bajo demanda",
  },
  {
    id: "gmail",
    name: "Agente Gmail",
    icon: "📧",
    accent: "#EF4444",
    status: "activo",
    statusLabel: "Activo",
    description: "Lee correos sin leer, filtra urgentes y envía emails desde WhatsApp o el chat web.",
    tools: [
      "get_recent_unread_emails · Correos sin leer",
      "get_urgent_emails · Correos urgentes",
      "send_email · Enviar email directo",
      "send_email_to_contact · Enviar a contacto guardado",
    ],
    trigger: "Bajo demanda",
  },
  {
    id: "comunicaciones",
    name: "Agente Comunicaciones",
    icon: "📱",
    accent: "#7C3AED",
    status: "activo",
    statusLabel: "Activo",
    description: "Gestiona contactos, envía WhatsApps y realiza llamadas de voz a contactos guardados.",
    tools: [
      "save_contact · Guardar contacto",
      "get_contact · Buscar contacto",
      "send_whatsapp_to_contact · Enviar WhatsApp",
      "call_contact · Llamar con mensaje de voz",
    ],
    trigger: "Bajo demanda",
  },
  {
    id: "tareas",
    name: "Agente Tareas",
    icon: "✅",
    accent: "#7C3AED",
    status: "activo",
    statusLabel: "Activo",
    description: "Administra tu lista de pendientes: agrega, consulta y marca tareas como completadas.",
    tools: [
      "add_task · Agregar tarea",
      "get_tasks · Ver pendientes",
      "complete_task · Marcar completada",
    ],
    trigger: "Bajo demanda",
  },
  {
    id: "finanzas",
    name: "Agente Finanzas",
    icon: "💳",
    accent: "#D97706",
    status: "activo",
    statusLabel: "Activo",
    description: "Registra gastos, monitorea presupuesto y lleva control de deudas personales.",
    tools: [
      "add_expense · Registrar gasto",
      "get_expenses · Resumen del día / semana",
      "add_debt · Registrar deuda",
      "get_debts · Ver deudas pendientes",
      "pay_debt · Marcar deuda como pagada",
    ],
    trigger: "Bajo demanda",
  },
  {
    id: "recordatorios",
    name: "Agente Recordatorios & Metas",
    icon: "🎯",
    accent: "#059669",
    status: "activo",
    statusLabel: "Activo",
    description: "Crea recordatorios por fecha y rastrea el avance de tus metas personales.",
    tools: [
      "add_reminder · Agregar recordatorio",
      "get_reminders · Ver próximos recordatorios",
      "add_goal · Crear meta",
      "get_goals · Ver metas activas",
      "update_goal_progress · Actualizar progreso",
    ],
    trigger: "Bajo demanda",
  },
  {
    id: "salud",
    name: "Agente Salud & Hyrox",
    icon: "💪",
    accent: "#10B981",
    status: "activo",
    statusLabel: "Activo",
    description: "Monitorea sueño, calorías, estado de ánimo y medicamentos. Optimizado para entrenamiento Hyrox.",
    tools: [
      "log_sleep · Registrar sueño",
      "log_mood · Registrar estado de ánimo",
      "log_calories · Registrar comida",
      "get_calories_today · Resumen calórico",
      "add_medication · Agregar medicamento",
      "get_health_summary · Resumen de salud",
    ],
    trigger: "Bajo demanda + Cron",
  },
  {
    id: "blackboard",
    name: "Agente Blackboard UDEM",
    icon: "🎓",
    accent: "#6366F1",
    status: "activo",
    statusLabel: "Activo",
    description: "Consulta tareas pendientes y calificaciones de Blackboard Ultra vía API REST con OAuth.",
    tools: [
      "get_bb_assignments · Tareas pendientes",
      "get_bb_grades · Calificaciones",
    ],
    trigger: "Bajo demanda",
  },
];

const STATUS_COLORS = {
  activo: { bg: "#DCFCE7", text: "#166534", dot: "#22C55E" },
  auto: { bg: "#DBEAFE", text: "#1E40AF", dot: "#2563EB" },
  inactivo: { bg: "#F1F5F9", text: "#64748B", dot: "#94A3B8" },
};

// ─── COMPONENTS ──────────────────────────────────────────────────────────────

function StatCard({ icon, label, value, accent = "#2563EB" }) {
  return (
    <div style={{
      background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 14,
      padding: "16px 20px", display: "flex", alignItems: "center", gap: 14,
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: accent, borderRadius: "14px 0 0 14px" }}/>
      <div style={{
        width: 42, height: 42, borderRadius: 11,
        background: `${accent}14`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 18,
      }}>{icon}</div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#0F172A", lineHeight: 1 }}>{value}</div>
        <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 2 }}>{label}</div>
      </div>
    </div>
  );
}

function AgentCard({ agent, onTest }) {
  const [expanded, setExpanded] = useState(false);
  const sc = STATUS_COLORS[agent.status] || STATUS_COLORS.inactivo;

  return (
    <div style={{
      background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 16,
      overflow: "hidden", transition: "box-shadow .2s, transform .2s",
    }}
      onMouseEnter={e => { e.currentTarget.style.boxShadow = "0 8px 28px rgba(37,99,235,.09)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.transform = "none"; }}
    >
      {/* Accent bar */}
      <div style={{ height: 3, background: agent.accent }}/>

      <div style={{ padding: "18px 20px" }}>
        {/* Header row */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: `${agent.accent}14`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 18, flexShrink: 0,
            }}>{agent.icon}</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#0F172A" }}>{agent.name}</div>
              <div style={{ fontSize: 11, color: "#94A3B8", marginTop: 1 }}>{agent.trigger}</div>
            </div>
          </div>
          <div style={{
            display: "flex", alignItems: "center", gap: 5,
            background: sc.bg, padding: "3px 9px", borderRadius: 20, flexShrink: 0,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: sc.dot }}/>
            <span style={{ fontSize: 11, fontWeight: 600, color: sc.text }}>{agent.statusLabel}</span>
          </div>
        </div>

        {/* Description */}
        <p style={{ fontSize: 13, color: "#475569", lineHeight: 1.55, margin: "0 0 12px" }}>
          {agent.description}
        </p>

        {/* Tools list */}
        <div style={{ marginBottom: 14 }}>
          <button onClick={() => setExpanded(v => !v)} style={{
            background: "none", border: "none", padding: 0, cursor: "pointer",
            fontSize: 11, fontWeight: 700, color: "#94A3B8", letterSpacing: ".07em",
            textTransform: "uppercase", display: "flex", alignItems: "center", gap: 5,
          }}>
            <span style={{ transition: "transform .2s", display: "inline-block",
              transform: expanded ? "rotate(90deg)" : "none" }}>▶</span>
            {agent.tools.length} herramienta{agent.tools.length !== 1 ? "s" : ""}
          </button>
          {expanded && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 5,
              animation: "fadeSlideIn .15s ease" }}>
              {agent.tools.map(t => {
                const [tool, desc] = t.split(" · ");
                return (
                  <div key={t} style={{ display: "flex", alignItems: "baseline", gap: 8,
                    padding: "5px 8px", background: "#F8FAFC", borderRadius: 7,
                    border: "1px solid #F1F5F9" }}>
                    <code style={{ fontSize: 11, fontFamily: "'SF Mono','Fira Code',monospace",
                      color: agent.accent, fontWeight: 600, flexShrink: 0 }}>{tool}</code>
                    {desc && <span style={{ fontSize: 12, color: "#64748B" }}>{desc}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => onTest(agent)} style={{
            flex: 1, padding: "7px 0", borderRadius: 8,
            background: agent.accent, border: "none",
            color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer",
            transition: "opacity .15s",
          }}
            onMouseEnter={e => { e.currentTarget.style.opacity = ".88"; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = "1"; }}
          >
            ↗ Probar en Chat
          </button>
          <button style={{
            padding: "7px 14px", borderRadius: 8,
            background: "#F8FAFC", border: "1px solid #E2E8F0",
            color: "#64748B", fontSize: 12, fontWeight: 500, cursor: "pointer",
          }}>Detalles</button>
        </div>
      </div>
    </div>
  );
}

function TestModal({ agent, onClose }) {
  const [input, setInput] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!agent) return null;

  async function run() {
    const msg = input.trim();
    if (!msg || loading) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, session_id: `agent_test_${agent.id}` }),
      });
      const data = await res.json();
      setResult(data.reply || data.error || "Sin respuesta.");
    } catch {
      setResult("Error de conexión. Verifica que el servidor esté activo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(15,23,42,.65)",
      backdropFilter: "blur(4px)", zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: "#fff", borderRadius: 20, padding: "28px 32px",
        width: "100%", maxWidth: 520, boxShadow: "0 32px 80px rgba(15,23,42,.25)",
        animation: "zoomIn .2s cubic-bezier(.4,0,.2,1)",
      }}>
        {/* Modal header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 9,
              background: `${agent.accent}14`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
            }}>{agent.icon}</div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#0F172A" }}>Probar · {agent.name}</div>
              <div style={{ fontSize: 12, color: "#94A3B8" }}>Envía un mensaje al agente</div>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "#F1F5F9", border: "none", borderRadius: 8,
            padding: "4px 10px", cursor: "pointer", fontSize: 13, color: "#64748B",
          }}>✕</button>
        </div>

        {/* Suggestion chips */}
        <div style={{ marginBottom: 14, display: "flex", flexWrap: "wrap", gap: 7 }}>
          {agent.tools.slice(0, 3).map(t => {
            const desc = t.split(" · ")[1] || t.split(" · ")[0];
            return (
              <button key={t} onClick={() => setInput(desc)} style={{
                padding: "5px 11px", borderRadius: 20,
                border: "1px solid #E2E8F0", background: "#F8FAFC",
                color: "#475569", fontSize: 12, cursor: "pointer",
              }}>{desc}</button>
            );
          })}
        </div>

        {/* Input */}
        <div style={{
          display: "flex", gap: 8, marginBottom: 16,
        }}>
          <input
            autoFocus
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") run(); }}
            placeholder="Ej: ¿Qué tareas tengo pendientes?"
            style={{
              flex: 1, padding: "9px 12px", borderRadius: 10,
              border: "1px solid #E2E8F0", fontSize: 14, color: "#1E293B",
              fontFamily: "inherit", outline: "none",
            }}
            onFocus={e => { e.target.style.borderColor = agent.accent; }}
            onBlur={e => { e.target.style.borderColor = "#E2E8F0"; }}
          />
          <button onClick={run} disabled={!input.trim() || loading} style={{
            padding: "9px 18px", borderRadius: 10,
            background: input.trim() && !loading ? agent.accent : "#E2E8F0",
            border: "none", color: input.trim() && !loading ? "#fff" : "#94A3B8",
            fontSize: 13, fontWeight: 600, cursor: input.trim() && !loading ? "pointer" : "not-allowed",
          }}>
            {loading ? "…" : "Enviar"}
          </button>
        </div>

        {/* Result */}
        {result && (
          <div style={{
            background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 10,
            padding: "12px 14px", fontSize: 13, color: "#334155", lineHeight: 1.6,
            whiteSpace: "pre-wrap", maxHeight: 260, overflowY: "auto",
            animation: "fadeSlideIn .2s ease",
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#94A3B8", letterSpacing: ".08em",
              textTransform: "uppercase", marginBottom: 6 }}>Respuesta de Jarvis</div>
            {result}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function JarvisAgentes() {
  const now = useTime();
  const [testAgent, setTestAgent] = useState(null);
  const [filter, setFilter] = useState("todos");

  const totalTools = AGENTS.reduce((sum, a) => sum + a.tools.length, 0);
  const autoAgents = AGENTS.filter(a => a.status === "auto").length;
  const activeAgents = AGENTS.filter(a => a.status === "activo").length;

  const filtered = filter === "todos" ? AGENTS
    : filter === "auto" ? AGENTS.filter(a => a.status === "auto")
    : AGENTS.filter(a => a.status === "activo");

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
        @keyframes zoomIn { from { opacity:0; transform:scale(.94) } to { opacity:1; transform:scale(1) } }
        @keyframes fadeSlideIn { from { opacity:0; transform:translateY(5px) } to { opacity:1; transform:none } }
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
            {["Dashboard", "Salud", "Agentes IA", "Chat", "Inversiones"].map((item, i) => (
              <button key={item} style={{
                padding: "6px 14px", borderRadius: 8, border: "1px solid",
                borderColor: i === 2 ? "#2563EB" : "#E2E8F0",
                background: i === 2 ? "#2563EB" : "#fff",
                color: i === 2 ? "#fff" : "#64748B",
                fontSize: 13, fontWeight: 500, cursor: "pointer",
                transition: "all .15s",
              }}>{item}</button>
            ))}
          </nav>
        </div>

        {/* Page header banner */}
        <div style={{
          background: "linear-gradient(135deg, #0F172A 0%, #1E3A5F 60%, #1e40af 100%)",
          borderRadius: 20, padding: "24px 32px",
          color: "#fff", display: "flex", alignItems: "center", justifyContent: "space-between",
          gap: 24, marginBottom: 20,
        }}>
          <div>
            <div style={{ fontSize: 13, color: "#93C5FD", marginBottom: 4, letterSpacing: ".05em" }}>
              Sistema de Agentes IA
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-.02em", lineHeight: 1.1, marginBottom: 8 }}>
              {AGENTS.length} agentes activos
            </div>
            <div style={{ fontSize: 14, color: "#BFDBFE", lineHeight: 1.5, maxWidth: 520 }}>
              Cada agente puede ser invocado desde WhatsApp o el chat web. Todos comparten contexto y memoria de conversación.
            </div>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{ fontSize: 42, marginBottom: 4 }}>🤖</div>
            <div style={{ fontSize: 13, color: "#93C5FD" }}>claude-sonnet-4-6</div>
            <div style={{ fontSize: 12, color: "#60A5FA", marginTop: 2 }}>
              {pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}
            </div>
          </div>
        </div>

        {/* Stat cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
          <StatCard icon="🤖" label="Agentes totales" value={AGENTS.length} accent="#2563EB"/>
          <StatCard icon="⚡" label="Bajo demanda" value={activeAgents} accent="#7C3AED"/>
          <StatCard icon="⏰" label="Automáticos (cron)" value={autoAgents} accent="#059669"/>
          <StatCard icon="🔧" label="Herramientas disponibles" value={totalTools} accent="#D97706"/>
        </div>

        {/* Filter tabs */}
        <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
          {[
            { key: "todos", label: `Todos (${AGENTS.length})` },
            { key: "activo", label: `Bajo demanda (${activeAgents})` },
            { key: "auto", label: `Automáticos (${autoAgents})` },
          ].map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)} style={{
              padding: "7px 16px", borderRadius: 9, border: "1px solid",
              borderColor: filter === f.key ? "#2563EB" : "#E2E8F0",
              background: filter === f.key ? "#EFF6FF" : "#fff",
              color: filter === f.key ? "#2563EB" : "#64748B",
              fontSize: 13, fontWeight: filter === f.key ? 600 : 400,
              cursor: "pointer", transition: "all .15s",
            }}>{f.label}</button>
          ))}
        </div>

        {/* Agents grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {filtered.map(agent => (
            <AgentCard key={agent.id} agent={agent} onTest={setTestAgent}/>
          ))}
        </div>

        {/* Footer */}
        <div style={{ textAlign: "center", marginTop: 24, fontSize: 12, color: "#CBD5E1" }}>
          Jarvis Dashboard · Última sync: {pad(now.getHours())}:{pad(now.getMinutes())} ·
          <span style={{ color: "#10B981", marginLeft: 6 }}>● Conectado</span>
        </div>
      </div>

      {/* Test modal */}
      <TestModal agent={testAgent} onClose={() => setTestAgent(null)}/>
    </div>
  );
}
