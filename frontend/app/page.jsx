"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import AnalysisPanel from "./analysis-panel";
import ProposalPanel from "./proposal-panel";

const call = async (path, options = {}) => {
  const res = await fetch(path, { credentials: "same-origin", cache: "no-store", ...options });
  let data;
  try { data = await res.json(); } catch { data = {}; }
  if (!res.ok) throw Error(data.error || data.detail || "API error (" + res.status + ")");
  return data;
};
const api = (path) => "/api/control/" + path;
const clock = (date) => new Date(date).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });

export default function Home() {
  const [auth, setAuth] = useState(null);
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [current, setCurrent] = useState("");
  const [messages, setMessages] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [draft, setDraft] = useState("");
  const [title, setTitle] = useState("");
  const [pending, setPending] = useState([]);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState("Chưa kết nối");
  const [activeTab, setActiveTab] = useState("chat");
  const [lastEvent, setLastEvent] = useState(0);
  const picker = useRef(null);
  const bottom = useRef(null);

  const refreshConversations = useCallback(async () => {
    const data = await call(api("conversations"));
    setConversations(data.items || []);
  }, []);
  const refreshRoom = useCallback(async (id) => {
    if (!id) return;
    const [m, a] = await Promise.all([
      call(api("conversations/" + id + "/messages")),
      call(api("conversations/" + id + "/attachments"))
    ]);
    setMessages(m.items || []);
    setAttachments(a.items || []);
    setConnected("Đồng bộ dữ liệu");
  }, []);

  useEffect(() => {
    call("/api/session").then((x) => setAuth(x.authenticated)).catch(() => setAuth(false));
  }, []);
  useEffect(() => {
    if (!auth) return;
    refreshConversations().catch((e) => setError(e.message));
  }, [auth, refreshConversations]);
  useEffect(() => {
    if (!auth || !current) return;
    let cancelled = false;
    setMessages([]);
    setAttachments([]);
    setPending([]);
    setLastEvent(0);
    refreshRoom(current).catch((e) => !cancelled && setError(e.message));
    const source = new EventSource(api("conversations/" + current + "/events"));
    const onUpdate = (ev) => {
      if (cancelled) return;
      if (ev.lastEventId) setLastEvent(Number(ev.lastEventId) || 0);
      refreshRoom(current).catch((e) => setError(e.message));
    };
    for (const type of ["conversation.created","message.created","attachment.received"])
      source.addEventListener(type, onUpdate);
    source.onopen = () => !cancelled && setConnected("SSE đã kết nối");
    source.onerror = () => !cancelled && setConnected("Đang kết nối lại");
    return () => { cancelled = true; source.close(); };
  }, [auth, current, refreshRoom]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, activeTab]);

  async function login(e) {
    e.preventDefault(); setBusy(true); setLoginError("");
    try {
      await call("/api/session", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }) });
      setPassword(""); setAuth(true);
    } catch (e) { setLoginError(e.message); }
    finally { setBusy(false); }
  }
  async function logout() {
    try { await call("/api/session", { method: "DELETE" }); }
    catch (e) { setError(e.message); }
    setAuth(false); setCurrent(""); setConversations([]);
  }
  async function createRoom(e) {
    e.preventDefault(); if (!title.trim()) return;
    setBusy(true); setError("");
    try {
      const data = await call(api("conversations"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim() })
      });
      setTitle(""); await refreshConversations(); setCurrent(data.id); setActiveTab("chat");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function send(e) {
    e.preventDefault(); if (!current || !draft.trim()) return;
    setBusy(true); setError("");
    try {
      await call(api("conversations/" + current + "/messages"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: draft.trim(), attachment_ids: pending })
      });
      setDraft(""); setPending([]); await refreshRoom(current);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function upload(e) {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (!current || !files.length) return;
    setBusy(true); setError("");
    for (const file of files) {
      if (!["image/png","image/jpeg","video/mp4"].includes(file.type)) {
        setError("Chỉ hỗ trợ PNG, JPEG và MP4."); continue;
      }
      const limit = file.type === "video/mp4" ? 25 * 1024 * 1024 : 8 * 1024 * 1024;
      if (file.size > limit) { setError("Tệp vượt giới hạn dung lượng."); continue; }
      try {
        const data = new FormData(); data.append("file", file);
        const result = await call(api("conversations/" + current + "/attachments"), {
          method: "POST", body: data
        });
        setPending((prev) => [...prev, result.id]);
      } catch (err) { setError(err.message); }
    }
    await refreshRoom(current).catch(() => {});
    setBusy(false);
  }
  if (auth === null) return <main className="loading">Đang xác định phiên đăng nhập…</main>;
  if (!auth) return (
    <main className="loginPage">
      <section className="loginCard">
        <div className="logoMark">BX</div>
        <h1>BaoXTra AI Agency</h1>
        <p>Control Center V0.6 · Quản lý dự án và hội thoại</p>
        <form onSubmit={login}>
          <label htmlFor="password">Mật khẩu quản trị</label>
          <input id="password" type="password" minLength={1} value={password}
            onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          <button disabled={busy} className="primary">{busy ? "Đang xác thực…" : "Đăng nhập"}</button>
          {loginError && <p className="error" role="alert">{loginError}</p>}
        </form>
        <p className="subtle">Chế độ REVIEW_ONLY · Không thực thi lệnh giao dịch</p>
      </section>
    </main>
  );
  return (
    <main className="appShell">
      <header className="topbar">
        <div className="brand"><div className="logoMark small">BX</div><div><strong>BaoXTra AI Agency</strong><small>Control Center V0.6</small></div></div>
        <div className="topActions"><span className="safeBadge">REVIEW_ONLY</span><button className="quiet" onClick={logout}>Đăng xuất</button></div>
      </header>
      <div className="workspace">
        <aside className="sidebar">
          <h2>Dự án / Projects</h2>
          <form className="createForm" onSubmit={createRoom}>
            <input aria-label="Tên cuộc trò chuyện mới" placeholder="Tên dự án mới…" value={title}
              minLength={3} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
            <button className="primary" disabled={busy || title.trim().length < 3}>+ Tạo</button>
          </form>
          <nav aria-label="Danh sách cuộc trò chuyện">
            {conversations.map((room) => (
              <button key={room.id} className={"room " + (current === room.id ? "selected" : "")}
                onClick={() => { setCurrent(room.id); setError(""); setActiveTab("chat"); }}>
                <span>▣</span><span className="truncate">{room.title}</span>
              </button>
            ))}
          </nav>
          {!conversations.length && <p className="muted">Chưa có cuộc trò chuyện nào.</p>}
          <div className="sidebarFoot">Dữ liệu được lưu ở backend. Không có AI xử lý tự động trong bản này.</div>
        </aside>
        <section className="mainPanel">
          {!current ? (
            <div className="emptyState"><div className="emptyIcon">✦</div><h2>Bắt đầu một dự án mới</h2>
              <p>Tạo cuộc trò chuyện để gửi yêu cầu, ảnh chụp giao diện hoặc video minh họa. Dữ liệu sẽ được lưu để chuẩn bị phân tích AI.</p>
            </div>
          ) : <>
            <div className="roomHead">
              <div><h2>{conversations.find((x) => x.id === current)?.title || "Dự án"}</h2>
                <span className="statusLine">● {connected} · event #{lastEvent}</span></div>
              <button className="quiet" onClick={() => refreshRoom(current).catch((e) => setError(e.message))}>Làm mới</button>
            </div>
            <div className="mobileTabs">
              {["chat","files","plan"].map((t) => <button key={t} onClick={() => setActiveTab(t)}
                className={activeTab === t ? "active" : ""}>{t === "chat" ? "Chat" : t === "files" ? "Tài liệu" : "Kế hoạch"}</button>)}
            </div>
            {activeTab === "chat" ? <>
              <div className="messages">
                {!messages.length && <div className="intro"><strong>Không gian trao đổi / Workspace</strong><p>Gửi thông tin dự án trong khung bên dưới. Hệ thống sẽ lưu hội thoại; Agent chưa tự trả lời.</p></div>}
                {messages.map((m) => <div key={m.id} className="messageOwner">
                  <span className="messageLabel">Bạn · {clock(m.created_at)}</span>
                  <div>{m.body}</div>
                </div>)}
                <div ref={bottom} />
              </div>
              {pending.length > 0 && <div className="pending">Đã chọn {pending.length} tệp cách ly · chờ gắn vào tin nhắn
                <button className="quiet" onClick={() => setPending([])}>Bỏ chọn</button></div>}
              <form className="composer" onSubmit={send}>
                <input ref={picker} type="file" accept="image/png,image/jpeg,video/mp4" multiple
                  onChange={upload} hidden aria-label="Tải ảnh hoặc video" />
                <button type="button" className="attachButton" title="Tải ảnh/video" disabled={busy}
                  onClick={() => picker.current?.click()}>＋</button>
                <textarea aria-label="Nhập nội dung hội thoại" value={draft} maxLength={8000}
                  onChange={(e) => setDraft(e.target.value)} placeholder="Mô tả ứng dụng hoặc yêu cầu phân tích…"
                  rows={2} />
                <button type="submit" className="primary sendButton" disabled={busy || !draft.trim()}>Gửi</button>
              </form>
              <div className="disclaimer">Bản V0.6 chỉ lưu dữ liệu. AI Vision, phê duyệt và thực thi Agent chưa được kết nối.</div>
            </> : activeTab === "files" ? <div className="contentPanel">
              <h3>Ảnh và video đã nhận</h3>
              <p className="muted">Tệp đang cách ly, chưa quét mã độc và chưa xử lý bằng AI. Không mở xem trước hay tải xuống.</p>
              {attachments.map((a) => <article className="fileRow" key={a.id}>
                <strong>{a.mime.startsWith("image/") ? "▣ Ảnh" : "▻ Video"}</strong>
                <span>{(a.byte_size / 1024).toFixed(1)} KB</span><small>{a.processing_status}</small>
              </article>)}
              {!attachments.length && <p>Chưa có tệp nào.</p>}
              <AnalysisPanel conversationId={current} attachments={attachments} />
            </div> : <div className="contentPanel">
              <ProposalPanel conversationId={current} />
            </div>}
          </>}
          {error && <div className="errorBanner" role="alert">{error}<button onClick={() => setError("")} aria-label="Đóng thông báo">×</button></div>}
        </section>
        <aside className="rightPanel">
          <h2>Quy trình / Workflow</h2>
          <div className="step active"><span>01</span><div><strong>Giao yêu cầu</strong><small>Chat + hình ảnh/video</small></div></div>
          <div className="step"><span>02</span><div><strong>AI phân tích</strong><small>Chưa kết nối</small></div></div>
          <div className="step"><span>03</span><div><strong>Sơ đồ ứng dụng</strong><small>Chưa kết nối</small></div></div>
          <div className="step"><span>04</span><div><strong>Owner duyệt</strong><small>Không tự thực thi</small></div></div>
          <div className="rightFoot"><strong>Trạng thái hệ thống</strong><p>Chưa triển khai production. Không có kết nối broker hoặc lệnh LIVE.</p></div>
        </aside>
      </div>
    </main>
  );
}
