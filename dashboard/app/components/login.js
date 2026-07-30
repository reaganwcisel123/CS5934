// Auth gate (opt-in via ?auth=1 + an API base). Ported unchanged from signal.html.
(function(A){
  const { API_BASE } = A.api;

  function Login({ onAuth }){
    // Sprint demo: prefill the dummy account so the gated site is one-click.
    const [email, setEmail] = React.useState("demo@clinicatlas.dev");
    const [pw, setPw] = React.useState("triad-demo-2026");
    const [mode, setMode] = React.useState("login");
    const [error, setError] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    const submit = async e => {
      e.preventDefault(); setError(""); setBusy(true);
      try{
        const res = await fetch(API_BASE + "/auth/" + mode, { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password: pw }) });
        const d = await res.json().catch(() => ({}));
        if(!res.ok) throw new Error(d.detail || ("HTTP " + res.status));
        onAuth(d.token);
      }catch(err){ setError(String(err.message || err)); } finally{ setBusy(false); }
    };
    return (
      <div className="login-wrap">
        <form className="login-card" onSubmit={submit}>
          <div className="login-brand"><span className="mark">T</span>Triad · Signal</div>
          <h2>{mode === "login" ? "Sign in to the Clinic Needs Atlas" : "Create your account"}</h2>
          {mode === "login" && <p className="login-alt">Sprint demo login is prefilled. Just click Sign in.</p>}
          <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
          <input type="password" placeholder="Password" value={pw} onChange={e => setPw(e.target.value)} required />
          {error && <div className="login-err">{error}</div>}
          <button type="submit" disabled={busy}>{busy ? "…" : (mode === "login" ? "Sign in" : "Create account")}</button>
          <div className="login-alt">
            {mode === "login" ? "New here? " : "Have an account? "}
            <a onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
              {mode === "login" ? "Create an account" : "Sign in"}</a>
          </div>
        </form>
      </div>
    );
  }

  A.Login = Login;
})(window.Atlas);
