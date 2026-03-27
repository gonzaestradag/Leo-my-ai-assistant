import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { label: "Dashboard",  to: "/" },
  { label: "Salud",      to: "/salud" },
  { label: "Agentes IA", to: "/agentes" },
  { label: "Chat",       to: "/chat" },
  { label: "Inversiones",to: "/inversiones" },
];

function pad(n) { return String(n).padStart(2, "0"); }

function useTime() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  return now;
}

// ─── MOCK DATA ────────────────────────────────────────────────────────────────
const HEALTH = {
  sleep: 7.2, sleepGoal: 8,
  calories: 1840, caloriesGoal: 2200,
  protein: 142, proteinGoal: 180,
  steps: 6800, stepsGoal: 10000,
  water: 1.8, waterGoal: 3,
  mood: 4, moodMax: 5,
  weight: 74.5, weightGoal: 72,
};

const WEEKLY_SLEEP = [
  { day: "L", hours: 6.5 }, { day: "M", hours: 7.8 }, { day: "X", hours: 7.0 },
  { day: "J", hours: 8.1 }, { day: "V", hours: 6.2 }, { day: "S", hours: 9.0 },
  { day: "D", hours: 7.2 },
];

const HYROX_SESSIONS = [
  { date: "Mar 24", type: "Carrera + SkiErg", duration: "52 min", intensity: "alta", done: true },
  { date: "Mar 22", type: "Sled Push & Pull", duration: "45 min", intensity: "alta", done: true },
  { date: "Mar 20", type: "Recuperación activa", duration: "30 min", intensity: "baja", done: true },
  { date: "Mar 27", type: "Burpee Broad Jumps", duration: "55 min", intensity: "alta", done: false },
];

const MEDICATIONS = [
  { name: "Vitamina D3", dosage: "2000 UI", time: "08:00", taken: true },
  { name: "Omega-3", dosage: "1000 mg", time: "13:00", taken: true },
  { name: "Magnesio", dosage: "400 mg", time: "21:00", taken: false },
];

const MOOD_LABELS = ["", "Muy bajo", "Bajo", "Regular", "Bien", "Excelente"];
const MOOD_COLORS = ["", "#EF4444", "#F97316", "#F59E0B", "#10B981", "#2563EB"];

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function Bar({ value, max, color = "#2563EB", height = 6 }) {
  const pct = Math.min(value / max, 1) * 100;
  return (
    <div style={{ background: "rgba(148,163,184,.15)", borderRadius: 9, height, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 9,
        transition: "width .6s cubic-bezier(.4,0,.2,1)" }}/>
    </div>
  );
}

function Ring({ value, max, size = 64, stroke = 6, color = "#2563EB", children }) {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(value / max, 1);
  return (
    <svg width={size} height={size} style={{ display: "block" }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(148,163,184,.2)" strokeWidth={stroke}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={`${circ * pct} ${circ}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: "stroke-dasharray .6s cubic-bezier(.4,0,.2,1)" }}/>
      {children && (
        <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
          style={{ fontSize: 12, fontWeight: 700, fill: color, fontFamily: "inherit" }}>
          {children}
        </text>
      )}
    </svg>
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

// ─── PANELS ──────────────────────────────────────────────────────────────────

function MetricsPanel({ h }) {
  const metrics = [
    { label: "Sueño",    value: h.sleep,    max: h.sleepGoal,    unit: "h",    color: "#7C3AED" },
    { label: "Calorías", value: h.calories, max: h.caloriesGoal, unit: "kcal", color: "#EF4444" },
    { label: "Proteína", value: h.protein,  max: h.proteinGoal,  unit: "g",    color: "#F97316" },
    { label: "Pasos",    value: h.steps,    max: h.stepsGoal,    unit: "",     color: "#10B981" },
    { label: "Agua",     value: h.water,    max: h.waterGoal,    unit: "L",    color: "#2563EB" },
    { label: "Ánimo",    value: h.mood,     max: h.moodMax,      unit: `/${h.moodMax}`, color: MOOD_COLORS[h.mood] },
  ];
  return (
    <PanelWrapper title="Métricas del día" icon="📊" accent="#10B981">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        {metrics.map(m => (
          <div key={m.label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Ring value={m.value} max={m.max} size={56} stroke={5} color={m.color}>
              {Math.round((m.value / m.max) * 100)}%
            </Ring>
            <div>
              <div style={{ fontSize: 11, color: "#94A3B8", fontWeight: 600 }}>{m.label}</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#1E293B" }}>{m.value}{m.unit}</div>
              <div style={{ fontSize: 11, color: "#CBD5E1" }}>/ {m.max}{m.unit}</div>
            </div>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function SleepPanel({ data }) {
  const maxH = Math.max(...data.map(d => d.hours));
  const avg = (data.reduce((s, d) => s + d.hours, 0) / data.length).toFixed(1);
  return (
    <PanelWrapper title="Sueño semanal" icon="😴" accent="#7C3AED">
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 16 }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: "#1E293B" }}>{avg}h</span>
        <span style={{ fontSize: 13, color: "#94A3B8" }}>promedio esta semana</span>
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 70 }}>
        {data.map(d => {
          const pct = d.hours / maxH;
          const ok = d.hours >= 7;
          return (
            <div key={d.day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <div style={{ fontSize: 10, color: ok ? "#7C3AED" : "#94A3B8", fontWeight: 600 }}>{d.hours}</div>
              <div style={{
                width: "100%", height: Math.round(pct * 50),
                background: ok ? "#7C3AED" : "#CBD5E1",
                borderRadius: "4px 4px 0 0",
                transition: "height .4s",
              }}/>
              <div style={{ fontSize: 10, color: "#94A3B8", fontWeight: 600 }}>{d.day}</div>
            </div>
          );
        })}
      </div>
      <div style={{ marginTop: 12, fontSize: 12, color: "#94A3B8" }}>
        Meta: 8h · Días ≥7h: {data.filter(d => d.hours >= 7).length}/7
      </div>
    </PanelWrapper>
  );
}

function HyroxPanel({ sessions }) {
  const intensityColors = { alta: "#EF4444", media: "#F59E0B", baja: "#10B981" };
  return (
    <PanelWrapper title="Entrenamiento Hyrox" icon="🏋️" accent="#EF4444">
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {sessions.map((s, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "9px 10px", borderRadius: 9,
            background: s.done ? "#F8FAFC" : "#EFF6FF",
            border: `1px solid ${s.done ? "#F1F5F9" : "#BFDBFE"}`,
            opacity: s.done ? 1 : 1,
          }}>
            <span style={{ fontSize: 16 }}>{s.done ? "✅" : "⏳"}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#1E293B" }}>{s.type}</div>
              <div style={{ fontSize: 11, color: "#94A3B8" }}>{s.date} · {s.duration}</div>
            </div>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 6,
              background: `${intensityColors[s.intensity]}18`,
              color: intensityColors[s.intensity],
            }}>{s.intensity}</span>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function MedicationPanel({ meds }) {
  const taken = meds.filter(m => m.taken).length;
  return (
    <PanelWrapper title="Medicamentos" icon="💊" accent="#6366F1">
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: "#1E293B" }}>{taken}/{meds.length}</span>
        <span style={{ fontSize: 13, color: "#94A3B8" }}>tomados hoy</span>
      </div>
      <Bar value={taken} max={meds.length} color="#6366F1" height={6}/>
      <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        {meds.map((m, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "7px 10px", borderRadius: 8,
            background: m.taken ? "#F0FDF4" : "#F8FAFC",
            border: `1px solid ${m.taken ? "#BBF7D0" : "#E2E8F0"}`,
          }}>
            <span style={{ fontSize: 14 }}>{m.taken ? "✅" : "⬜"}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#1E293B" }}>{m.name}</div>
              <div style={{ fontSize: 11, color: "#94A3B8" }}>{m.dosage} · {m.time}</div>
            </div>
          </div>
        ))}
      </div>
    </PanelWrapper>
  );
}

function MoodPanel({ mood }) {
  const emojis = ["", "😞", "😕", "😐", "😊", "🤩"];
  return (
    <PanelWrapper title="Estado de ánimo" icon="🧠" accent={MOOD_COLORS[mood]}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
        <span style={{ fontSize: 48 }}>{emojis[mood]}</span>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: MOOD_COLORS[mood] }}>
            {MOOD_LABELS[mood]}
          </div>
          <div style={{ fontSize: 12, color: "#94A3B8", marginTop: 2 }}>
            {mood}/{HEALTH.moodMax} hoy
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        {[1, 2, 3, 4, 5].map(n => (
          <div key={n} style={{
            flex: 1, height: 6, borderRadius: 4,
            background: n <= mood ? MOOD_COLORS[mood] : "rgba(148,163,184,.2)",
            transition: "background .3s",
          }}/>
        ))}
      </div>
      <div style={{ marginTop: 10, fontSize: 12, color: "#94A3B8" }}>
        Registrado hoy a las 09:30
      </div>
    </PanelWrapper>
  );
}

function WeightPanel({ weight, goal }) {
  const diff = weight - goal;
  return (
    <PanelWrapper title="Peso corporal" icon="⚖️" accent="#D97706">
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 32, fontWeight: 700, color: "#1E293B" }}>{weight}</span>
        <span style={{ fontSize: 14, color: "#94A3B8" }}>kg</span>
      </div>
      <div style={{ fontSize: 13, color: diff > 0 ? "#D97706" : "#10B981", fontWeight: 600, marginBottom: 12 }}>
        {diff > 0 ? `▼ ${diff.toFixed(1)} kg para tu meta` : `✅ Meta alcanzada`}
      </div>
      <Bar value={goal} max={weight} color="#D97706" height={6}/>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <span style={{ fontSize: 11, color: "#94A3B8" }}>Meta: {goal} kg</span>
        <span style={{ fontSize: 11, color: "#CBD5E1" }}>Actual: {weight} kg</span>
      </div>
    </PanelWrapper>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────
export default function JarvisSalud() {
  const now = useTime();
  const location = useLocation();

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
          background: "linear-gradient(135deg, #0F172A 0%, #1E3A5F 60%, #065F46 100%)",
          borderRadius: 20, padding: "28px 32px",
          color: "#fff", display: "flex", alignItems: "center", justifyContent: "space-between",
          gap: 24, marginBottom: 20,
        }}>
          <div>
            <div style={{ fontSize: 13, color: "#6EE7B7", marginBottom: 4, letterSpacing: ".05em" }}>
              Panel de salud
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-.02em", lineHeight: 1.1, marginBottom: 8 }}>
              Hyrox Sub-1:15 · 82% del camino
            </div>
            <div style={{ fontSize: 14, color: "#A7F3D0", lineHeight: 1.5, maxWidth: 520 }}>
              Sueño promedio esta semana: 7.4h · {HEALTH.steps.toLocaleString()} pasos hoy ·
              Ánimo: {MOOD_LABELS[HEALTH.mood]}
            </div>
          </div>
          <div style={{ textAlign: "center", flexShrink: 0 }}>
            <div style={{ fontSize: 48, marginBottom: 4 }}>💪</div>
            <div style={{ fontSize: 13, color: "#6EE7B7" }}>Entrenamiento hoy</div>
            <div style={{ fontSize: 12, color: "#34D399", marginTop: 2 }}>
              {pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}
            </div>
          </div>
        </div>

        {/* Metrics full-width */}
        <div style={{ marginBottom: 16 }}>
          <MetricsPanel h={HEALTH}/>
        </div>

        {/* 3-col grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
          <SleepPanel data={WEEKLY_SLEEP}/>
          <HyroxPanel sessions={HYROX_SESSIONS}/>
          <MedicationPanel meds={MEDICATIONS}/>
        </div>

        {/* 2-col row */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <MoodPanel mood={HEALTH.mood}/>
          <WeightPanel weight={HEALTH.weight} goal={HEALTH.weightGoal}/>
        </div>

        {/* Footer */}
        <div style={{ textAlign: "center", marginTop: 24, fontSize: 12, color: "#CBD5E1" }}>
          Jarvis Dashboard · Última sync: {pad(now.getHours())}:{pad(now.getMinutes())} ·
          <span style={{ color: "#10B981", marginLeft: 6 }}>● Conectado</span>
        </div>
      </div>
    </div>
  );
}
