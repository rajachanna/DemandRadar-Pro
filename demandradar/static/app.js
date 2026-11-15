/* DemandRadar Pro — same-origin, operator-only; no third-party messages are sent. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&#39;"})[c]);
  const clip = (v, length = 100) => String(v ?? "").slice(0, length);
  const STATUSES = ["new", "shortlisted", "contacted", "replied", "won", "lost", "archived"];
  const LABELS = {python_contracts:"Python bounties", automation_help:"Automation help wanted", ai_workflows:"AI agent bounties", web_integrations:"Webhook / API issues", freelance:"Freelance developer discussions", automation:"Automation contractor discussions", contract:"Contract developer discussions"};
  const state = {key:sessionStorage.getItem("dr_operator_key") || "", session:null, items:[], toastTimer:null};
  function toast(message, error=false){
    const node=$("toast"); node.textContent=String(message); node.className="toast shown"+(error?" error":"");
    window.clearTimeout(state.toastTimer); state.toastTimer=window.setTimeout(()=>node.className="toast",4200);
  }
  async function api(url, opts={}) {
    const response = await fetch(url, {method:opts.method || "GET", headers:{"X-Operator-Key":state.key,...(opts.body?{"Content-Type":"application/json"}:{})}, body:opts.body?JSON.stringify(opts.body):undefined, cache:"no-store"});
    if(response.status===401){lock();throw Error("Operator session expired or key incorrect")}
    if(!response.ok){let description="HTTP "+response.status;try{const d=await response.json();description=d.detail || description;}catch(_){}throw Error(description)}
    return opts.raw ? response : response.json();
  }
  function lock(){state.key="";state.session=null;sessionStorage.removeItem("dr_operator_key");$("auth-overlay").hidden=false;$("sync-status").textContent="Not connected";$("auth-error").textContent="";}
  async function authenticate(key){state.key=String(key||"");try{const session=await api("/api/session");state.session=session;sessionStorage.setItem("dr_operator_key",state.key);$("auth-overlay").hidden=true;$("sync-status").textContent="Operator connected";$("demo-banner").hidden=!session.demo_mode;sourceQueries();await refresh();toast("Secure workspace connected");}catch(error){state.key="";sessionStorage.removeItem("dr_operator_key");$("auth-error").textContent=error.message;$("auth-overlay").hidden=false;}}
  function sourceQueries(){const keys=(state.session?.providers?.[$("source-provider").value])||[];$("source-query").innerHTML=keys.map(x=>`<option value="${esc(x)}">${esc(LABELS[x]||x)}</option>`).join("");}
  function date(value){if(!value)return "Date not provided";const d=new Date(value);return Number.isNaN(d.getTime())?"Date unavailable":d.toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"});}
  function sourceName(source){return {github_issues:"GitHub Issues",hacker_news:"Hacker News",manual:"Manual public link",synthetic_demo:"SYNTHETIC DEMO"}[source]||source;}
  function renderCategories(categories,total){const chart=$("category-chart");if(!categories.length){chart.innerHTML='<div class="chart-empty">No opportunities yet. Scan a supported public source or import a link.</div>';return;}
    const peak=Math.max(1,...categories.map(x=>x.count));chart.innerHTML=categories.map(x=>`<div class="chart-row"><span class="chart-label" title="${esc(x.category)}">${esc(x.category)}</span><div class="chart-track"><div class="chart-fill" style="width:${Math.max(4,Math.round(x.count/peak*100))}%"></div></div><span class="chart-number">${Number(x.count)}</span></div>`).join("");
  }
  function renderRows(items){state.items=items;$("sidebar-total").textContent=String(items.length);$("table-total").textContent=String(items.length);$("table-count").textContent=`${items.length} records shown`;
    if(!items.length){$("lead-rows").innerHTML='<tr><td colspan="5" class="table-placeholder">No matching public posts yet. Scan a source, import one link or change your filters.</td></tr>';return;}
    $("lead-rows").innerHTML=items.map(item=>`<tr><td><span class="post-title" title="${esc(item.title)}">${esc(clip(item.title,78))}</span><div class="post-sub">${esc(sourceName(item.source))} · ${esc(date(item.published_at))}${item.source==="synthetic_demo"?" · DEMO ONLY":""}</div></td><td><span class="score-pill ${item.score<55?"low":""}">◆ ${item.score}/100</span></td><td><span class="skill-tag">${esc(item.category)}</span></td><td><span class="state-pill ${esc(item.status)}">${esc(item.status)}</span></td><td><button type="button" data-record="${Number(item.id)}" class="row-action">Review ↗</button></td></tr>`).join("");
    $("lead-rows").querySelectorAll("[data-record]").forEach(node=>node.addEventListener("click",()=>openRecord(Number(node.dataset.record))));
  }
  async function refresh(){try{const [summary,records,scans]=await Promise.all([api("/api/summary"),api("/api/opportunities?"+new URLSearchParams({status:$("status-filter").value,q:$("search-filter").value,min_score:"0",limit:"250"})),api("/api/scans")]);
      $("stat-total").textContent=summary.total;$("stat-high").textContent=summary.high_priority;$("stat-contacted").textContent=summary.contacted;$("stat-won").textContent=summary.won;
      renderCategories(summary.categories,summary.total);renderRows(records.items);renderScans(scans.items);$("sync-status").textContent="Live workspace data";
    }catch(error){toast(error.message,true);}}
  function renderScans(scans){const node=$("scan-log");if(!scans.length){node.innerHTML='<div class="activity-empty">No scans recorded. Public API connections are optional; your saved opportunities remain local.</div>';return;}
    node.innerHTML=scans.slice(0,7).map(x=>`<div class="activity-item"><span class="activity-dot ${x.outcome==="failed"?"failed":""}"></span><div class="activity-copy"><strong>${esc(sourceName(x.source))} · ${esc(LABELS[x.search_key]||x.search_key)}</strong><small>${esc(date(x.occurred_at))} · ${esc(x.outcome)}${x.detail?" · "+esc(clip(x.detail,85)):""}</small></div><span class="activity-count">${x.new_count} new</span></div>`).join("");
  }
  async function scan(){const btn=$("scan-btn");btn.disabled=true;btn.textContent="Scanning public API...";$("scan-result").className="inline-status";$("scan-result").textContent="Connecting to a read-only source. No outreach will be sent.";
    try{const result=await api("/api/scan",{method:"POST",body:{provider:$("source-provider").value,search:$("source-query").value}});$("scan-result").textContent=`Received ${result.fetched} public records. ${result.new} added, ${result.duplicates} duplicates. Relevance & payment remain unverified.`;toast(`${result.new} new records imported`);await refresh();}
    catch(error){$("scan-result").className="inline-status error";$("scan-result").textContent="Scan could not complete: "+error.message;toast(error.message,true)}finally{btn.disabled=false;btn.textContent="◎   Scan source now";}
  }
  async function openRecord(recordId){let item;try{item=await api(`/api/opportunities/${recordId}`)}catch(e){toast(e.message,true);return;}
    $("drawer-overlay").hidden=false;
    const reasons=(item.reasons||[]).map(r=>`<div class="reason-item">${esc(r)}</div>`).join("");
    const statusSelect=STATUSES.map(x=>`<option value="${x}" ${x===item.status?"selected":""}>${x.charAt(0).toUpperCase()+x.slice(1)}</option>`).join("");
    $("drawer-content").innerHTML=`<h2 class="drawer-title">${esc(item.title)}</h2><div class="drawer-meta"><span class="score-pill ${item.score<55?"low":""}">◆ ${item.score}/100 · Rule score</span><span class="state-pill ${esc(item.status)}">${esc(item.status)}</span></div>
       <span class="detail-label">SOURCE & DATE</span><div class="detail-card">${esc(sourceName(item.source))} · ${esc(date(item.published_at))}${item.source==="synthetic_demo"?"<br>ILLUSTRATIVE SYNTHETIC RECORD — NOT A CLIENT":""}<br><a class="drawer-link" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.url)}</a></div>
       <span class="detail-label">PUBLIC POST DESCRIPTION</span><div class="drawer-description">${esc(item.description||"No summary supplied.")}</div>
       <span class="detail-label">WHY IT MATCHED</span><div class="detail-card">${reasons}<div class="drawer-warning" style="margin-top:12px">${item.budget_evidence?"Budget mention: "+esc(item.budget_evidence)+". ":"No explicit budget extracted. "}Payment, eligibility and legitimacy have not been verified.</div></div>
       <span class="detail-label">REVIEW STATUS & NOTES</span><select class="drawer-select" id="drawer-state">${statusSelect}</select><textarea class="drawer-notes" id="drawer-note" rows="3" maxlength="1500" placeholder="Document your verification or follow-up...">${esc(item.note||"")}</textarea><div class="drawer-actions"><button id="drawer-save" class="button button-outline">Save review status</button><button id="drawer-draft" class="button button-primary">Create proposal draft ↗</button></div>
       <span class="detail-label">MANUAL OUTREACH DRAFT</span><p class="drawer-warning">Drafts are not sent to anyone. Verify payment, platform rules, claims and contact permissions first.</p>
       <textarea class="drawer-textarea" id="drawer-draft-text" spellcheck="true" placeholder="Click Create proposal draft to start..." aria-label="Editable proposal draft"></textarea>
       <div class="drawer-actions"><button class="button button-outline" id="drawer-copy">Copy reviewed draft</button>${state.session?.ai_available?'<button class="button button-outline" id="drawer-ai">Generate optional AI draft</button>':""}${state.session?.telegram_available?'<button class="button button-outline" id="drawer-alert">Notify my Telegram</button>':""}</div><div id="drawer-msg" class="drawer-status"></div>`;
    $("drawer-save").addEventListener("click",async()=>{try{await api(`/api/opportunities/${recordId}/status`,{method:"PATCH",body:{status:$("drawer-state").value,note:$("drawer-note").value}});$("drawer-msg").textContent="Review status saved. No prospect contacted.";await refresh();}catch(e){toast(e.message,true)}});
    const draft=(mode)=>api(`/api/opportunities/${recordId}/draft`,{method:"POST",body:{mode}}).then(d=>{$("drawer-draft-text").value=d.text;$("drawer-msg").textContent=`${d.mode.toUpperCase()} draft — review required, not sent.`;}).catch(e=>toast(e.message,true));
    $("drawer-draft").addEventListener("click",()=>draft("template"));
    $("drawer-ai")?.addEventListener("click",()=>draft("ai"));
    $("drawer-copy").addEventListener("click",async()=>{const value=$("drawer-draft-text").value;if(!value)return toast("Generate or write a draft first",true);try{await navigator.clipboard.writeText(value);toast("Draft copied. No message sent.");}catch(_){$("drawer-draft-text").select();toast("Copy unavailable; draft selected for manual copying.");}});
    $("drawer-alert")?.addEventListener("click",async()=>{try{await api("/api/alerts/telegram",{method:"POST",body:{record_id:recordId}});toast("Notification sent to your configured Telegram channel only.");}catch(e){toast(e.message,true)}});
  }
  function closeDrawer(){$("drawer-overlay").hidden=true;$("drawer-content").textContent="";}
  async function exportCSV(){try{const response=await api("/api/exports/opportunities.csv",{raw:true});const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="demandradar-opportunities.csv";document.body.appendChild(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);toast("Local CSV export ready") }catch(e){toast(e.message,true)}}
  function showManual(){$("manual-overlay").hidden=false;$("manual-error").textContent="";}
  async function importManual(e){e.preventDefault();$("manual-error").textContent="";try{const r=await api("/api/opportunities/import",{method:"POST",body:{url:$("manual-url").value,title:$("manual-title-input").value,description:$("manual-description").value}});$("manual-overlay").hidden=true;$("manual-form").reset();toast(r.new?"Public link added to review queue":"Duplicate URL — existing record preserved");await refresh();}catch(error){$("manual-error").textContent=error.message;}}
  $("auth-form").addEventListener("submit",e=>{e.preventDefault();authenticate($("operator-key").value)});
  $("source-provider").addEventListener("change",sourceQueries);
  $("scan-btn").addEventListener("click",scan);
  $("scan-shortcut").addEventListener("click",()=>$("scanner").scrollIntoView({behavior:"smooth"}));
  $("manual-shortcut").addEventListener("click",showManual);$("manual-btn").addEventListener("click",showManual);
  $("close-manual").addEventListener("click",()=>$("manual-overlay").hidden=true);
  $("manual-form").addEventListener("submit",importManual);
  $("refresh-btn").addEventListener("click",refresh);$("export-btn").addEventListener("click",exportCSV);$("lock-btn").addEventListener("click",lock);
  $("status-filter").addEventListener("change",refresh);let searchTimer;$("search-filter").addEventListener("input",()=>{clearTimeout(searchTimer);searchTimer=setTimeout(refresh,220)});
  $("close-drawer").addEventListener("click",closeDrawer);$("drawer-scrim").addEventListener("click",closeDrawer);
  document.addEventListener("keydown",e=>{if(e.key==="Escape"){closeDrawer();$("manual-overlay").hidden=true;}});
  $("auth-overlay").hidden=false;
  if(state.key)authenticate(state.key);
})();
