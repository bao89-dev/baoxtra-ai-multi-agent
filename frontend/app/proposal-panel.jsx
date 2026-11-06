"use client";
import { useCallback, useEffect, useState } from "react";

const endpoint = (path) => "/api/control/" + path;
async function jsonRequest(path, init={}) {
  const response=await fetch(endpoint(path), {cache:"no-store",credentials:"same-origin",...init});
  const data=await response.json().catch(()=>({}));
  if(!response.ok) throw Error(data.error || data.detail || "API error "+response.status);
  return data;
}
const initialTasks=[
  {id:"T01",title:"Review approved project scope",depends_on:[]},
  {id:"T02",title:"Prepare tests and Draft PR",depends_on:["T01"]}
];

export default function ProposalPanel({conversationId}) {
  const [items,setItems]=useState([]);
  const [selected,setSelected]=useState("");
  const [title,setTitle]=useState("");
  const [summary,setSummary]=useState("");
  const [diagram,setDiagram]=useState("flowchart TD; UI[User Interface] --> API[Review-only API]");
  const [tasks,setTasks]=useState(JSON.stringify(initialTasks,null,2));
  const [reason,setReason]=useState("Tôi đã đọc và đồng ý với đúng phiên bản bản nháp này.");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);

  const refresh=useCallback(async()=>{
    if(!conversationId)return;
    const data=await jsonRequest("conversations/"+conversationId+"/proposals");
    setItems(data.items||[]);
  },[conversationId]);

  useEffect(()=>{setSelected("");setItems([]);refresh().catch(e=>setError(e.message));},[refresh]);
  const current=items.find(x=>x.id===selected);
  let dirty=Boolean(current && (
    title!==current.content.title || summary!==current.content.summary ||
    diagram!==current.content.diagram
  ));
  if(current) {
    try { dirty ||= JSON.stringify(JSON.parse(tasks)) !== JSON.stringify(current.content.tasks); }
    catch { dirty=true; }
  }
  function load(item) {
    setSelected(item.id);setTitle(item.content.title);
    setSummary(item.content.summary);setDiagram(item.content.diagram);
    setTasks(JSON.stringify(item.content.tasks,null,2));
  }
  async function save(asRevision) {
    setError("");setBusy(true);
    try{
      const parsed=JSON.parse(tasks);
      if(!Array.isArray(parsed))throw Error("Tasks phải là một danh sách JSON");
      const content={title,summary,diagram,tasks:parsed};
      let path="proposals",body={...content,conversation_id:conversationId};
      if(asRevision&&current){path="proposals/"+current.id+"/revisions";body={...content,expected_version:current.version};}
      const result=await jsonRequest(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      await refresh();setSelected(result.id);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function decide(action) {
    if(!current)return;
    setBusy(true);setError("");
    try {
      await jsonRequest("proposals/"+current.id+"/decision",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({expected_version:current.version,expected_sha256:current.sha256,action,reason})
      });
      await refresh();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="proposalPanel">
    <h3>Thiết kế & phê duyệt / Design & Approval</h3>
    <p className="muted">Bản nháp do bạn nhập hoặc biên tập. Chưa có AI tự sinh sơ đồ. Phê duyệt chỉ ghi nhận quyết định, không kích hoạt Agent hay merge code.</p>
    <label htmlFor="proposal-choice">Phiên bản / Proposal</label>
    <select id="proposal-choice" value={selected} onChange={e=>{
      const item=items.find(x=>x.id===e.target.value);
      if(item)load(item);else setSelected("");
    }}>
      <option value="">Tạo bản nháp mới</option>
      {items.map(x=><option key={x.id} value={x.id}>{x.content.title} · V{x.version} · {x.status}</option>)}
    </select>
    {current&&<div className="proposalVersion">
      <strong>V{current.version} · {current.status}</strong>
      <small>SHA-256: {current.sha256}</small>
    </div>}
    <label htmlFor="proposal-title">Tên ứng dụng</label>
    <input id="proposal-title" value={title} maxLength={160} onChange={e=>setTitle(e.target.value)}/>
    <label htmlFor="proposal-summary">Phạm vi và yêu cầu</label>
    <textarea id="proposal-summary" rows={4} maxLength={6000} value={summary} onChange={e=>setSummary(e.target.value)}/>
    <label htmlFor="proposal-diagram">Sơ đồ Mermaid (chỉ lưu văn bản)</label>
    <textarea id="proposal-diagram" rows={3} maxLength={12000} value={diagram} onChange={e=>setDiagram(e.target.value)}/>
    <label htmlFor="proposal-tasks">Task DAG (JSON)</label>
    <textarea id="proposal-tasks" rows={7} value={tasks} onChange={e=>setTasks(e.target.value)}/>
    <button className="primary" disabled={busy} onClick={()=>save(Boolean(current))}>
      {current?"Lưu thành phiên bản mới / New revision":"Tạo bản nháp / Create draft"}
    </button>
    {current&&<div className="approvalActions">
      <p className="muted">Các nút chỉ quyết định bản đã lưu. Nếu bạn sửa nội dung phía trên, phải lưu phiên bản mới trước khi có thể duyệt.</p>
      <label htmlFor="proposal-reason">Lý do quyết định</label>
      <textarea id="proposal-reason" rows={2} minLength={3} maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/>
      <div className="decisionRow">
        <button disabled={busy||dirty||current.status!=="DRAFT"||reason.trim().length<3}
          onClick={()=>decide("APPROVE")}>Duyệt V{current.version}</button>
        <button disabled={busy||dirty||current.status!=="DRAFT"||reason.trim().length<3}
          onClick={()=>decide("REQUEST_CHANGES")}>Yêu cầu sửa</button>
        <button disabled={busy||dirty||current.status!=="DRAFT"||reason.trim().length<3}
          onClick={()=>decide("REJECT")}>Từ chối</button>
      </div>
    </div>}
    {error&&<p role="alert" className="error">{error}</p>}
  </section>;
}
