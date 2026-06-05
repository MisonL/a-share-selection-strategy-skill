"""Static assets for the local A-share HTML report."""

from __future__ import annotations


CSS = """
:root{color-scheme:light;--bg:#f6f7f9;--surface:#fff;--text:#18202a;--muted:#5d6978;--line:#dfe4ea;--accent:#0f766e;--danger:#b42318;--shadow:0 10px 30px rgba(15,23,42,.08)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.page{width:min(1180px,calc(100% - 32px));margin:0 auto;padding:28px 0 44px}
.hero,.section{background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}
.hero{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;padding:28px}
.eyebrow,.metric span,.facts dt,.note-card .note-label{color:var(--muted);font-size:12px;font-weight:700;text-transform:uppercase}
h1,h2,p{margin:0}
h1{font-size:30px;line-height:1.2}
h2{margin-bottom:16px;font-size:18px}
.hero-main p{margin-top:10px;color:var(--muted)}
.hero-actions{display:grid;justify-items:end;gap:12px}
.status{border:1px solid currentColor;border-radius:999px;padding:6px 12px;font-weight:700}
.status.ok{color:var(--accent)}
.status.failed{color:var(--danger)}
.language-toggle{display:flex;gap:6px}
.language-toggle button{border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--muted);font:inherit;font-weight:700;padding:5px 10px;cursor:pointer}
.language-toggle button.active{border-color:var(--accent);color:var(--accent)}
.section{margin-top:18px;padding:22px}
.metrics,.note-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.metric,.note-card{border:1px solid var(--line);border-radius:8px;padding:14px}
.metric strong{display:block;margin-top:6px;font-size:22px}
.note-card strong{display:block;margin-top:6px;font-size:16px}
.explain-lead{max-width:780px;margin-bottom:16px;color:var(--text);font-size:15px}
.limit-panel{margin-top:12px;border:1px solid #cbd5e1;border-left:4px solid var(--accent);border-radius:8px;padding:14px 16px;background:#f8fafc}
.limit-panel strong{display:block;margin-bottom:4px}
.limit-panel p{color:var(--muted)}
.boundary{margin-top:14px;color:var(--muted)}
.technical-details,.report-details{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.technical-details summary,.report-details summary{cursor:pointer;color:var(--muted);font-weight:700}
.technical-details summary span{display:block;margin-top:3px;font-size:12px;font-weight:400}
.facts{display:grid;grid-template-columns:minmax(170px,230px) 1fr;gap:10px 18px;margin:14px 0}
.facts dt{overflow-wrap:anywhere}
.facts dd{margin:0;min-width:0}
.empty{color:var(--muted)}
.table-note{margin-top:10px;color:var(--muted);font-size:13px}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;white-space:nowrap}
th,td{border-bottom:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}
th{color:var(--muted);font-size:12px;text-transform:uppercase}
td{max-width:340px;overflow:hidden;text-overflow:ellipsis}
td.text-cell{min-width:220px;max-width:460px;white-space:normal;overflow:visible;text-overflow:clip}
.evidence{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.evidence li{display:grid;grid-template-columns:minmax(130px,180px) 1fr;gap:12px}
.evidence span{color:var(--muted);font-weight:700}
code{white-space:normal;overflow-wrap:anywhere}
@media(max-width:700px){.page{width:min(100% - 20px,1180px);padding-top:10px}.hero{display:block;padding:20px}.hero-actions{justify-items:start;margin-top:16px}.facts,.evidence li{grid-template-columns:1fr}}
"""

JS = """
(() => {document.querySelectorAll('details.technical-details').forEach(el=>{el.open=false;});const storageKey='aShareSelectionReportLang';const root=document.documentElement;const mode=root.dataset.langMode||'auto';const generated=root.dataset.lang||'en';const saved=localStorage.getItem(storageKey);const initial=mode==='auto'?(saved||generated):mode;function setLang(lang){root.dataset.lang=lang;root.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-i18n-en]').forEach(el=>{el.textContent=el.dataset[lang==='zh'?'i18nZh':'i18nEn'];});const title=document.querySelector('title[data-i18n-title-en]');if(title){title.textContent=title.dataset[lang==='zh'?'i18nTitleZh':'i18nTitleEn'];}document.querySelectorAll('[data-set-lang]').forEach(btn=>btn.classList.toggle('active',btn.dataset.setLang===lang));localStorage.setItem(storageKey,lang);}document.querySelectorAll('[data-set-lang]').forEach(btn=>btn.addEventListener('click',()=>setLang(btn.dataset.setLang)));setLang(initial);})();
"""
