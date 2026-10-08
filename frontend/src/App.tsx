import { Navigate, Route, Routes } from "react-router-dom";

import { readToken } from "./api/client";
import { Layout } from "./components/Layout";
import { ChatPage } from "./pages/ChatPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { UploadPage } from "./pages/UploadPage";

function RequireAuth() {
  if (!readToken()) {
    return <Navigate to="/login" replace />;
  }
  return <Layout />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/documents" element={<UploadPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
      </Route>
    </Routes>
  );
}
