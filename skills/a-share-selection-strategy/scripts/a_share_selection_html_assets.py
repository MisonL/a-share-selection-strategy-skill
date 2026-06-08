"""Static assets for the local A-share HTML report."""

from __future__ import annotations


CSS = """
:root{color-scheme:light;--bg:#eef1f3;--surface:#fff;--ink:#111827;--text:#1f2933;--muted:#64707d;--line:#d9e1e7;--soft:#f6f8fa;--accent:#0d7c66;--accent-strong:#063f36;--warm:#c57a00;--danger:#b42318;--shadow:0 18px 45px rgba(17,24,39,.12)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.page{width:min(1200px,calc(100% - 32px));margin:0 auto;padding:28px 0 48px}
.hero,.section{background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}
.hero{display:flex;align-items:stretch;justify-content:space-between;gap:24px;padding:0}
.executive-hero{position:relative;overflow:hidden;min-height:236px;border:0;background:#111;color:#f8fafc}
.executive-hero::before{content:"";position:absolute;inset:0;background:linear-gradient(120deg,rgba(13,124,102,.38),rgba(197,122,0,.18) 48%,rgba(255,255,255,0) 74%),repeating-linear-gradient(90deg,rgba(255,255,255,.08) 0 1px,transparent 1px 58px);opacity:.9}
.hero-main,.hero-actions{position:relative}
.hero-main{display:grid;align-content:center;flex:1;padding:38px 40px}
.eyebrow,.metric span,.facts dt,.note-card .note-label{color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase}
.executive-hero .eyebrow{color:#9ee6d7}
h1,h2,p{margin:0}
h1{font-size:44px;line-height:1.08;letter-spacing:0;margin-top:8px}
h2{margin-bottom:18px;font-size:20px;line-height:1.25}
.hero-main p{max-width:680px;margin-top:14px;color:#cbd5e1;font-size:17px}
.signal-bars{display:flex;align-items:end;gap:7px;height:44px;margin-top:28px}
.signal-bars span{display:block;width:18px;height:14px;border-radius:4px;background:rgba(255,255,255,.22)}
.signal-bars span:nth-child(2){height:22px}.signal-bars span:nth-child(3){height:30px}.signal-bars span:nth-child(4){height:38px}.signal-bars span:nth-child(5){height:44px}
.signal-bars span.active{background:#26d6a5}
.hero-actions{display:grid;align-content:center;justify-items:end;gap:12px;min-width:190px;padding:32px 30px;background:rgba(255,255,255,.08);border-left:1px solid rgba(255,255,255,.12)}
.status{border:1px solid currentColor;border-radius:999px;padding:7px 13px;font-weight:800}
.status.ok{color:#26d6a5}
.status.failed{color:var(--danger)}
.language-toggle{display:flex;gap:6px}
.language-toggle button{min-height:34px;border:1px solid rgba(255,255,255,.28);border-radius:999px;background:rgba(255,255,255,.12);color:#d7dee8;font:inherit;font-weight:800;padding:5px 12px;cursor:pointer}
.language-toggle button.active{border-color:#26d6a5;color:#26d6a5;background:rgba(38,214,165,.12)}
.section{margin-top:20px;padding:26px}
.executive-summary{display:grid;grid-template-columns:1.1fr 1.4fr .8fr;gap:16px;margin-bottom:18px}
.executive-summary>div{border:1px solid var(--line);border-radius:8px;background:var(--soft);padding:18px}
.executive-summary span,.summary-highlight span{display:block;color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase}
.executive-summary strong{display:block;margin-top:8px;color:var(--ink);font-size:22px;line-height:1.25}
.executive-summary ul{margin:8px 0 0;padding-left:18px;color:var(--text)}
.executive-summary li+li{margin-top:5px}
.summary-highlight{background:var(--ink)!important;color:#fff!important}
.summary-highlight strong{color:#fff}.summary-highlight small{display:block;margin-top:5px;color:#cbd5e1}
.metrics,.note-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.metric,.note-card{border:1px solid var(--line);border-radius:8px;padding:16px;background:#fff}
.metric strong{display:block;margin-top:7px;color:var(--ink);font-size:28px;line-height:1}
.note-card strong{display:block;margin-top:7px;color:var(--ink);font-size:17px}
.explain-lead{max-width:820px;margin-bottom:16px;color:var(--text);font-size:16px}
.limit-panel{margin-top:14px;border:1px solid #b9d7ce;border-left:5px solid var(--accent);border-radius:8px;padding:16px 18px;background:#f4fbf8}
.limit-panel strong{display:block;margin-bottom:4px}
.limit-panel p{color:var(--muted)}
.disclosure-alerts{margin:12px 0 0;padding:0;list-style:none;display:grid;gap:8px}
.disclosure-alerts li{border:1px solid #f0cf9d;border-left:5px solid var(--warm);border-radius:8px;background:#fff8ed;padding:12px 14px;color:#6c3d00}
.boundary{margin-top:14px;color:var(--muted)}
.technical-details,.report-details{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.technical-details summary,.report-details summary{cursor:pointer;color:var(--muted);font-weight:700}
.technical-details summary span{display:block;margin-top:3px;font-size:12px;font-weight:400}
.facts{display:grid;grid-template-columns:minmax(170px,230px) 1fr;gap:10px 18px;margin:14px 0}
.facts dt{overflow-wrap:anywhere}
.facts dd{margin:0;min-width:0}
.empty{color:var(--muted)}
.candidate-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-bottom:18px}
.candidate-card{position:relative;display:grid;gap:14px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:18px;overflow:hidden}
.candidate-card::before{content:"";position:absolute;inset:0 0 auto 0;height:4px;background:var(--accent)}
.candidate-rank{width:max-content;border-radius:999px;background:#e7f6f2;color:var(--accent-strong);font-weight:800;padding:4px 10px}
.candidate-main strong{display:block;color:var(--ink);font-size:22px;line-height:1.2}.candidate-main span{color:var(--muted);font-weight:700}
.candidate-score{display:flex;align-items:end;justify-content:space-between;border-top:1px solid var(--line);padding-top:12px}.candidate-score span{color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase}.candidate-score strong{font-size:30px;color:var(--accent-strong);line-height:1}
.candidate-facts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.candidate-facts span{border-radius:8px;background:var(--soft);padding:10px;color:var(--muted);font-size:12px}.candidate-facts strong{display:block;margin-top:2px;color:var(--ink);font-size:14px}
.candidate-copy{display:grid;gap:8px;color:var(--text)}.candidate-copy p{font-size:14px}.candidate-copy b{display:block;color:var(--ink);margin-bottom:2px}.candidate-copy small{color:#6c3d00;font-weight:800}
.detail-table-heading{display:flex;align-items:end;justify-content:space-between;gap:18px;margin:8px 0 10px;border-top:1px solid var(--line);padding-top:16px}.detail-table-heading strong{font-size:16px}.detail-table-heading p{color:var(--muted);font-size:13px}
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
@media(max-width:820px){.page{width:min(100% - 20px,1200px);padding-top:10px}.hero{display:block}.hero-main{padding:30px 24px}.hero-actions{justify-items:start;min-width:0;border-left:0;border-top:1px solid rgba(255,255,255,.12);padding:20px 24px}.executive-summary{grid-template-columns:1fr}.candidate-facts{grid-template-columns:1fr}.detail-table-heading{display:block}.detail-table-heading p{margin-top:4px}.facts,.evidence li{grid-template-columns:1fr}h1{font-size:34px}.section{padding:20px}}
"""

JS = """
(() => {document.querySelectorAll('details.technical-details').forEach(el=>{el.open=false;});const storageKey='aShareSelectionReportLang';const root=document.documentElement;const mode=root.dataset.langMode||'auto';const generated=root.dataset.lang||'en';const saved=localStorage.getItem(storageKey);const initial=mode==='auto'?(saved||generated):mode;function setLang(lang){root.dataset.lang=lang;root.lang=lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-i18n-en]').forEach(el=>{el.textContent=el.dataset[lang==='zh'?'i18nZh':'i18nEn'];});const title=document.querySelector('title[data-i18n-title-en]');if(title){title.textContent=title.dataset[lang==='zh'?'i18nTitleZh':'i18nTitleEn'];}document.querySelectorAll('[data-set-lang]').forEach(btn=>btn.classList.toggle('active',btn.dataset.setLang===lang));localStorage.setItem(storageKey,lang);}document.querySelectorAll('[data-set-lang]').forEach(btn=>btn.addEventListener('click',()=>setLang(btn.dataset.setLang)));setLang(initial);})();
"""
