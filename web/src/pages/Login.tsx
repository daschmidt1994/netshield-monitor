import { useState } from "react";
import { api, setCsrf } from "../api";
import { useT } from "../i18n";

export function Login({ onLogin }: { onLogin: (name: string) => void }) {
  const { t } = useT();
  const [u, setU] = useState("admin");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="login-wrap">
      <form className="card login" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setErr(null);
        try { const r = await api.post<{ username: string; csrf_token: string }>("/api/v1/auth/login", { username: u, password: p }); setCsrf(r.csrf_token); onLogin(r.username); }
        catch (ex) { setErr(`${t("loginFailed")}: ${ex instanceof Error ? ex.message : ex}`); }
        finally { setBusy(false); }
      }}>
        <div className="brand big"><img src="/favicon.svg" alt="" width={36} height={36} /> {t("appName")}</div>
        <label>{t("username")}<input autoComplete="username" value={u} onChange={(e) => setU(e.target.value)} required /></label>
        <label>{t("password")}<input type="password" autoComplete="current-password" value={p} onChange={(e) => setP(e.target.value)} required /></label>
        {err && <div className="error-box">{err}</div>}
        <button className="btn" disabled={busy}>{t("login")}</button>
      </form>
    </div>
  );
}
