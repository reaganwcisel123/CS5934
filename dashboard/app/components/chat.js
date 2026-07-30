// The Sherpa: grounded explainer chat, route-aware. Rendered only when an API
// base is configured (never show a dead robot).
(function(A){
  const Icon = A.Icon;
  const { chat } = A.api;

  function ChatWidget({ countyId, countyName, context }){
    const [open, setOpen] = React.useState(false);
    const [msgs, setMsgs] = React.useState([]);
    const [input, setInput] = React.useState("");
    const [busy, setBusy] = React.useState(false);
    const bodyRef = React.useRef(null);
    // keep the transcript pinned to the newest message
    React.useEffect(() => { const el = bodyRef.current; if(el) el.scrollTop = el.scrollHeight; }, [msgs, busy]);

    const ask = async q => {
      if(!q || busy) return;
      setInput(""); setMsgs(m => [...m, { role: "user", text: q }]); setBusy(true);
      try{
        const res = await chat(q, countyId);
        const d = await res.json().catch(() => ({}));
        if(!res.ok) throw new Error(d.detail || ("HTTP " + res.status));
        setMsgs(m => [...m, { role: "assistant", text: d.answer || "(no answer)" }]);
      }catch(err){ setMsgs(m => [...m, { role: "error", text: String(err.message || err) }]); }
      finally{ setBusy(false); }
    };
    const send = e => { e.preventDefault(); ask(input.trim()); };

    const starters = (context && context.starters) || ["Why is this county high-need?"];
    const sub = (context && context.sub) || countyName;

    return (
      <React.Fragment>
        <button className="chat-fab" onClick={() => setOpen(o => !o)} title="Ask the Sherpa" aria-label="Ask the Sherpa">
          <Icon name={open ? "x" : "sparkles"} size={20} color="#fff" />
        </button>
        {open && (
          <div className="chat-panel" role="dialog" aria-label="Sherpa assistant">
            <div className="chat-head">
              <Icon name="sparkles" size={16} color="var(--command-600)" /><b>Sherpa</b>
              <span className="chat-sub">{sub}</span>
              <button className="chat-x" onClick={() => setOpen(false)} aria-label="Close">✕</button>
            </div>
            <div className="chat-body" ref={bodyRef}>
              {msgs.length === 0 && (
                <React.Fragment>
                  <div className="chat-hint">Ask about {sub}. Answers use only this dashboard's data and flag anything still pending.</div>
                  <div className="chat-starters">
                    {starters.map((s, i) => <button key={i} className="chat-starter" onClick={() => ask(s)}>{s}</button>)}
                  </div>
                </React.Fragment>
              )}
              {msgs.map((m, i) => <div key={i} className={"chat-msg " + m.role}>{m.text}</div>)}
              {busy && <div className="chat-msg assistant chat-typing">…</div>}
            </div>
            <form className="chat-input" onSubmit={send}>
              <input value={input} onChange={e => setInput(e.target.value)} placeholder={"Ask about " + sub + "…"} aria-label="Your question" />
              <button type="submit" disabled={busy} aria-label="Send"><Icon name="send" size={16} color="#fff" /></button>
            </form>
          </div>
        )}
      </React.Fragment>
    );
  }

  A.ChatWidget = ChatWidget;
})(window.Atlas);
