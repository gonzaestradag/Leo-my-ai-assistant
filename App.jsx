import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import JarvisDashboard from "./JarvisDashboard.jsx";
import JarvisSalud from "./JarvisSalud.jsx";
import JarvisAgentes from "./JarvisAgentes.jsx";
import JarvisChat from "./JarvisChat.jsx";
import JarvisInversiones from "./JarvisInversiones.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"            element={<JarvisDashboard />} />
        <Route path="/salud"       element={<JarvisSalud />} />
        <Route path="/agentes"     element={<JarvisAgentes />} />
        <Route path="/chat"        element={<JarvisChat />} />
        <Route path="/inversiones" element={<JarvisInversiones />} />
        <Route path="*"            element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
