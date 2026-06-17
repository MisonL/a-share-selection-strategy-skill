"""Static assets for the local A-share HTML report."""
from __future__ import annotations
CSS = """
:root{color-scheme:light;--bg:#f8fafc;--surface:#fff;--ink:#111d2f;--text:#243247;--muted:#637083;--line:#d8e0ea;--line-strong:#c5d0dd;--soft:#f7fafc;--green:#0a8f63;--green-dark:#047857;--blue:#1b75d0;--orange:#d97706;--red:#c73535;--shadow:0 8px 22px rgba(15,23,42,.07);--shadow-soft:0 12px 30px rgba(15,23,42,.09)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
	body{margin:0;background:linear-gradient(180deg,#fbfdff 0,#f8fafc 340px,#f8fafc 100%);color:var(--text);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
		.page{width:min(2048px,calc(100% - 40px));margin:0 auto;padding:8px 0 20px}
h1,h2,h3,p{margin:0}h2{font-size:21px;line-height:1.25;color:var(--ink)}h3{font-size:20px;line-height:1.25;color:var(--ink)}
.hero,.section,.panel-card{background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}
	.executive-hero{background:transparent;border:0;border-radius:0;box-shadow:none;padding:0 10px 0;color:var(--ink)}
	.hero-title-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(520px,600px);gap:34px;align-items:start}
	.hero-copy h1{font-family:Georgia,"Times New Roman","Songti SC",serif;font-size:56px;line-height:.96;letter-spacing:0;color:#101b2d}
	.hero-badges{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
	.hero-badge{display:inline-flex;align-items:center;min-height:30px;border:1px solid var(--line);border-radius:6px;background:#fff;color:#26384f;font-weight:800;padding:5px 13px}
.hero-badge.ok{border-color:#8fcfb4;color:#047857;background:#f5fbf8}.hero-badge.blue{border-color:#aecbed;color:#1b65b8;background:#f5f9ff}.hero-badge.warn{border-color:#e7bf75;color:#a15c00;background:#fff9ee}.hero-badge.purple{border-color:#cbbbe8;color:#5f43a6;background:#faf7ff}.hero-badge.danger{border-color:#ecaaa5;color:#b42318;background:#fff7f6}
.hero-note{display:flex;align-items:center;gap:8px;margin-top:9px;color:#334155;font-size:14px}
.hero-note::before{content:"i";display:inline-grid;place-items:center;width:18px;height:18px;border:1px solid #64748b;border-radius:50%;font-size:12px;font-weight:900;color:#334155}
.hero-side{display:block}
.hero-fact-card{position:relative;width:100%;min-height:112px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:8px 18px;box-shadow:var(--shadow-soft)}
.hero-fact-card::after{display:none}
.hero-fact-card div{position:relative;display:grid;grid-template-columns:92px 1fr;gap:14px;padding:3px 0 3px 22px}
.hero-fact-card div::before{content:"";position:absolute;left:0;top:8px;width:13px;height:13px;border:1px solid #9aa8b7;border-radius:3px;background:linear-gradient(#9aa8b7,#9aa8b7) 3px 3px/7px 1px no-repeat,linear-gradient(#9aa8b7,#9aa8b7) 3px 7px/7px 1px no-repeat,#fff}
.hero-fact-card span{color:#526173;font-weight:800}.hero-fact-card strong{color:#1e293b;font-weight:800}
.section{margin-top:8px;padding:10px}.section>h2{display:flex;align-items:center;gap:10px;margin-bottom:14px}.section>h2::before{content:"";display:block;width:6px;height:22px;border-radius:5px;background:var(--green)}
.dashboard-section,.watchlist-section{padding:0;background:transparent;border:0;box-shadow:none}
	.report-overview-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(520px,1fr);gap:12px}
.pipeline-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:0;align-items:stretch;border:1px solid var(--line);border-radius:8px;background:#fff;overflow:hidden}
		.pipeline-card{display:grid;grid-template-columns:54px minmax(0,1fr);gap:13px;align-items:center;min-height:84px;border-right:1px solid var(--line);padding:8px 18px;background:#fff}
.pipeline-card:last-child{border-right:0}
	.pipeline-icon{position:relative;width:48px;height:48px;border-radius:50%;background:#13a266;box-shadow:inset 0 -8px 16px rgba(0,0,0,.08)}
.pipeline-icon::before,.pipeline-icon::after{content:"";position:absolute;background:#fff}.pipeline-icon::before{left:15px;top:16px;width:24px;height:18px;clip-path:polygon(0 0,100% 0,64% 45%,64% 100%,36% 100%,36% 45%)}.pipeline-icon::after{display:none}
.pipeline-icon.circle::before{left:14px;top:14px;width:10px;height:10px;border-radius:50%;box-shadow:15px 0 0 #fff,7px 14px 0 4px #fff;clip-path:none}.pipeline-icon.eye::before{left:10px;top:14px;width:28px;height:18px;border:4px solid #fff;border-radius:50%;background:transparent;clip-path:none}.pipeline-icon.eye::after{display:block;left:21px;top:20px;width:6px;height:6px;border-radius:50%;background:#fff}.pipeline-icon.shield::before{left:13px;top:8px;width:22px;height:27px;background:#fff;clip-path:polygon(50% 0,88% 14%,80% 70%,50% 100%,20% 70%,12% 14%)}.pipeline-icon.shield::after{display:block;left:23px;top:14px;width:4px;height:10px;border-radius:2px;background:#f59e0b;box-shadow:0 14px 0 -1px #f59e0b}
.pipeline-card.input .pipeline-icon{background:#1f7eea}.pipeline-card.passed .pipeline-icon{background:#12a36f}.pipeline-card.watch .pipeline-icon{background:#1e88e5}.pipeline-card.risk .pipeline-icon{background:#f59e0b}.pipeline-card span:not(.pipeline-icon){display:block;color:#174034;font-weight:900}
.pipeline-card.passed span:not(.pipeline-icon){color:#174a82}.pipeline-card.watch span:not(.pipeline-icon){color:#7a4300}.pipeline-card.risk span:not(.pipeline-icon){color:#991b1b}.pipeline-card strong{display:block;margin-top:2px;color:#111827;font-size:27px;line-height:1.02;letter-spacing:0}.pipeline-card small{display:block;margin-top:3px;color:#475569;font-size:13px;line-height:1.28}
.selection-flow-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:9px 20px}
.selection-flow-card h2{display:flex;align-items:baseline;gap:8px;margin-bottom:7px}.selection-flow-card h2 span{color:#667085;font-size:15px;font-weight:600}
.selection-flow{display:grid;grid-template-columns:repeat(7,max-content);justify-content:center;align-items:center;gap:22px}
.flow-step{display:grid;justify-items:center;min-width:86px;color:#1e293b;text-align:center}
	.flow-index{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;background:#1b75d0;color:#fff;font-size:19px;font-weight:900}
.flow-step.input .flow-index{background:#1b75d0}.flow-step.passed .flow-index{background:#0b8f63}.flow-step.watch .flow-index{background:#1b75d0}.flow-step.risk .flow-index{background:#f08a00}
.flow-step span:not(.flow-index){display:block;margin-top:7px;color:#0f172a;font-weight:900}
.flow-step strong{display:block;margin-top:2px;color:#334155;font-weight:700}
.flow-step small{display:block;margin-top:1px;color:#64748b;font-size:12px}
.flow-arrow{width:88px;height:2px;background:#64748b;position:relative}
.flow-arrow::after{content:"";position:absolute;right:-1px;top:-5px;width:11px;height:11px;border-top:2px solid #64748b;border-right:2px solid #64748b;transform:rotate(45deg)}
.metrics,.note-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.metric,.note-card{border:1px solid var(--line);border-radius:8px;padding:16px;background:#fff}
.metric>span,.facts dt,.note-card .note-label{color:var(--muted);font-size:12px;font-weight:800}
.metric strong{display:block;margin-top:7px;color:var(--ink);font-size:28px;line-height:1}
.note-card strong{display:block;margin-top:7px;color:var(--ink);font-size:17px}
.limit-panel{margin-top:14px;border:1px solid #b9d7ce;border-left:5px solid var(--green);border-radius:8px;padding:16px 18px;background:#f5fbf8}
.limit-panel strong{display:block;margin-bottom:4px}.limit-panel p{color:var(--muted)}
	.disclosure-alerts{margin:8px 0 0;padding:0;list-style:none;display:grid;gap:6px}
	.disclosure-alerts li{border:1px solid #f0cf9d;border-left:5px solid var(--orange);border-radius:8px;background:#fff8ed;padding:8px 12px;color:#6c3d00;font-size:14px}
.boundary{margin-top:14px;color:var(--muted)}
.technical-details,.report-details{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.technical-details summary,.report-details summary{cursor:pointer;color:var(--muted);font-weight:700}
.report-details summary{width:max-content;max-width:100%;border:1px solid var(--line);border-radius:8px;background:#fff;padding:9px 12px;color:var(--green-dark)}
.report-details[open] summary{margin-bottom:12px}
.technical-details summary span{display:block;margin-top:3px;font-size:12px;font-weight:400}
.review-note,.diagnostic-intro{color:var(--muted);margin-bottom:12px}
.facts{display:grid;grid-template-columns:minmax(170px,230px) 1fr;gap:10px 18px;margin:14px 0}
.facts dt{overflow-wrap:anywhere}.facts dd{margin:0;min-width:0}
.empty{color:var(--muted)}
	.watchlist-dashboard{display:grid;grid-template-columns:minmax(560px,1.26fr) minmax(380px,.76fr) minmax(500px,1.06fr);gap:12px;align-items:stretch}
		.watchlist-preview-pane,.operator-checklist,.candidate-entry-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:11px}
.candidate-cards[data-preview-table]{display:block}
.candidate-cards[data-preview-table] table{table-layout:fixed;white-space:normal}
.candidate-cards[data-preview-table] th,.candidate-cards[data-preview-table] td{padding:7px 9px;line-height:1.35}
.candidate-cards[data-preview-table] th:nth-child(1),.candidate-cards[data-preview-table] td:nth-child(1){width:190px}
.candidate-cards[data-preview-table] th:nth-child(2),.candidate-cards[data-preview-table] td:nth-child(2){width:82px}
.candidate-cards[data-preview-table] th:nth-child(3),.candidate-cards[data-preview-table] td:nth-child(3){width:110px}
.preview-heading{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:7px}
.preview-heading h3{font-size:20px}.preview-heading p{margin-top:4px;color:var(--muted);font-size:13px}
		.candidate-open-slot{display:grid;align-items:stretch;justify-items:stretch;min-height:100%}
			.candidate-open-banner{display:grid;gap:9px;align-content:center;justify-items:center;width:100%;height:100%;min-height:196px;border:1px solid #42b18d;border-radius:8px;background:linear-gradient(180deg,#fbfffd 0,#f2fbf6 100%);padding:16px 22px 14px;color:#1e293b;text-align:center;text-decoration:none;box-shadow:inset 0 0 0 1px rgba(26,153,112,.04)}
.candidate-open-banner:hover{border-color:var(--green);background:linear-gradient(180deg,#f4fbf7 0,#e9f8f1 100%)}
	.candidate-open-title{position:relative;display:inline-flex;align-items:center;gap:8px;color:var(--green-dark);font-size:18px;line-height:1.2;font-weight:900}.candidate-open-title::before{content:"";width:18px;height:20px;border:2px solid var(--green);border-radius:3px;background:linear-gradient(var(--green),var(--green)) 5px 5px/7px 2px no-repeat,linear-gradient(var(--green),var(--green)) 5px 10px/7px 2px no-repeat,linear-gradient(var(--green),var(--green)) 5px 15px/7px 2px no-repeat}
	.candidate-open-body{max-width:380px;color:#475569;font-size:13px;line-height:1.45}.candidate-open-button{display:inline-flex;align-items:center;min-height:34px;border:1px solid var(--line);border-radius:6px;background:#fff;color:#1e293b;font-weight:800;padding:5px 18px;box-shadow:0 4px 10px rgba(15,23,42,.04)}
	.candidate-open-foot{position:relative;color:#334155;font-size:12px;font-weight:700;text-align:center;width:100%;padding-bottom:14px}.candidate-open-foot::after{content:"";position:absolute;left:50%;bottom:0;width:9px;height:9px;border-right:2px solid var(--green-dark);border-bottom:2px solid var(--green-dark);transform:translateX(-50%) rotate(45deg)}
.operator-checklist h3{display:grid;gap:2px;margin-bottom:7px}.operator-checklist h3 span{color:var(--muted);font-size:13px;font-weight:700}
.check-item{display:grid;grid-template-columns:18px 1fr;gap:10px;align-items:start;padding:4px 0;color:#2f3f54}
.check-dot{position:relative;width:17px;height:17px;margin-top:2px;border:1px solid #3fb083;border-radius:50%;background:#f4fbf8}.check-dot::after{content:"";position:absolute;left:5px;top:3px;width:5px;height:9px;border-right:2px solid #0b8f63;border-bottom:2px solid #0b8f63;transform:rotate(40deg)}
		.candidate-master-detail{margin-top:8px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px;box-shadow:0 8px 20px rgba(15,23,42,.04);scroll-margin-top:18px}
		.master-detail-header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:10px}
	.master-detail-header h3{font-size:20px}.master-detail-header p{margin-top:4px;max-width:760px;color:var(--muted);font-size:13px;line-height:1.35}
.file-chip{display:inline-block;border:1px solid #a6d8c5;border-radius:7px;background:#f4fbf8;padding:6px 11px;color:var(--green-dark)}
.field-notice{margin:-2px 0 9px;border:1px solid #f0cf9d;border-left:5px solid var(--orange);border-radius:8px;background:#fffaf0;padding:8px 12px;color:#6c3d00;font-size:13px;line-height:1.4}
.candidate-toolbar{display:grid;grid-template-columns:2fr repeat(4,minmax(130px,1fr)) auto;gap:9px;margin-bottom:7px;align-items:end}
.candidate-toolbar label{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;font-weight:800}
.candidate-toolbar label span{white-space:nowrap}
.candidate-toolbar label input,.candidate-toolbar label select{flex:1;min-width:0}
.candidate-toolbar input,.candidate-toolbar select,.candidate-toolbar button{height:36px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font:inherit;padding:6px 10px}
.candidate-toolbar button{min-width:54px;color:#64748b;cursor:pointer;box-shadow:0 2px 7px rgba(15,23,42,.04)}
		.master-detail-grid{display:grid;grid-template-columns:minmax(0,1.22fr) minmax(560px,.98fr);gap:12px;align-items:stretch}
.master-list-panel{min-width:0}
			.master-table{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff}
.master-table table{white-space:normal}
	.master-table th{position:sticky;top:0;z-index:1;background:#f8fafc;color:#27384f}
.master-table tr[data-candidate-row]{cursor:pointer}
.master-table tr[data-candidate-row]:hover{background:#f8fcfa}
.master-table tr[data-selected="true"]{background:#eaf4ff;outline:2px solid #6daff0;outline-offset:-2px}
.sparse-note{display:grid;place-items:center;min-height:104px;border-top:1px dashed var(--line);color:#64748b;font-size:13px;background:linear-gradient(180deg,#fff,#fbfdff)}
.row-check{display:inline-grid;place-items:center;width:16px;height:16px;border:1px solid var(--line);border-radius:4px;background:#fff}
tr[data-selected="true"] .row-check{background:#1683df;border-color:#1683df}
tr[data-selected="true"] .row-check::after{content:"";width:6px;height:9px;border-right:2px solid #fff;border-bottom:2px solid #fff;transform:rotate(40deg)}
.symbol-cell{color:#475569;font-weight:650;letter-spacing:.01em}.name-cell{color:#172033;font-weight:760}
.stock-anchor{display:block;color:#0f3a65;font-size:15px}.stock-anchor+span{display:block;color:#334155;font-size:13px}
.level-badge,.risk-badge{display:inline-flex;align-items:center;width:max-content;max-width:100%;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:850;border:0}
.level-badge{background:#e7f1ff;color:#175cd3}
.level-badge.high{background:#fff1df;color:#b54708}
.level-badge.medium{background:#e7f1ff;color:#175cd3}
.level-badge.low{background:#eef2f7;color:#475569}
.risk-badge.notice{background:#ecfdf3;color:#067647;border:1px solid #abefc6}
.risk-badge.attention{background:#fffaeb;color:#b54708;border:1px solid #fedf89}
.risk-badge.high{background:#fef3f2;color:#b42318;border:1px solid #fecdca}
			.candidate-detail-panel{align-self:stretch;height:100%;border:1px solid var(--line);border-radius:8px;background:#fff;min-width:0;overflow:hidden;box-shadow:0 8px 18px rgba(15,23,42,.04)}
			.detail-head{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding:11px 14px 9px}
		.detail-head h3{font-size:21px}.detail-head span{color:var(--muted);font-weight:700}.detail-head b{color:#334155}
	.detail-body{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(220px,.92fr);min-height:0}
	.detail-main{min-width:0;border-right:1px solid var(--line)}
	.detail-main .detail-grid:last-child{border-bottom:0}
	.detail-evidence-card{display:grid;align-content:start;gap:9px;padding:12px 14px;background:#f8fafc;border-left:1px solid #e7edf4}
	.detail-evidence-card span{color:#1e293b;font-weight:900;font-size:13px;line-height:1.35}
.detail-evidence-card p{margin:0;border:1px solid #e7edf4;border-radius:7px;background:#fff;padding:11px 12px;color:var(--text);line-height:1.62;white-space:pre-line;word-break:break-word;box-shadow:0 3px 10px rgba(15,23,42,.03)}
	.detail-grid{display:grid;grid-template-columns:146px 1fr;border-bottom:1px solid #e7edf4}
	.detail-grid:last-child{border-bottom:0}
		.detail-grid>span{display:flex;align-items:center;gap:8px;background:#fbfdff;color:#1e293b;font-weight:900;padding:9px 12px;border-right:1px solid #e7edf4;font-size:13px;line-height:1.35}
		.detail-grid p{min-width:0;padding:9px 12px;color:var(--text);line-height:1.5}
	.master-table-footer{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:8px;color:#475569}
.candidate-pager{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.candidate-pager button,.candidate-pager select{min-height:34px;border:1px solid #d6e0eb;border-radius:7px;background:#fff;color:#1e293b;font:inherit;padding:5px 11px;box-shadow:0 2px 8px rgba(15,23,42,.04)}
.candidate-pager button{cursor:pointer}.candidate-pager button:not(:disabled):hover{border-color:#9cc7ee;background:#f7fbff}.candidate-pager button:disabled{opacity:.48;cursor:not-allowed;box-shadow:none}
.candidate-page-numbers{display:flex;align-items:center;gap:6px}.candidate-page-number{min-width:32px;height:32px;border:1px solid #d6e0eb;border-radius:7px;background:#fff;color:#1e293b;font:inherit;box-shadow:0 2px 8px rgba(15,23,42,.04);cursor:pointer}.candidate-page-number.active{border-color:#1b75d0;background:#1b75d0;color:#fff}.candidate-page-ellipsis{color:#64748b;padding:0 2px}.candidate-page-status{color:#334155}
	.final-notice-grid{display:grid;grid-template-columns:.88fr 1fr;gap:16px}
			.result-notice-card,.disclaimer-card{min-height:112px;display:grid;grid-template-columns:1fr;gap:12px;align-items:center;border:1px solid var(--line);border-radius:8px;background:#fff;padding:18px 22px}
.result-notice-card{border-color:#e5b45d;background:#fffaf2}.disclaimer-card{border-color:#80b6ef;background:#f8fbff}
	.result-notice-card h3,.disclaimer-card h3{position:relative;padding-left:38px;font-size:18px;line-height:1.2}.result-notice-card h3::before,.disclaimer-card h3::before{content:"";position:absolute;left:0;top:1px;width:26px;height:24px}.result-notice-card h3::before{background:#f59e0b;clip-path:polygon(50% 0,100% 88%,0 88%);border-radius:4px}.result-notice-card h3::after{content:"!";position:absolute;left:10px;top:2px;color:#fff;font-size:18px;font-weight:900}.disclaimer-card h3::before{background:#1b75d0;clip-path:polygon(50% 0,100% 18%,86% 82%,50% 100%,14% 82%,0 18%);border-radius:4px}.disclaimer-card h3::after{content:"";position:absolute;left:8px;top:6px;width:10px;height:13px;border:2px solid #fff;border-top:0;border-radius:0 0 7px 7px}.result-notice-card p,.disclaimer-card p{margin-top:6px;color:#344054;line-height:1.5}
.result-notice-illustration,.disclaimer-illustration{display:none}
.disclaimer-illustration{background:linear-gradient(135deg,#d9e9fb,#cbdff7)}
.result-notice-illustration::before,.result-notice-illustration::after,.disclaimer-illustration::before,.disclaimer-illustration::after{display:none}
.detail-table-heading{display:flex;align-items:end;justify-content:space-between;gap:18px;margin:8px 0 10px;border-top:1px solid var(--line);padding-top:16px}
.detail-table-heading strong{font-size:16px}.detail-table-heading p{color:var(--muted);font-size:13px}
.table-note{margin-top:10px;color:var(--muted);font-size:13px}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;white-space:nowrap}
th,td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{color:#334155;font-size:12px;background:#f8fafc}
td{max-width:340px;overflow:hidden;text-overflow:ellipsis}
td.text-cell{min-width:220px;max-width:460px;white-space:normal;overflow:visible;text-overflow:clip}
.evidence{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.evidence li{display:grid;grid-template-columns:minmax(130px,180px) 1fr;gap:12px}
.evidence span{color:var(--muted);font-weight:700}
code{white-space:normal;overflow-wrap:anywhere}
@media(max-width:1280px){.hero-title-row,.report-overview-grid,.watchlist-dashboard,.final-notice-grid{grid-template-columns:1fr}.selection-flow{grid-template-columns:repeat(4,1fr);gap:12px}.flow-arrow{display:none}.candidate-open-banner{min-height:160px}.master-detail-grid{grid-template-columns:1fr}.detail-body{grid-template-columns:1fr}.detail-main{border-right:0;border-bottom:1px solid var(--line)}.hero-fact-card{max-width:none}}
@media(max-width:900px){.page{width:min(100% - 20px,1200px);padding-top:12px}.pipeline-metrics,.candidate-toolbar{grid-template-columns:1fr}.pipeline-card{border-right:0;border-bottom:1px solid var(--line)}.pipeline-card:last-child{border-bottom:0}.selection-flow{grid-template-columns:1fr}.hero-copy h1{font-size:40px}.hero-fact-card{padding-right:18px}.hero-fact-card::after{display:none}.master-detail-header,.detail-table-heading,.preview-heading,.master-table-footer{display:block}.facts,.evidence li,.detail-grid,.hero-fact-card div{grid-template-columns:1fr}.detail-grid>span{border-right:0;border-bottom:1px solid var(--line)}.section{padding:14px}}
"""
JS = """
(() => {
  document.querySelectorAll('details.technical-details').forEach(el => { el.open = false; });
  const storageKey = 'aShareSelectionReportLang';
  const root = document.documentElement;
  const mode = root.dataset.langMode || 'auto';
  const generated = root.dataset.lang || 'en';
  const saved = localStorage.getItem(storageKey);
  const initial = mode === 'auto' ? (saved || generated) : mode;
  function setLang(lang) {
    root.dataset.lang = lang;
    root.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.querySelectorAll('[data-i18n-en]').forEach(el => {
      el.textContent = el.dataset[lang === 'zh' ? 'i18nZh' : 'i18nEn'];
    });
    const title = document.querySelector('title[data-i18n-title-en]');
    if (title) {
      title.textContent = title.dataset[lang === 'zh' ? 'i18nTitleZh' : 'i18nTitleEn'];
    }
    document.querySelectorAll('[data-set-lang]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.setLang === lang);
    });
    localStorage.setItem(storageKey, lang);
  }
  function initCandidateMasterDetail() {
    document.querySelectorAll('[data-candidate-master-detail]').forEach(rootEl => {
      let rows = Array.from(rootEl.querySelectorAll('[data-candidate-row]'));
      const search = rootEl.querySelector('[data-candidate-search]');
	const board = rootEl.querySelector('[data-candidate-board]');
	const industry = rootEl.querySelector('[data-candidate-industry]');
      const level = rootEl.querySelector('[data-candidate-level]');
      const sort = rootEl.querySelector('[data-candidate-sort]');
      const reset = rootEl.querySelector('[data-candidate-reset]');
      const pageSize = rootEl.querySelector('[data-candidate-page-size]');
      const prev = rootEl.querySelector('[data-candidate-prev]');
      const next = rootEl.querySelector('[data-candidate-next]');
      const count = rootEl.querySelector('[data-candidate-visible-count]');
      const total = rootEl.querySelector('[data-candidate-total-count]');
      const pageCurrent = rootEl.querySelector('[data-candidate-page-current]');
      const pageTotal = rootEl.querySelector('[data-candidate-page-total]');
      const pageNumbers = rootEl.querySelector('[data-candidate-page-numbers]');
      const detail = rootEl.querySelector('[data-candidate-detail]');
      let currentPage = 1;
      function pageLimit() {
        return Number(pageSize?.value || 10) || 10;
      }
      function rowMatches(row) {
        const query = (search?.value || '').trim().toLowerCase();
        return (!query || (row.dataset.search || '').includes(query))
          && (!(board?.value || '') || row.dataset.board === board.value)
          && (!(industry?.value || '') || row.dataset.industry === industry.value)
          && (!(level?.value || '') || row.dataset.level === level.value);
      }
      function setText(attr, value) {
        detail.querySelectorAll(`[data-${attr}]`).forEach(el => { el.textContent = value || ''; });
      }
      function setDetail(row) {
        if (!row || !detail) {
          return;
        }
        rows.forEach(item => { item.dataset.selected = item === row ? 'true' : 'false'; });
        const textMap = { rowTitle: 'detail-title', rowDate: 'detail-date', rowSummary: 'detail-summary', rowReason: 'detail-reason', rowAction: 'detail-action', rowEvidence: 'detail-evidence' };
        Object.entries(textMap).forEach(([key, attr]) => setText(attr, row.dataset[key]));
        detail.querySelectorAll('[data-detail-level]').forEach(el => {
          el.textContent = row.dataset.rowLevel || '';
          el.className = 'level-badge ' + (row.dataset.rowLevelClass || 'low');
        });
        const riskEl = detail.querySelector('[data-detail-risk]');
        if (riskEl) { riskEl.textContent = row.dataset.risk || ''; riskEl.className = 'risk-badge ' + (row.dataset.rowRiskClass || 'notice'); }
      }
      function renderPages(pages) {
        if (!pageNumbers) { return; }
        pageNumbers.textContent = '';
        const makeButton = page => {
          const button = document.createElement('button');
          button.type = 'button'; button.className = 'candidate-page-number' + (page === currentPage ? ' active' : ''); button.textContent = String(page);
          button.addEventListener('click', () => { currentPage = page; render(); });
          pageNumbers.appendChild(button);
        };
        const visiblePages = new Set([1, pages, currentPage - 1, currentPage, currentPage + 1]);
        let previousPage = 0;
        [...visiblePages].filter(page => page >= 1 && page <= pages).sort((a, b) => a - b).forEach(page => {
          if (previousPage && page - previousPage > 1) {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'candidate-page-ellipsis'; ellipsis.textContent = '...'; pageNumbers.appendChild(ellipsis);
          }
          makeButton(page); previousPage = page;
        });
      }
        function render() {
        const visible = rows.filter(rowMatches);
        const pages = Math.max(1, Math.ceil(visible.length / pageLimit()));
        currentPage = Math.min(currentPage, pages);
        const start = (currentPage - 1) * pageLimit();
        const shown = new Set(visible.slice(start, start + pageLimit()));
        rows.forEach(row => { row.hidden = !shown.has(row); });
        if (total) { total.textContent = String(rows.length); } if (count) { count.textContent = String(visible.length); }
        if (pageCurrent) { pageCurrent.textContent = String(currentPage); } if (pageTotal) { pageTotal.textContent = String(pages); }
        if (prev) { prev.disabled = currentPage <= 1; } if (next) { next.disabled = currentPage >= pages; }
        renderPages(pages);
        const selected = rows.find(row => row.dataset.selected === 'true' && shown.has(row));
        setDetail(selected || visible[0] || { dataset: { rowTitle: '', rowDate: '-', rowSummary: '', rowReason: '', rowAction: '', rowEvidence: '', rowLevel: '', rowLevelClass: 'low', risk: '', rowRiskClass: 'notice' } });
      }
      function applyFilters() { currentPage = 1; render(); }
      function applySort() {
        const tbody = rows[0]?.parentElement;
        if (!tbody) {
          return;
        }
        rows = [...rows].sort((a, b) => {
          if ((sort?.value || 'score') === 'score') { return Number(b.dataset.score || 0) - Number(a.dataset.score || 0); }
          return Number(a.dataset.rank || 0) - Number(b.dataset.rank || 0);
        });
        rows.forEach(row => tbody.appendChild(row));
        render();
      }
      rows.forEach(row => row.addEventListener('click', () => setDetail(row)));
      [search, board, industry, level].forEach(el => el && el.addEventListener('input', applyFilters));
      sort && sort.addEventListener('input', applySort);
      pageSize && pageSize.addEventListener('input', applyFilters);
      prev && prev.addEventListener('click', () => { currentPage = Math.max(1, currentPage - 1); render(); });
      next && next.addEventListener('click', () => { currentPage += 1; render(); });
      reset && reset.addEventListener('click', () => {
        if (search) { search.value = ''; }
        if (board) { board.value = ''; }
        if (industry) { industry.value = ''; }
        if (level) { level.value = ''; }
        if (sort) { sort.value = 'score'; }
        applySort();
      });
      rows.forEach(row => { row.dataset.selected = 'false'; });
      applySort();
    });
  }
  document.querySelectorAll('[data-set-lang]').forEach(btn => {
    btn.addEventListener('click', () => setLang(btn.dataset.setLang));
  });
  setLang(initial);
  initCandidateMasterDetail();
})();
"""
if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli
    fail_not_cli(__file__)
