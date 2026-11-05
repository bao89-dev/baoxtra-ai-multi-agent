"use client";
import { useCallback, useEffect, useState } from "react";

export default function AnalysisPanel({ conversationId, attachments }) {
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState("");
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!conversationId) return;
    const response = await fetch("/api/control/conversations/" + conversationId + "/analysis-jobs", {
      cache: "no-store", credentials: "same-origin"
    });
    if (!response.ok) throw Error("Không tải được lịch sử phân tích");
    const data = await response.json();
    setJobs(data.items || []);
  }, [conversationId]);

  useEffect(() => {
    setSelected("");
    setInstructions("");
    load().catch((e) => setError(e.message));
  }, [load]);

  const chosen = attachments.find((item) => item.id === selected);
  async function requestAnalysis() {
    if (!chosen) return;
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/control/conversations/" + conversationId + "/analysis-jobs", {
        credentials: "same-origin",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attachment_id: chosen.id,
          job_type: chosen.mime.startsWith("video/") ? "video_review" : "image_review",
          instructions
        })
      });
      if (!response.ok) throw Error("Không thể tạo yêu cầu phân tích");
      await load();
      setInstructions("");
    } catch(e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <section className="analysisPanel" aria-label="Yêu cầu phân tích">
    <h3>Yêu cầu phân tích / Analysis Request</h3>
    <p className="muted">Yêu cầu sẽ được ghi vào lịch sử. Tệp chưa quét an toàn sẽ bị chặn; chưa sử dụng AI Vision.</p>
    <label htmlFor="analysis-file">Tệp cần đánh giá</label>
    <select id="analysis-file" value={selected} onChange={(e) => setSelected(e.target.value)}>
      <option value="">Chọn ảnh hoặc video…</option>
      {attachments.map((a) => <option key={a.id} value={a.id}>
        {a.mime.startsWith("video/") ? "Video" : "Ảnh"} · {a.id.slice(0,8)} · {a.processing_status}
      </option>)}
    </select>
    <label htmlFor="analysis-prompt">Yêu cầu / Instructions</label>
    <textarea id="analysis-prompt" rows={3} maxLength={3000} value={instructions}
      placeholder="Ví dụ: Đánh giá bố cục ứng dụng và đề xuất các module…"
      onChange={(e) => setInstructions(e.target.value)} />
    <button className="primary" disabled={!chosen || busy} onClick={requestAnalysis}>
      {busy ? "Đang ghi nhận…" : "Ghi yêu cầu phân tích"}
    </button>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="analysisHistory">
      <h3>Lịch sử yêu cầu</h3>
      <button className="quiet" onClick={() => load().catch((e) => setError(e.message))}>Làm mới</button>
      {jobs.map((job) => <article className="fileRow" key={job.id}>
        <strong>{job.job_type}</strong>
        <span>{job.status}</span>
        <small>{job.blocker}</small>
      </article>)}
      {!jobs.length && <p className="muted">Chưa có yêu cầu phân tích.</p>}
    </div>
  </section>;
}
