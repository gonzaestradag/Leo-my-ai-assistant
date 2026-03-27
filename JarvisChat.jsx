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
const SESSION_ID = "web_dashboard";

function pad(n) { return String(n).padStart(2, "0"); }

function useTime() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  return now;
}

function TypingIndicator() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "10px 14px",
      background: "#F1F5F9", borderRadius: "16px 16px 16px 4px", width: "fit-content" }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 6, height: 6, borderRadius: "50%", background: "#94A3B8",
          animation: "bounce .9s infinite",
          animationDelay: `${i * 0.18}s`,
        }}/>
      ))}
    </div>
  );
}

function Message({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: 10,
      animation: "fadeSlideIn .2s cubic-bezier(.4,0,.2,1)",
    }}>
      {!isUser && (
        <div style={{
          width: 30, height: 30, borderRadius: 8, flexShrink: 0, marginRight: 8, marginTop: 2,
          background: "linear-gradient(135deg, #1E3A5F, #2563EB)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13, fontWeight: 800, color: "#fff",
        }}>J</div>
      )}
      <div style={{
        maxWidth: "72%",
        padding: "10px 14px",
        borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
        background: isUser
          ? "linear-gradient(135deg, #1E3A5F, #2563EB)"
          : "#F1F5F9",
        color: isUser ? "#fff" : "#1E293B",
        fontSize: 14,
        lineHeight: 1.55,
        boxShadow: isUser ? "0 2px 8px rgba(37,99,235,.25)" : "none",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}>
        {msg.text}
        <div style={{
          fontSize: 10,
          marginTop: 4,
          color: isUser ? "rgba(255,255,255,.55)" : "#CBD5E1",
          textAlign: "right",
        }}>
          {msg.time}
        </div>
      </div>
      {isUser && (
        <div style={{
          width: 30, height: 30, borderRadius: 8, flexShrink: 0, marginLeft: 8, marginTop: 2,
          background: "#E2E8F0",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13, fontWeight: 700, color: "#475569",
        }}>GE</div>
      )}
    </div>
  );
}

export default function JarvisChat() {
  const now = useTime();
  const location = useLocation();
  const [messages, setMessages] = useState([
    {
      id: 0,
      role: "assistant",
      text: "Hola Gonzalo 👋 Soy Jarvis. ¿En qué te puedo ayudar hoy?",
      time: `${pad(new Date().getHours())}:${pad(new Date().getMinutes())}`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const userMsg = {
      id: Date.now(),
      role: "user",
      text,
      time: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
    };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: SESSION_ID }),
      });
      const data = await res.json();
      const reply = data.reply || data.error || "Sin respuesta.";
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "assistant",
        text: reply,
        time: `${pad(new Date().getHours())}:${pad(new Date().getMinutes())}`,
      }]);
    } catch {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "assistant",
        text: "Error de conexión. Revisa que el servidor esté activo.",
        time: `${pad(new Date().getHours())}:${pad(new Date().getMinutes())}`,
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const suggestions = [
    "¿Qué tengo hoy en agenda?",
    "¿Cuánto he gastado esta semana?",
    "Muéstrame mis tareas pendientes",
    "¿Cómo está mi salud esta semana?",
  ];

  return (
    <div style={{
      minHeight: "100vh",
      background: "#F0F4F8",
      fontFamily: "'Inter', 'SF Pro Display', -apple-system, sans-serif",
      display: "flex",
      flexDirection: "column",
      padding: "24px",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; }
        @keyframes fadeSlideIn { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:none } }
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0) }
          40% { transform: translateY(-5px) }
        }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
        textarea:focus { outline: none; }
        textarea { resize: none; }
      `}</style>

      <div style={{ maxWidth: 860, margin: "0 auto", width: "100%", display: "flex", flexDirection: "column", flex: 1 }}>

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

        {/* Chat container */}
        <div style={{
          background: "#fff",
          border: "1px solid #E2E8F0",
          borderRadius: 20,
          display: "flex",
          flexDirection: "column",
          flex: 1,
          overflow: "hidden",
          boxShadow: "0 1px 4px rgba(15,23,42,.05)",
        }}>

          {/* Chat header */}
          <div style={{
            background: "linear-gradient(135deg, #0F172A 0%, #1E3A5F 60%, #1e40af 100%)",
            padding: "18px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 12,
                background: "rgba(255,255,255,.12)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 18, fontWeight: 800, color: "#fff",
              }}>J</div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#fff" }}>Jarvis AI</div>
                <div style={{ fontSize: 12, color: "#93C5FD", display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#10B981", display: "inline-block" }}/>
                  En línea · claude-sonnet-4-6
                </div>
              </div>
            </div>
            <div style={{ fontSize: 13, color: "#93C5FD", fontFamily: "'SF Mono', monospace" }}>
              {pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}
            </div>
          </div>

          {/* Messages area */}
          <div style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px 24px",
            minHeight: 0,
            maxHeight: "calc(100vh - 340px)",
          }}>
            {/* Quick suggestions — only shown when there's just the initial message */}
            {messages.length === 1 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#94A3B8", letterSpacing: ".08em",
                  textTransform: "uppercase", marginBottom: 10 }}>Sugerencias rápidas</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {suggestions.map(s => (
                    <button key={s} onClick={() => { setInput(s); inputRef.current?.focus(); }} style={{
                      padding: "6px 12px", borderRadius: 20,
                      border: "1px solid #E2E8F0", background: "#F8FAFC",
                      color: "#475569", fontSize: 12, fontWeight: 500,
                      cursor: "pointer", transition: "all .15s",
                    }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = "#2563EB"; e.currentTarget.style.color = "#2563EB"; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = "#E2E8F0"; e.currentTarget.style.color = "#475569"; }}
                    >{s}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map(msg => <Message key={msg.id} msg={msg} />)}
            {loading && (
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 10 }}>
                <div style={{
                  width: 30, height: 30, borderRadius: 8, flexShrink: 0,
                  background: "linear-gradient(135deg, #1E3A5F, #2563EB)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 13, fontWeight: 800, color: "#fff",
                }}>J</div>
                <TypingIndicator />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: "#E2E8F0", margin: "0 24px" }} />

          {/* Input area */}
          <div style={{ padding: "16px 24px", display: "flex", gap: 10, alignItems: "flex-end" }}>
            <div style={{
              flex: 1,
              background: "#F8FAFC",
              border: "1px solid #E2E8F0",
              borderRadius: 12,
              padding: "10px 14px",
              display: "flex",
              alignItems: "flex-end",
              gap: 8,
              transition: "border-color .15s",
            }}
              onFocusCapture={e => { e.currentTarget.style.borderColor = "#2563EB"; }}
              onBlurCapture={e => { e.currentTarget.style.borderColor = "#E2E8F0"; }}
            >
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={e => {
                  setInput(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
                }}
                onKeyDown={handleKey}
                placeholder="Escribe un mensaje a Jarvis… (Enter para enviar)"
                style={{
                  flex: 1,
                  border: "none",
                  background: "transparent",
                  fontSize: 14,
                  color: "#1E293B",
                  fontFamily: "inherit",
                  lineHeight: 1.5,
                  maxHeight: 120,
                  overflowY: "auto",
                }}
              />
            </div>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              style={{
                width: 42, height: 42, borderRadius: 12,
                background: input.trim() && !loading
                  ? "linear-gradient(135deg, #1E3A5F, #2563EB)"
                  : "#E2E8F0",
                border: "none",
                cursor: input.trim() && !loading ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 16,
                transition: "all .15s",
                flexShrink: 0,
                boxShadow: input.trim() && !loading ? "0 2px 8px rgba(37,99,235,.3)" : "none",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M22 2L11 13" stroke={input.trim() && !loading ? "#fff" : "#94A3B8"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke={input.trim() && !loading ? "#fff" : "#94A3B8"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>

          {/* Footer hint */}
          <div style={{ textAlign: "center", paddingBottom: 14, fontSize: 11, color: "#CBD5E1" }}>
            Enter para enviar · Shift+Enter para nueva línea ·
            <span style={{ color: "#10B981", marginLeft: 4 }}>● claude-sonnet-4-6</span>
          </div>
        </div>

        {/* Bottom bar */}
        <div style={{ textAlign: "center", marginTop: 16, fontSize: 12, color: "#CBD5E1" }}>
          Jarvis Dashboard · {pad(now.getHours())}:{pad(now.getMinutes())} ·
          <span style={{ color: "#10B981", marginLeft: 6 }}>● Conectado</span>
        </div>
      </div>
    </div>
  );
}
