"""Static assets for the local A-share HTML report."""
from __future__ import annotations
CSS = """
:root{color-scheme:light;--bg:#f8fafc;--surface:#fff;--ink:#111d2f;--text:#243247;--muted:#637083;--line:#d8e0ea;--line-strong:#c5d0dd;--soft:#f7fafc;--green:#0a8f63;--green-dark:#047857;--blue:#1b75d0;--orange:#d97706;--red:#c73535;--shadow:0 8px 22px rgba(15,23,42,.07);--shadow-soft:0 12px 30px rgba(15,23,42,.09)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
	body{margin:0;max-width:100%;overflow-x:hidden;background:linear-gradient(180deg,#fbfdff 0,#f8fafc 340px,#f8fafc 100%);color:var(--text);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
		.page{width:min(2048px,calc(100% - 40px));margin:0 auto;padding:8px 0 20px}
h1,h2,h3,h4,p{margin:0}h2{font-size:21px;line-height:1.25;color:var(--ink)}h3{font-size:20px;line-height:1.25;color:var(--ink)}
.hero,.section,.panel-card{background:var(--surface);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}
	.executive-hero{background:transparent;border:0;border-radius:0;box-shadow:none;padding:0 10px 0;color:var(--ink)}
	.hero-title-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(520px,600px);gap:34px;align-items:start}
	.hero-copy h1{font-family:Georgia,"Times New Roman","Songti SC",serif;font-size:56px;line-height:.96;letter-spacing:0;color:#101b2d}
	.hero-badges{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
	.hero-badge{display:inline-flex;align-items:center;min-height:30px;border:1px solid var(--line);border-radius:6px;background:#fff;color:#26384f;font-weight:800;padding:5px 13px}
.hero-badge.ok{border-color:#8fcfb4;color:#047857;background:#f5fbf8}.hero-badge.blue{border-color:#aecbed;color:#1b65b8;background:#f5f9ff}.hero-badge.warn{border-color:#e7bf75;color:#a15c00;background:#fff9ee}.hero-badge.purple{border-color:#cbbbe8;color:#5f43a6;background:#faf7ff}.hero-badge.danger{border-color:#ecaaa5;color:#b42318;background:#fff7f6}
.hero-note{display:flex;align-items:center;gap:8px;margin-top:9px;color:#334155;font-size:14px}
.hero-note::before{content:"i";display:inline-grid;place-items:center;width:18px;height:18px;border:1px solid #64748b;border-radius:50%;font-size:12px;font-weight:900;color:#334155}
.hero-side{display:grid;gap:12px;align-content:start}
.hero-machine-note{margin:0;border:1px solid #d8e4f1;border-left:4px solid #1b75d0;border-radius:8px;background:#f8fbff;padding:11px 12px;color:#334155;font-size:13px;line-height:1.5;box-shadow:0 6px 16px rgba(15,23,42,.04)}
.hero-machine-note strong{color:#102033}
.field-coverage-card{display:grid;gap:12px;margin:10px 0 12px;border:1px solid #cfe1f3;border-radius:8px;background:linear-gradient(180deg,#fbfdff 0,#f7fbff 100%);padding:12px 14px;box-shadow:0 6px 16px rgba(15,23,42,.04)}
.field-coverage-head{display:grid;gap:4px}.field-coverage-head strong{color:var(--ink);font-size:15px;line-height:1.2}.field-coverage-head p{color:var(--muted);font-size:12px;line-height:1.45}
.field-coverage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}
.field-coverage-chip{display:grid;gap:3px;min-width:0;border:1px solid #d7e3ef;border-radius:8px;background:#fff;padding:10px 11px;box-shadow:0 2px 8px rgba(15,23,42,.03)}
.field-coverage-chip span{color:var(--muted);font-size:12px;font-weight:800}
.field-coverage-chip strong{color:var(--ink);font-size:15px;line-height:1.2}
.field-coverage-chip b{color:#0b8f63;font-size:12px;line-height:1.2}
.field-coverage-chip[data-field-missing="true"]{border-color:#e8c7a7;background:#fffaf2}
.field-coverage-chip[data-field-missing="true"] b{color:#a15c00}
.hero-fact-card{position:relative;width:100%;min-height:112px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:8px 18px;box-shadow:var(--shadow-soft)}
.hero-fact-card::after{display:none}
.hero-fact-card div{position:relative;display:grid;grid-template-columns:92px 1fr;gap:14px;padding:3px 0 3px 22px}
.hero-fact-card div::before{content:"";position:absolute;left:0;top:8px;width:13px;height:13px;border:1px solid #9aa8b7;border-radius:3px;background:linear-gradient(#9aa8b7,#9aa8b7) 3px 3px/7px 1px no-repeat,linear-gradient(#9aa8b7,#9aa8b7) 3px 7px/7px 1px no-repeat,#fff}
.hero-fact-card span{color:#526173;font-weight:800}.hero-fact-card strong{color:#1e293b;font-weight:800}
.section{margin-top:8px;padding:10px}.section>h2{display:flex;align-items:center;gap:10px;margin-bottom:14px}.section>h2::before{content:"";display:block;width:6px;height:22px;border-radius:5px;background:var(--green)}
.dashboard-section,.watchlist-section{padding:0;background:transparent;border:0;box-shadow:none}
	.report-overview-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(520px,1fr);gap:12px}
button.pipeline-card,button.flow-step{font:inherit;color:inherit;cursor:pointer}
.pipeline-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;align-items:stretch;border:1px solid var(--line);border-radius:8px;background:#fff;overflow:hidden}
		.pipeline-card{display:grid;grid-template-columns:54px minmax(0,1fr);gap:14px;align-items:center;min-height:74px;border:0;border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:8px 18px;background:#fff;text-align:left}
.pipeline-card:nth-child(2n){border-right:0}.pipeline-card:nth-last-child(-n+2){border-bottom:0}
.pipeline-card:hover,.pipeline-card:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f8fcff;box-shadow:inset 0 0 0 2px #9cc7ee}.pipeline-card:active{background:#f2f8ff}
	.pipeline-icon{position:relative;width:48px;height:48px;border-radius:50%;background:#13a266;box-shadow:inset 0 -8px 16px rgba(0,0,0,.08)}
.pipeline-icon::before,.pipeline-icon::after{content:"";position:absolute;left:50%;top:50%;background:#fff;transform:translate(-50%,-50%)}.pipeline-icon::before{width:50%;height:42%;clip-path:polygon(0 0,100% 0,64% 45%,64% 100%,36% 100%,36% 45%)}.pipeline-icon::after{display:none}
.pipeline-icon.circle::before{width:10px;height:10px;border-radius:50%;box-shadow:-11px 0 0 #fff,11px 0 0 #fff,0 15px 0 5px #fff;clip-path:none;transform:translate(-50%,-72%)}.pipeline-icon.eye::before{width:30px;height:20px;border:4px solid #fff;border-radius:50%;background:transparent;clip-path:none}.pipeline-icon.eye::after{display:block;width:6px;height:6px;border-radius:50%;background:#fff}.pipeline-icon.shield::before{width:46%;height:58%;background:#fff;clip-path:polygon(50% 0,88% 14%,80% 70%,50% 100%,20% 70%,12% 14%)}.pipeline-icon.shield::after{display:block;width:4px;height:10px;border-radius:2px;background:#f59e0b;box-shadow:0 14px 0 -1px #f59e0b;transform:translate(-50%,-61%)}
.pipeline-card.input .pipeline-icon{background:#1f7eea}.pipeline-card.passed .pipeline-icon{background:#12a36f}.pipeline-card.watch .pipeline-icon{background:#1e88e5}.pipeline-card.risk .pipeline-icon{background:#f59e0b}.pipeline-copy{display:grid;grid-template-columns:minmax(0,max-content) minmax(0,max-content) minmax(0,1fr);align-items:center;column-gap:10px;min-width:0}.pipeline-copy>span{display:block;color:#174034;font-size:16px;font-weight:900;line-height:1;white-space:nowrap}
.pipeline-card.passed .pipeline-copy>span{color:#174a82}.pipeline-card.watch .pipeline-copy>span{color:#7a4300}.pipeline-card.risk .pipeline-copy>span{color:#991b1b}.pipeline-card strong{display:block;color:#111827;font-size:30px;line-height:1;letter-spacing:0;font-variant-numeric:tabular-nums}.pipeline-card small{display:block;min-width:0;color:#475569;font-size:13px;line-height:1.1;white-space:normal;overflow-wrap:anywhere}
.selection-flow-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:9px 20px}
.selection-flow-card h2{display:flex;align-items:baseline;gap:8px;margin-bottom:7px}.selection-flow-card h2 span{color:#667085;font-size:15px;font-weight:600}
.selection-flow{display:grid;grid-template-columns:repeat(7,max-content);justify-content:center;align-items:center;gap:22px}
.flow-step{display:grid;justify-items:center;min-width:86px;border:0;border-radius:8px;background:transparent;color:#1e293b;text-align:center;padding:8px 10px}
.flow-step:hover,.flow-step:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f8fbff;box-shadow:0 0 0 2px #bfdbfe}.flow-step:active{background:#eef6ff}
	.flow-index{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;background:#1b75d0;color:#fff;font-size:19px;font-weight:900}
.flow-step.input .flow-index{background:#1b75d0}.flow-step.passed .flow-index{background:#0b8f63}.flow-step.watch .flow-index{background:#1b75d0}.flow-step.risk .flow-index{background:#f08a00}
.flow-step span:not(.flow-index){display:block;margin-top:7px;color:#0f172a;font-weight:900}
.flow-step strong{display:block;margin-top:2px;color:#334155;font-weight:700}
.flow-step small{display:block;margin-top:1px;color:#64748b;font-size:12px}
.flow-arrow{width:88px;height:2px;background:#64748b;position:relative}
.flow-arrow::after{content:"";position:absolute;right:-1px;top:-5px;width:11px;height:11px;border-top:2px solid #64748b;border-right:2px solid #64748b;transform:rotate(45deg)}
.insight-drawer[hidden]{display:none}.insight-drawer{position:fixed;inset:0;z-index:80;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.45);contain:layout paint}
.insight-dialog{position:relative;width:min(580px,100%);max-height:min(720px,calc(100vh - 48px));overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff;padding:20px 22px 18px;box-shadow:0 18px 48px rgba(15,23,42,.22);contain:content}
.insight-close{position:absolute;right:14px;top:14px;min-height:34px;border:1px solid var(--line);border-radius:6px;background:#fff;color:#1e293b;font:inherit;font-weight:800;padding:5px 12px;cursor:pointer}.insight-close:hover,.insight-close:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;border-color:#9cc7ee;background:#f7fbff}
.insight-eyebrow{display:inline-flex;align-items:center;min-height:26px;border:1px solid #bfdbfe;border-radius:6px;background:#f8fbff;color:#175cd3;font-size:12px;font-weight:900;padding:3px 9px}
.insight-dialog h3{margin-top:14px;padding-right:74px}.insight-summary{margin-top:8px;color:#475569;line-height:1.55}.insight-facts{display:grid;grid-template-columns:minmax(140px,190px) minmax(0,1fr);gap:8px 14px;margin:16px 0 0;padding-top:14px;border-top:1px solid var(--line)}
.insight-facts dt{color:#526173;font-size:12px;font-weight:900}.insight-facts dd{margin:0;min-width:0;color:#172033;font-weight:800;overflow-wrap:anywhere}
.insight-actions{display:grid;gap:7px;margin:16px 0 0;padding:13px 16px 13px 30px;border:1px solid #b9d7ce;border-radius:8px;background:#f5fbf8;color:#205044}
.metrics,.note-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.metric,.note-card{border:1px solid var(--line);border-radius:8px;padding:16px;background:#fff}
.metric>span,.facts dt,.note-card .note-label{color:var(--muted);font-size:12px;font-weight:800}
.metric strong{display:block;margin-top:7px;color:var(--ink);font-size:28px;line-height:1}
.note-card strong{display:block;margin-top:7px;color:var(--ink);font-size:17px}
.limit-panel{margin-top:14px;border:1px solid #b9d7ce;border-left:5px solid var(--green);border-radius:8px;padding:16px 18px;background:#f5fbf8}
.limit-panel strong{display:block;margin-bottom:4px}.limit-panel p{color:var(--muted)}
	.disclosure-alerts{margin:8px 0 0;padding:0;list-style:none;display:grid;gap:6px}
	.disclosure-alerts li{border:1px solid #f0cf9d;border-left:5px solid var(--orange);border-radius:8px;background:#fff8ed;padding:8px 12px;color:#6c3d00;font-size:14px}
.boundary{margin-top:14px;color:var(--muted);overflow-wrap:anywhere}
.technical-details,.report-details{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.technical-details summary,.report-details summary{cursor:pointer;color:var(--muted);font-weight:700}
.technical-details summary{display:inline-flex;align-items:center;gap:8px;width:max-content;max-width:100%;min-height:34px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--green-dark);padding:8px 12px}
.technical-details summary::marker{content:""}.technical-details summary::-webkit-details-marker{display:none}
.report-details summary{width:max-content;max-width:100%;border:1px solid var(--line);border-radius:8px;background:#fff;padding:9px 12px;color:var(--green-dark)}
.technical-details[open] summary,.report-details[open] summary{margin-bottom:12px}
.technical-details summary::after{content:">";margin-left:2px;color:#0b8f63;font-size:12px;line-height:1;transition:transform .18s ease}
.technical-details[open] summary::after{transform:rotate(90deg)}
.technical-details summary span{display:block;font-size:12px;font-weight:400;color:#64748b}
.report-note,.diagnostic-intro{color:var(--muted);margin-bottom:12px}
.facts{display:grid;grid-template-columns:minmax(170px,230px) 1fr;gap:10px 18px;margin:14px 0}
.facts dt{overflow-wrap:anywhere}.facts dd{margin:0;min-width:0;overflow-wrap:anywhere}
.empty{color:var(--muted)}
.watchlist-dashboard{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(320px,.88fr);gap:12px;align-items:stretch}
.watchlist-preview-pane{min-width:0;border:1px solid var(--line);border-radius:8px;background:#fff;padding:11px}
.candidate-cards[data-preview-table]{display:block;min-width:0;max-width:100%;overflow-x:auto}
.candidate-cards[data-preview-table] table{min-width:500px;table-layout:fixed;white-space:normal}
.preview-mobile-cards{display:none}
.candidate-cards[data-preview-table] th,.candidate-cards[data-preview-table] td{padding:7px 9px;line-height:1.35}
.candidate-cards[data-preview-table] th:nth-child(1),.candidate-cards[data-preview-table] td:nth-child(1){width:148px}
.candidate-cards[data-preview-table] th:nth-child(2),.candidate-cards[data-preview-table] td:nth-child(2){width:72px}
.candidate-cards[data-preview-table] th:nth-last-child(2),.candidate-cards[data-preview-table] td:nth-last-child(2){width:88px}
.candidate-cards[data-preview-table] tr[data-preview-symbol]{cursor:pointer}
.candidate-cards[data-preview-table] tr[data-preview-symbol]:hover{background:#f8fcfa}
.candidate-cards[data-preview-table] tr[data-preview-symbol]:focus-visible{outline:2px solid #6daff0;outline-offset:-2px;background:#f8fcfa}
.preview-heading{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:7px}
.preview-heading h3{font-size:20px}.preview-heading p{margin-top:4px;color:var(--muted);font-size:13px}
		.candidate-open-slot{display:grid;align-items:stretch;justify-items:stretch;min-width:0;min-height:100%}
			.candidate-open-banner{display:grid;gap:9px;align-content:center;justify-items:center;width:100%;min-height:100%;border:1px solid #42b18d;border-radius:8px;background:linear-gradient(180deg,#fbfffd 0,#f2fbf6 100%);padding:16px 20px 14px;color:#1e293b;text-align:center;text-decoration:none;box-shadow:inset 0 0 0 1px rgba(26,153,112,.04)}
.candidate-open-banner:hover,.candidate-open-banner:focus-visible{outline:2px solid #0a8f63;outline-offset:2px;border-color:var(--green);background:linear-gradient(180deg,#f4fbf7 0,#e9f8f1 100%);box-shadow:inset 0 0 0 2px rgba(10,143,99,.16)}
	.candidate-open-title{position:relative;display:inline-flex;align-items:center;gap:8px;color:var(--green-dark);font-size:18px;line-height:1.2;font-weight:900}.candidate-open-title::before{content:"";width:18px;height:20px;border:2px solid var(--green);border-radius:3px;background:linear-gradient(var(--green),var(--green)) 5px 5px/7px 2px no-repeat,linear-gradient(var(--green),var(--green)) 5px 10px/7px 2px no-repeat,linear-gradient(var(--green),var(--green)) 5px 15px/7px 2px no-repeat}
	.candidate-open-body{max-width:min(380px,100%);color:#475569;font-size:13px;line-height:1.45}.candidate-open-button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:1px solid var(--line);border-radius:7px;background:#fff;color:#1e293b;font-weight:800;padding:7px 18px;box-shadow:0 4px 10px rgba(15,23,42,.04)}
	.candidate-open-foot{position:relative;color:#334155;font-size:12px;font-weight:700;text-align:center;width:100%;padding-bottom:14px}.candidate-open-foot::after{content:"";position:absolute;left:50%;bottom:0;width:9px;height:9px;border-right:2px solid var(--green-dark);border-bottom:2px solid var(--green-dark);transform:translateX(-50%) rotate(45deg)}
		.candidate-master-detail{margin-top:8px;max-width:100%;overflow:hidden;border:1px solid var(--line);border-radius:8px;background:#fff;padding:10px;box-shadow:0 8px 20px rgba(15,23,42,.04);scroll-margin-top:18px}
		.master-detail-header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:10px}
	.master-detail-header h3{font-size:20px}.master-detail-header p{margin-top:4px;max-width:760px;color:var(--muted);font-size:13px;line-height:1.35}
.candidate-file-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.file-chip{display:inline-block;border:1px solid #a6d8c5;border-radius:7px;background:#f4fbf8;padding:6px 11px;color:var(--green-dark)}
.candidate-download-link{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:1px solid #047857;border-radius:7px;background:#047857;color:#fff;font-weight:900;padding:7px 14px;text-decoration:none;box-shadow:0 4px 12px rgba(10,143,99,.15)}
.candidate-download-link:hover,.candidate-download-link:focus-visible{outline:2px solid #0a8f63;outline-offset:2px;background:#065f46;border-color:#065f46;box-shadow:0 0 0 3px rgba(10,143,99,.16)}
.field-notice{margin:-2px 0 9px;border:1px solid #f0cf9d;border-left:5px solid var(--orange);border-radius:8px;background:#fffaf0;padding:8px 12px;color:#6c3d00;font-size:13px;line-height:1.4}
.candidate-toolbar{display:grid;grid-template-columns:2fr repeat(3,minmax(130px,1fr)) max-content;gap:9px;margin-bottom:7px;align-items:end}
.candidate-toolbar.has-industry{grid-template-columns:2fr repeat(4,minmax(130px,1fr)) max-content}
.candidate-toolbar label{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;font-weight:800}
.candidate-toolbar label span{white-space:nowrap}
.candidate-toolbar label input,.candidate-toolbar label select{flex:1;min-width:0}
.candidate-toolbar input,.candidate-toolbar select{width:100%;height:40px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font:inherit;padding:7px 10px}
.candidate-toolbar button{height:40px;min-width:82px;border:1px solid var(--line);border-radius:7px;background:#fff;color:#64748b;font:inherit;padding:7px 14px;cursor:pointer;box-shadow:0 2px 7px rgba(15,23,42,.04)}
.candidate-toolbar input:focus-visible,.candidate-toolbar select:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;border-color:#9cc7ee;background:#f7fbff}
.candidate-toolbar button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;border-color:#9cc7ee;background:#f7fbff}
.candidate-toolbar-status{min-height:20px;margin:-2px 0 7px;color:#0f766e;font-size:12px;font-weight:750;line-height:1.35}
		.master-detail-grid{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(420px,.88fr);gap:12px;align-items:start}
.master-list-panel{min-width:0;max-width:100%;overflow:clip}
.candidate-detail-panel{position:sticky;top:12px}
.detail-head-copy{display:grid;gap:4px;min-width:0}
.detail-head-note{color:#64748b;font-size:12px;font-weight:700;line-height:1.35}
			.master-table{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff;contain:content}
.master-table table{min-width:100%;white-space:normal;table-layout:fixed}.master-table td,.master-table th{overflow-wrap:anywhere}
.master-table:not(.has-wide-table) th:nth-child(1),.master-table:not(.has-wide-table) td:nth-child(1){width:62px}
.master-table:not(.has-wide-table) th:nth-child(2),.master-table:not(.has-wide-table) td:nth-child(2){width:112px}
.master-table.has-wide-table table{min-width:980px;table-layout:auto}
	.master-table th{position:sticky;top:0;z-index:1;background:#f8fafc;color:#27384f}
.master-table tr[data-candidate-row]{cursor:pointer}
.master-table tr[data-candidate-row]:hover{background:#f8fcfa}
.master-table tr[data-candidate-row]:focus-visible{outline:2px solid #6daff0;outline-offset:-2px;background:#f8fcfa}
.master-table tbody tr[hidden]{display:none}
.master-table tr[data-selected="true"]{background:#eaf4ff;box-shadow:inset 0 0 0 2px #6daff0}
.candidate-empty-row td{height:112px;text-align:center;color:#64748b;background:linear-gradient(180deg,#fff,#fbfdff);white-space:normal}
.candidate-empty-state{display:grid;place-items:center;gap:4px;min-height:96px}
.candidate-empty-state strong{color:#334155;font-size:14px}
.candidate-empty-state span{font-size:12px}
.rank-cell{display:flex;align-items:center;gap:7px;min-width:0}.rank-number{display:inline-flex;align-items:center;gap:5px;min-width:0}
.sparse-note{display:grid;place-items:center;min-height:104px;border-top:1px dashed var(--line);color:#64748b;font-size:13px;background:linear-gradient(180deg,#fff,#fbfdff)}
.row-check{display:inline-grid;place-items:center;width:16px;height:16px;border:1px solid var(--line);border-radius:4px;background:#fff}
tr[data-selected="true"] .row-check{background:#1683df;border-color:#1683df}
tr[data-selected="true"] .row-check::after{content:"";width:6px;height:9px;border-right:2px solid #fff;border-bottom:2px solid #fff;transform:rotate(40deg)}
.symbol-cell{color:#475569;font-weight:650;letter-spacing:.01em}.name-cell{color:#172033;font-weight:760}.name-cell.missing,.stock-anchor.missing{color:#64748b}
.stock-anchor{display:block;color:#0f3a65;font-size:15px;line-height:1.25}.stock-code{display:block;margin-top:3px;color:#334155;font-size:13px;font-weight:800;letter-spacing:.02em}
.level-badge,.risk-badge{display:inline-flex;align-items:center;width:max-content;max-width:100%;border-radius:6px;padding:4px 10px;font-size:12px;font-weight:850;border:0}
.level-badge{background:#e7f1ff;color:#175cd3}
.level-badge.high{background:#fff1df;color:#b54708}
.level-badge.medium{background:#e7f1ff;color:#175cd3}
.level-badge.low{background:#eef2f7;color:#475569}
.risk-badge.notice{background:#ecfdf3;color:#067647;border:1px solid #abefc6}
.risk-badge.attention{background:#fffaeb;color:#b54708;border:1px solid #fedf89}
.risk-badge.high{background:#fef3f2;color:#b42318;border:1px solid #fecdca}
		.candidate-detail-panel{align-self:stretch;height:100%;max-height:560px;border:1px solid var(--line);border-radius:8px;background:#fff;min-width:0;overflow:auto;box-shadow:0 8px 18px rgba(15,23,42,.04);contain:content;scrollbar-gutter:stable}
.stock-detail-drawer[hidden]{display:none}.stock-detail-drawer{position:fixed;inset:0;z-index:90;display:grid;place-items:center;padding:20px;background:rgba(15,23,42,.58);backdrop-filter:blur(8px);contain:layout paint}
.stock-dialog{width:min(1120px,100%);max-height:min(92vh,920px);overflow:auto;border:1px solid var(--line);border-radius:10px;background:linear-gradient(180deg,#fff 0,#fbfdff 100%);box-shadow:0 28px 72px rgba(15,23,42,.28);contain:content;scrollbar-gutter:stable}
		.stock-dialog-head{position:sticky;top:0;z-index:3;display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:18px 20px 14px;border-bottom:1px solid #e3eaf2;background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(250,252,255,.96))}.stock-dialog-head > div{min-width:0;max-width:100%}
	.stock-dialog-head h3{margin-top:4px;font-size:22px;line-height:1.15;overflow-wrap:anywhere}.stock-dialog-head p{display:flex;flex-wrap:wrap;gap:12px;margin-top:6px;color:var(--muted);font-size:13px;overflow-wrap:anywhere}
	.stock-dialog-eyebrow{display:inline-flex;align-items:center;min-height:26px;border:1px solid #b9d7ce;border-radius:6px;background:#f5fbf8;color:#0b8f63;font-size:12px;font-weight:900;padding:3px 9px}
		.stock-dialog-close{min-height:44px;border:1px solid var(--line);border-radius:7px;background:#fff;color:#1e293b;font:inherit;font-weight:800;padding:7px 16px;cursor:pointer}
	.stock-dialog-close:hover,.stock-dialog-close:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;border-color:#9cc7ee;background:#f7fbff}
		.stock-dialog-grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(360px,.95fr);gap:14px;padding:14px;align-items:start}
	.stock-chart-panel,.stock-facts-panel{border:1px solid var(--line);border-radius:9px;background:#fff;min-width:0;box-shadow:0 8px 18px rgba(15,23,42,.04)}
	.stock-chart-panel{display:grid;gap:10px;padding:14px;background:linear-gradient(180deg,#fff 0,#f9fbfd 100%);min-height:0}
	.stock-chart-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;color:#1e293b}.stock-chart-head strong{display:block;font-size:16px}.stock-chart-head span{display:block;color:var(--muted);font-size:12px;margin-top:3px}
	.stock-chart-head [data-stock-field="candle-count"]{display:inline-flex;align-items:center;min-height:28px;border:1px solid #b9d7ce;border-radius:6px;background:#f5fbf8;color:#0b8f63;font-weight:800;padding:2px 10px}
.stock-chart-wrap{position:relative;min-height:380px;aspect-ratio:16/11;border:1px solid var(--line);border-radius:9px;background:#fff;overflow:hidden;contain:content;max-width:100%;width:100%}
.stock-chart-wrap canvas{display:block;width:100%;height:100%;touch-action:none}
	.stock-chart-empty{position:absolute;inset:0;display:grid;place-items:center;padding:18px;color:var(--muted);text-align:center;white-space:pre-line}
		.stock-chart-tooltip{position:absolute;z-index:2;display:grid;gap:3px;width:210px;max-width:calc(100% - 20px);border:1px solid #b9d7ce;border-radius:8px;background:rgba(255,255,255,.98);box-shadow:0 12px 28px rgba(15,23,42,.16);padding:8px 10px;color:#1e293b;font-size:12px;line-height:1.35;pointer-events:none;transform:none}
	.stock-chart-tooltip strong{font-size:13px;line-height:1.25;color:#0f172a}
	.stock-chart-tooltip span{display:block;color:#475569}
	.stock-chart-note{color:#64748b;font-size:12px;line-height:1.45}
	.stock-facts-panel{display:grid;align-content:start;gap:12px;padding:14px;background:#f8fafc;min-width:0;max-width:100%;width:100%}
	.stock-panel-section{display:grid;gap:10px;min-width:0;border:1px solid var(--line);border-radius:9px;background:#fff;padding:12px;box-shadow:0 4px 12px rgba(15,23,42,.03)}
	.stock-panel-title{display:flex;align-items:center;gap:8px;color:#1e293b;font-size:13px;line-height:1.25;font-weight:900}
	.stock-panel-title::before{content:"";width:4px;height:16px;border-radius:3px;background:#1b75d0}
	.stock-action-section{border-color:#bfdbfe;background:#f8fbff}
	.stock-action-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
	.stock-action-grid button{min-height:40px;border:1px solid #c9d7e7;border-radius:7px;background:#fff;color:#1e293b;font:inherit;font-size:13px;font-weight:850;padding:8px 10px;cursor:pointer}
	.stock-action-grid button:hover,.stock-action-grid button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;border-color:#82b6e8;background:#eef7ff}
	.stock-action-status{min-height:18px;color:#0b8f63;font-size:12px;font-weight:800}
	.stock-next-section{border-color:#dbe8f7;background:#fff}
	.stock-next-list{display:grid;gap:6px;margin:0;padding-left:20px;color:#334155;font-size:13px;line-height:1.45}
	.stock-fact-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
	.stock-fact-grid.secondary{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
	.stock-fact-grid div,.stock-text-section{border:1px solid #e7edf4;border-radius:8px;background:#fff;padding:11px 12px}
	.stock-fact-grid.secondary div{background:#fbfdff}
	.stock-fact-grid span,.stock-text-section span{display:block;color:var(--muted);font-size:12px;font-weight:800}
	.stock-fact-grid strong{display:block;margin-top:6px;color:var(--ink);font-size:16px;line-height:1.2;word-break:break-all}
	.stock-fact-grid.primary strong{font-size:17px}
	.stock-fact-grid.secondary strong{font-size:14px;color:#334155}
	.stock-tech-summary{border:1px solid #bfdbfe;border-radius:8px;background:#f8fbff;padding:10px 12px;color:#1e293b;font-size:13px;line-height:1.45;font-weight:750}
.stock-technical-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
	.stock-tech-card{display:grid;gap:5px;min-width:0;border:1px solid #e7edf4;border-left:4px solid #d6e0eb;border-radius:8px;background:#fff;padding:10px 11px}
	.stock-tech-card span{color:var(--muted);font-size:12px;font-weight:850}
	.stock-tech-card strong{color:#172033;font-size:15px;line-height:1.25;overflow-wrap:anywhere}
	.stock-tech-card[data-status="positive"]{border-left-color:#047857;background:#f3fbf7}
	.stock-tech-card[data-status="positive"] strong{color:#064e3b}
	.stock-tech-card[data-status="positive"] span{color:#0f766e}
	.stock-tech-card[data-status="attention"]{border-left-color:#d97706;background:#fffaf0}
	.stock-tech-card[data-status="attention"] strong{color:#854d0e}
	.stock-tech-card[data-status="attention"] span{color:#a16207}
	.stock-tech-card[data-status="negative"]{border-left-color:#c73535;background:#fff7f6}
	.stock-tech-card[data-status="negative"] strong{color:#991b1b}
	.stock-tech-card[data-status="negative"] span{color:#b91c1c}
	.stock-tech-note{color:#64748b;font-size:12px;line-height:1.45}
	.stock-text-section p{margin-top:6px;color:var(--text);line-height:1.5;white-space:pre-line;word-break:break-word;overflow-wrap:anywhere}
	.stock-text-section.summary,.stock-text-section.reason{border-color:#dbe8f7}
	.stock-text-section.risk{border-color:#fecdca;background:#fff7f6}
	.stock-text-section.action{border-color:#bfdbfe;background:#f8fbff}
	.stock-text-section.evidence{background:#fbfdff}
	.stock-text-section.evidence p{font-variant-numeric:tabular-nums}
			.detail-head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding:11px 14px 9px}
		.detail-head h3{font-size:21px}.detail-head span{color:var(--muted);font-weight:700}.detail-head b{color:#334155}
.detail-action-button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:1px solid #c9d7e7;border-radius:7px;background:#fff;color:#1e293b;font:inherit;font-size:13px;font-weight:850;padding:8px 12px;cursor:pointer;box-shadow:0 2px 8px rgba(15,23,42,.04)}
.detail-action-button:hover,.detail-action-button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;border-color:#82b6e8;background:#eef7ff}
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
.candidate-pager button,.candidate-pager select{min-height:40px;border:1px solid #d6e0eb;border-radius:7px;background:#fff;color:#1e293b;font:inherit;padding:7px 12px;box-shadow:0 2px 8px rgba(15,23,42,.04)}
.candidate-pager button{cursor:pointer}.candidate-pager button:not(:disabled):hover,.candidate-pager button:not(:disabled):focus-visible{outline:2px solid #1b75d0;outline-offset:2px;border-color:#9cc7ee;background:#f7fbff}.candidate-pager button:disabled{opacity:.48;cursor:not-allowed;box-shadow:none}
.candidate-page-numbers{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}.candidate-page-number{min-width:44px;min-height:44px;border:1px solid #d6e0eb;border-radius:7px;background:#fff;color:#1e293b;font:inherit;box-shadow:0 2px 8px rgba(15,23,42,.04);cursor:pointer}.candidate-page-number.active{border-color:#1b75d0;background:#1b75d0;color:#fff}.candidate-page-ellipsis{color:#64748b;padding:0 2px}.candidate-page-status{color:#334155}
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
.table-wrap{max-width:100%;overflow-x:auto}
table{width:100%;border-collapse:collapse;white-space:nowrap}
th,td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{color:#334155;font-size:12px;background:#f8fafc}
td{max-width:340px;overflow:hidden;text-overflow:ellipsis}
td.text-cell{min-width:220px;max-width:460px;white-space:normal;overflow:visible;text-overflow:clip}
.evidence{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.evidence li{display:grid;grid-template-columns:minmax(130px,180px) 1fr;gap:12px}
.evidence span{color:var(--muted);font-weight:700}
code{white-space:normal;overflow-wrap:anywhere}
@media(max-width:1500px){.report-overview-grid{grid-template-columns:minmax(0,1fr) minmax(420px,.9fr)}.selection-flow{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.flow-arrow{display:none}.master-detail-grid{grid-template-columns:minmax(0,1fr) minmax(420px,.82fr)}.candidate-detail-panel .detail-body{grid-template-columns:1fr}.candidate-detail-panel .detail-main{border-right:0;border-bottom:1px solid var(--line)}.candidate-detail-panel .detail-evidence-card{border-left:0;border-top:1px solid #e7edf4}}
@media(max-width:1280px){.hero-title-row,.report-overview-grid,.watchlist-dashboard,.final-notice-grid{grid-template-columns:1fr}.selection-flow{grid-template-columns:repeat(4,1fr);gap:12px}.flow-arrow{display:none}.candidate-open-banner{min-height:150px}.master-detail-grid{grid-template-columns:minmax(0,1fr) minmax(360px,.8fr)}.candidate-detail-panel{max-height:520px;position:relative;top:auto}.hero-fact-card{max-width:none}.hero-machine-note{font-size:12px}.master-table{max-height:52vh}}
@media(max-width:1100px){.candidate-toolbar{grid-template-columns:repeat(2,minmax(0,1fr))}.candidate-toolbar label:first-child{grid-column:1/-1}.candidate-toolbar button{align-self:end}.master-detail-grid{grid-template-columns:1fr}.candidate-detail-panel{max-height:none}.detail-body{grid-template-columns:1fr}.detail-main{border-right:0;border-bottom:1px solid var(--line)}.detail-evidence-card{border-left:0;border-top:1px solid #e7edf4}.master-table-footer{display:grid;grid-template-columns:1fr;align-items:start}.candidate-pager{margin-top:8px}.field-coverage-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:900px){.page{width:min(100% - 20px,1200px);padding-top:10px}.executive-hero{padding:0}.hero-title-row{gap:12px}.hero-copy h1{font-size:34px;line-height:1}.hero-badges{gap:8px}.hero-badge{min-height:34px;padding:5px 11px}.hero-note{margin-top:7px}.hero-fact-card{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;min-height:0;padding:8px 14px}.hero-fact-card div{grid-template-columns:78px minmax(0,1fr);gap:8px;padding:4px 8px 4px 20px}.hero-fact-card::after{display:none}.hero-side{gap:10px}.pipeline-card{grid-template-columns:44px minmax(0,1fr);justify-content:normal;gap:12px;min-height:66px;padding:9px 14px}.pipeline-icon{width:40px;height:40px}.pipeline-icon.circle::before{width:8px;height:8px;box-shadow:-9px 0 0 #fff,9px 0 0 #fff,0 12px 0 4px #fff}.pipeline-icon.eye::before{width:25px;height:17px;border-width:3px}.pipeline-icon.shield::after{height:8px;box-shadow:0 11px 0 -1px #f59e0b}.selection-flow-card{padding:9px 14px}.selection-flow{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.flow-step{min-width:0}.flow-index{width:32px;height:32px;font-size:17px}.flow-step span:not(.flow-index){margin-top:5px}.flow-step strong{font-size:13px}.flow-step small{font-size:11px}.candidate-toolbar{grid-template-columns:1fr}.master-detail-header,.detail-table-heading,.preview-heading,.master-table-footer{display:block}.facts,.evidence li,.detail-grid{grid-template-columns:1fr}.detail-grid>span{border-right:0;border-bottom:1px solid var(--line)}.field-coverage-grid{grid-template-columns:1fr}.section{padding:14px}}
@media(max-width:640px){body{font-size:14px;line-height:1.5}.page{width:min(100% - 16px,1200px);padding:8px 0 16px}.hero-copy h1{font-size:32px;line-height:1.02}.hero-badges{gap:8px}.hero-badge{flex:1 1 calc(50% - 8px);justify-content:center;min-height:36px}.hero-note{align-items:flex-start}.hero-fact-card{padding:8px 10px}.hero-fact-card div{grid-template-columns:1fr;gap:2px;padding:5px 8px 5px 18px}.hero-machine-note{padding:9px 10px;font-size:12px}.pipeline-card{min-height:72px;padding:9px 10px}.pipeline-copy{grid-template-columns:max-content max-content;grid-template-areas:"label value" "note note";align-items:center;column-gap:6px;row-gap:3px}.pipeline-copy>span{grid-area:label;font-size:15px}.pipeline-copy>strong{grid-area:value}.pipeline-card strong{font-size:25px}.pipeline-card small{grid-area:note;font-size:12px;line-height:1.2}.insight-drawer{place-items:end center;padding:12px}.insight-dialog{width:100%;max-height:calc(100vh - 24px);padding:18px 16px}.insight-close{min-width:44px;min-height:44px}.insight-dialog h3{padding-right:70px}.insight-facts{grid-template-columns:1fr;gap:3px}.candidate-file-actions{display:grid;grid-template-columns:1fr;justify-content:stretch;width:100%}.candidate-download-link{min-height:44px}.candidate-toolbar label{display:grid;gap:5px}.candidate-toolbar label span{white-space:normal}.candidate-toolbar input,.candidate-toolbar select,.candidate-toolbar button,.candidate-pager button,.candidate-pager select{min-height:44px}.candidate-cards[data-preview-table] th,.candidate-cards[data-preview-table] td{padding:8px}.candidate-master-detail{padding:8px}.master-table{max-height:58vh}.master-table table{min-width:860px}.candidate-detail-panel{box-shadow:none;position:relative;top:auto}.detail-head{gap:8px}.detail-head h3{font-size:19px}.detail-grid p,.detail-grid>span{padding:10px}.candidate-pager{display:grid;grid-template-columns:1fr 1fr;align-items:stretch}.candidate-pager [data-candidate-prev]{grid-column:1;grid-row:1}.candidate-pager [data-candidate-next]{grid-column:2;grid-row:1}.candidate-page-numbers{grid-column:1/-1;grid-row:2;justify-content:center}.candidate-page-status{grid-column:1;grid-row:3;align-self:center}.candidate-pager label{grid-column:2;grid-row:3;display:flex;align-items:center;justify-content:flex-end;gap:6px}.candidate-pager label select{min-width:0}.file-chip{display:block;width:100%;padding:8px 10px}.field-coverage-card{padding:10px 12px}.result-notice-card,.disclaimer-card{padding:14px 16px}.section{padding:12px}}
@media(hover:none){.candidate-open-button,.candidate-download-link,.candidate-toolbar input,.candidate-toolbar select,.candidate-toolbar button,.candidate-pager button,.candidate-pager select,.stock-dialog-close,.stock-action-grid button,.detail-action-button{min-height:44px}}
@media(max-width:640px){.candidate-cards[data-preview-table] .table-wrap{display:none}.preview-mobile-cards{display:grid;gap:10px}.preview-mobile-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:11px 12px;box-shadow:0 4px 12px rgba(15,23,42,.03);cursor:pointer}.preview-mobile-card:hover,.preview-mobile-card:focus-visible{outline:2px solid #6daff0;outline-offset:2px;background:#f8fcfa}.preview-mobile-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.preview-mobile-head .stock-anchor{font-size:16px;line-height:1.25}.preview-mobile-head .stock-code{margin-top:2px}.preview-mobile-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}.preview-mobile-meta-item{display:grid;gap:2px;min-width:0;border:1px solid #e7edf4;border-radius:8px;background:#fbfdff;padding:8px 9px;color:#334155;font-size:13px;line-height:1.35;overflow-wrap:anywhere}.preview-mobile-meta-item b{color:var(--muted);font-size:12px;font-weight:850}.preview-mobile-summary{margin-top:10px;color:var(--text);font-size:13px;line-height:1.5;overflow-wrap:anywhere}}
@media(max-width:520px){.hero-fact-card,.pipeline-metrics{grid-template-columns:1fr}.selection-flow{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.pipeline-card{border-right:0}.pipeline-card:nth-last-child(2){border-bottom:1px solid var(--line)}.flow-step small{display:none}}
@media(max-width:900px){.stock-detail-drawer{place-items:end center;padding:12px;padding-bottom:calc(12px + env(safe-area-inset-bottom))}.stock-dialog{width:100%;max-height:calc(100vh - 24px);padding-bottom:env(safe-area-inset-bottom)}.stock-dialog-grid{grid-template-columns:1fr}.stock-dialog-head{position:relative}.stock-chart-wrap{min-height:320px;aspect-ratio:auto}}
	@media(max-width:640px){.stock-dialog-head{position:relative;display:grid;grid-template-columns:minmax(0,1fr) max-content;align-items:start;gap:12px;padding:14px 16px 12px}.stock-dialog-head h3{font-size:24px;line-height:1.12}.stock-dialog-head p{gap:8px}.stock-dialog-close{min-width:44px;min-height:44px;margin-top:0;padding:5px 12px}.stock-action-grid{grid-template-columns:1fr}.stock-action-grid button{min-height:44px}.stock-fact-grid,.stock-fact-grid.secondary{grid-template-columns:1fr}.stock-technical-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.stock-chart-wrap{min-height:280px}}
"""
JS = """
(() => {
  document.querySelectorAll('details.technical-details').forEach(el => { el.open = false; });
  const storageKey = 'aShareSelectionReportLang';
  const root = document.documentElement;
  const mode = root.dataset.langMode || 'auto';
  const generated = root.dataset.lang || 'en';
  let saved = '';
  function readStorage(key) {
    try {
      return window.localStorage ? window.localStorage.getItem(key) : '';
    } catch (error) {
      return '';
    }
  }
  function writeStorage(key, value) {
    try {
      if (window.localStorage) {
        window.localStorage.setItem(key, value);
      }
    } catch (error) {
      return;
    }
  }
  saved = readStorage(storageKey);
  const initial = mode === 'auto' ? (saved || generated) : mode;
  function setLang(lang, options = {}) {
    const previous = root.dataset.lang || generated;
    const shouldRewriteText = options.forceText || previous !== lang;
    root.dataset.lang = lang;
    root.lang = lang === 'zh' ? 'zh-CN' : 'en';
    if (shouldRewriteText) {
      document.querySelectorAll('[data-i18n-en]').forEach(el => {
        el.textContent = el.dataset[lang === 'zh' ? 'i18nZh' : 'i18nEn'];
      });
      ['aria-label', 'title', 'placeholder'].forEach(attribute => {
        document.querySelectorAll(`[data-i18n-${attribute}-en]`).forEach(el => {
          if (attribute === 'title' && el.tagName === 'TITLE') {
            return;
          }
          const value = el.getAttribute(`data-i18n-${attribute}-${lang}`);
          if (value !== null) {
            el.setAttribute(attribute, value);
          }
        });
      });
    }
    const title = document.querySelector('title[data-i18n-title-en]');
    if (title) {
      title.textContent = title.dataset[lang === 'zh' ? 'i18nTitleZh' : 'i18nTitleEn'];
    }
    document.querySelectorAll('[data-set-lang]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.setLang === lang);
    });
    writeStorage(storageKey, lang);
    if (!options.silent) {
      document.dispatchEvent(new CustomEvent('report-language-change'));
    }
  }
  function runAfterFirstPaint(callback) {
    const scheduleIdle = () => {
      if ('requestIdleCallback' in window) {
        window.requestIdleCallback(callback, { timeout: 350 });
      } else {
        window.setTimeout(callback, 0);
      }
    };
    window.requestAnimationFrame(() => window.requestAnimationFrame(scheduleIdle));
  }
  let bodyLockCount = 0;
  function setBodyLocked(locked) {
    bodyLockCount = Math.max(0, bodyLockCount + (locked ? 1 : -1));
    const active = bodyLockCount > 0;
    document.body.style.overflow = active ? 'hidden' : '';
    document.body.style.paddingRight = active ? `${Math.max(0, window.innerWidth - document.documentElement.clientWidth)}px` : '';
  }
  function setModalContentHidden(hidden, activeModal) {
    document.querySelectorAll('[data-report-content]').forEach(el => {
      el.setAttribute('aria-hidden', hidden ? 'true' : 'false');
    });
    document.querySelectorAll('[data-report-modal-root]').forEach(el => {
      if (el !== activeModal) {
        el.setAttribute('aria-hidden', hidden ? 'true' : 'false');
      }
    });
  }

function initCandidateMasterDetail() {
  document.querySelectorAll('[data-candidate-master-detail]').forEach(rootEl => {
    const tbody = rootEl.querySelector('.master-table tbody');
    let rows = Array.from(rootEl.querySelectorAll('[data-candidate-row]'));
    let mountedRows = [];
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
    const detailOpenStock = detail ? detail.querySelector('[data-detail-open-stock]') : null;
    const toolbarStatus = rootEl.querySelector('[data-candidate-toolbar-status]');
    const reportContent = rootEl.closest('[data-report-content]') || document;
    const previewTriggers = reportContent.querySelectorAll('[data-preview-symbol]');
    const stockDrawer = rootEl.querySelector('[data-stock-detail-drawer]');
    const stockClose = stockDrawer ? stockDrawer.querySelector('[data-stock-detail-close]') : null;
    const stockChart = stockDrawer ? stockDrawer.querySelector('[data-stock-chart]') : null;
    const stockChartEmpty = stockDrawer ? stockDrawer.querySelector('[data-stock-chart-empty]') : null;
    const stockChartTooltip = stockDrawer ? stockDrawer.querySelector('[data-stock-chart-tooltip]') : null;
    const stockChartWrap = stockDrawer ? stockDrawer.querySelector('[data-stock-chart-wrap]') : null;
    const stockCopy = stockDrawer ? stockDrawer.querySelector('[data-stock-copy]') : null;
    const stockFilterBoard = stockDrawer ? stockDrawer.querySelector('[data-stock-filter-board]') : null;
    const stockFilterLevel = stockDrawer ? stockDrawer.querySelector('[data-stock-filter-level]') : null;
    const stockLocateRow = stockDrawer ? stockDrawer.querySelector('[data-stock-locate-row]') : null;
    const stockActionStatus = stockDrawer ? stockDrawer.querySelector('[data-stock-action-status]') : null;
    const candleDataEl = rootEl.querySelector('[data-candidate-candles]');
    let candleData = {};
    try {
      candleData = candleDataEl ? JSON.parse(candleDataEl.textContent || '{}') : {};
    } catch (error) {
      console.warn('Invalid embedded candle data', error);
    }
    const stockFieldTargets = stockDrawer ? Array.from(stockDrawer.querySelectorAll('[data-stock-field]')).reduce((targetMap, el) => {
      const key = el.dataset.stockField || '';
      if (!targetMap[key]) {
        targetMap[key] = [];
      }
      targetMap[key].push(el);
      return targetMap;
    }, {}) : {};
    function emptyDetailDataset() {
      return {
        rowTitle: localizedStockText('Select a stock', '请选择股票'),
        rowDate: '-',
        rowSummary: localizedStockText('Use the table on the left to preview row details.', '从左侧表格选择股票后，这里显示行详情。'),
        rowReason: localizedStockText('No stock is selected.', '当前未选择股票。'),
        rowAction: localizedStockText('Search or reset filters to find matching candidates.', '可搜索或重置筛选条件查看候选。'),
        rowEvidence: localizedStockText('No public evidence is selected yet.', '尚未选中公开证据。'),
        rowLevel: localizedStockText('None', '无'),
        rowLevelClass: 'low',
        rowRisk: localizedStockText('None', '无'),
        rowRiskClass: 'notice'
      };
    }
    const detailTargets = ['detail-title', 'detail-date', 'detail-summary', 'detail-reason', 'detail-action', 'detail-evidence']
      .reduce((targetMap, attr) => {
        targetMap[attr] = detail ? Array.from(detail.querySelectorAll(`[data-${attr}]`)) : [];
        return targetMap;
      }, {});
    const detailLevelTargets = detail ? Array.from(detail.querySelectorAll('[data-detail-level]')) : [];
    const detailRisk = detail ? detail.querySelector('[data-detail-risk]') : null;
    let currentPage = 1;
    let selectedRow = null;
    let activeStockRow = null;
    let emptyRow = null;
    let renderHandle = 0;
    let stockResizeHandle = 0;
    let stockClosing = false;
    let stockChartObserver = null;
    let chartHoverIndex = -1;
    const technicalCache = new Map();
    if (stockDrawer && stockDrawer.parentElement !== document.body) {
      document.body.appendChild(stockDrawer);
    }

    function textOrDash(value) {
      return value && String(value).trim() ? String(value) : '-';
    }

    function localizedStockText(en, zh) {
      return root.dataset.lang === 'zh' ? zh : en;
    }

    function setStockActionStatus(text) {
      if (stockActionStatus) {
        stockActionStatus.textContent = text || '';
      }
    }

    function setToolbarStatus(text) {
      if (toolbarStatus) {
        toolbarStatus.textContent = text || '';
      }
    }

    function setText(attr, value) {
      (detailTargets[attr] || []).forEach(el => { el.textContent = value || ''; });
    }

    function updateDetail(dataset, isEmpty = false) {
      if (detail) {
        detail.dataset.empty = isEmpty ? 'true' : 'false';
      }
      const textMap = {
        rowTitle: 'detail-title', rowDate: 'detail-date', rowSummary: 'detail-summary',
        rowReason: 'detail-reason', rowAction: 'detail-action', rowEvidence: 'detail-evidence'
      };
      Object.entries(textMap).forEach(([key, attr]) => setText(attr, dataset[key]));
      detailLevelTargets.forEach(el => {
        el.textContent = dataset.rowLevel || '';
        el.className = 'level-badge ' + (dataset.rowLevelClass || 'low');
      });
      if (detailRisk) {
        detailRisk.textContent = dataset.rowRisk || dataset.riskLabel || dataset.risk || '';
        detailRisk.className = 'risk-badge ' + (dataset.rowRiskClass || 'notice');
      }
      if (detailOpenStock) {
        detailOpenStock.disabled = isEmpty;
      }
    }

    function setStockField(field, value) {
      (stockFieldTargets[field] || []).forEach(el => {
        el.textContent = textOrDash(value);
      });
    }

    function stockDataFor(row) {
      const symbol = row?.dataset?.rowSymbol || '';
      const candles = symbol && Object.prototype.hasOwnProperty.call(candleData, symbol) ? candleData[symbol] : [];
      return Array.isArray(candles) ? candles : [];
    }

    function lastNumber(values) {
      for (let index = values.length - 1; index >= 0; index -= 1) {
        if (Number.isFinite(values[index])) {
          return values[index];
        }
      }
      return NaN;
    }

    function average(values) {
      const valid = values.filter(Number.isFinite);
      return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : NaN;
    }

    function minMax(values) {
      let min = Infinity;
      let max = -Infinity;
      let seen = false;
      for (let index = 0; index < values.length; index += 1) {
        const value = values[index];
        if (!Number.isFinite(value)) {
          continue;
        }
        seen = true;
        if (value < min) {
          min = value;
        }
        if (value > max) {
          max = value;
        }
      }
      return seen ? { min, max } : { min: NaN, max: NaN };
    }

    function standardDeviation(values) {
      const valid = values.filter(Number.isFinite);
      if (!valid.length) {
        return NaN;
      }
      const mean = average(valid);
      const variance = average(valid.map(value => (value - mean) ** 2));
      return Number.isFinite(variance) ? Math.sqrt(variance) : NaN;
    }

    function movingAverage(values, period) {
      if (values.length < period) {
        return [];
      }
      return values.map((_, index) => {
        if (index + 1 < period) {
          return NaN;
        }
        return average(values.slice(index + 1 - period, index + 1));
      });
    }

    function exponentialAverage(values, period) {
      const multiplier = 2 / (period + 1);
      let previous = NaN;
      return values.map(value => {
        if (!Number.isFinite(value)) {
          return NaN;
        }
        previous = Number.isFinite(previous) ? value * multiplier + previous * (1 - multiplier) : value;
        return previous;
      });
    }

    function formatSignedPercent(value) {
      if (!Number.isFinite(value)) {
        return '-';
      }
      const sign = value > 0 ? '+' : '';
      return `${sign}${value.toFixed(2)}%`;
    }

    function formatNumber(value, digits = 2) {
      return Number.isFinite(value) ? value.toFixed(digits) : '-';
    }

    function calculateRsi(closes, period) {
      if (closes.length <= period) {
        return NaN;
      }
      let gains = 0;
      let losses = 0;
      for (let index = closes.length - period; index < closes.length; index += 1) {
        const delta = closes[index] - closes[index - 1];
        if (delta >= 0) {
          gains += delta;
        } else {
          losses -= delta;
        }
      }
      if (losses === 0) {
        return gains === 0 ? 50 : 100;
      }
      const rs = gains / losses;
      return 100 - 100 / (1 + rs);
    }

    function calculateKdj(candles, period) {
      if (candles.length < period) {
        return { k: NaN, d: NaN, j: NaN };
      }
      let k = 50;
      let d = 50;
      candles.forEach((item, index) => {
        if (index + 1 < period) {
          return;
        }
        const periodRows = candles.slice(index + 1 - period, index + 1);
        const range = minMax(periodRows.map(row => row.high));
        const floor = minMax(periodRows.map(row => row.low));
        const high = range.max;
        const low = floor.min;
        const rsv = high !== low ? (item.close - low) / (high - low) * 100 : 50;
        k = k * 2 / 3 + rsv / 3;
        d = d * 2 / 3 + k / 3;
      });
      return { k, d, j: 3 * k - 2 * d };
    }

    function calculateBollinger(closes, period) {
      if (closes.length < period) {
        return { mid: [], upper: [], lower: [], latest: { mid: NaN, upper: NaN, lower: NaN } };
      }
      const mid = [];
      const upper = [];
      const lower = [];
      closes.forEach((_, index) => {
        if (index + 1 < period) {
          mid.push(NaN);
          upper.push(NaN);
          lower.push(NaN);
          return;
        }
        const periodValues = closes.slice(index + 1 - period, index + 1);
        const mean = average(periodValues);
        const deviation = standardDeviation(periodValues);
        mid.push(mean);
        upper.push(Number.isFinite(deviation) ? mean + deviation * 2 : NaN);
        lower.push(Number.isFinite(deviation) ? mean - deviation * 2 : NaN);
      });
      return {
        mid,
        upper,
        lower,
        latest: {
          mid: lastNumber(mid),
          upper: lastNumber(upper),
          lower: lastNumber(lower),
        },
      };
    }

    function calculateAtr(candles, period) {
      if (candles.length <= period) {
        return NaN;
      }
      const ranges = candles.slice(1).map((item, index) => {
        const previousClose = candles[index].close;
        return Math.max(
          item.high - item.low,
          Math.abs(item.high - previousClose),
          Math.abs(item.low - previousClose)
        );
      });
      return average(ranges.slice(-period));
    }

    function calculateTechnicalIndicators(rows) {
      const candles = rows
        .map((item, originalIndex) => ({
          originalIndex,
          date: String(item[0] || ''),
          open: Number(item[1]),
          high: Number(item[2]),
          low: Number(item[3]),
          close: Number(item[4]),
          volume: Number(item[5]),
        }))
        .filter(item => [item.open, item.high, item.low, item.close].every(Number.isFinite));
      const closes = candles.map(item => item.close);
      const highs = candles.map(item => item.high);
      const lows = candles.map(item => item.low);
      const volumes = candles.map(item => item.volume);
      const lastClose = lastNumber(closes);
      const ma5 = movingAverage(closes, 5);
      const ma10 = movingAverage(closes, 10);
      const ma20 = movingAverage(closes, 20);
      const ma60 = movingAverage(closes, 60);
      const bollinger = calculateBollinger(closes, 20);
      const latestMa5 = lastNumber(ma5);
      const latestMa10 = lastNumber(ma10);
      const latestMa20 = lastNumber(ma20);
      const latestMa60 = lastNumber(ma60);
      const maSpread = Number.isFinite(latestMa20) && latestMa20 !== 0
        ? (latestMa5 - latestMa20) / latestMa20 * 100
        : NaN;
      const oneDayChange = closes.length >= 2 && closes[closes.length - 2] !== 0
        ? (lastClose - closes[closes.length - 2]) / closes[closes.length - 2] * 100
        : NaN;
      const twentyDayStart = closes.length >= 20 ? closes[closes.length - 20] : NaN;
      const twentyDayChange = Number.isFinite(twentyDayStart) && twentyDayStart !== 0
        ? (lastClose - twentyDayStart) / twentyDayStart * 100
        : NaN;
      const recentHigh = highs.length >= 20 ? minMax(highs.slice(-20)).max : NaN;
      const recentLow = lows.length >= 20 ? minMax(lows.slice(-20)).min : NaN;
      const drawdown = Number.isFinite(recentHigh) && recentHigh !== 0
        ? (lastClose - recentHigh) / recentHigh * 100
        : NaN;
      const highDistance = Number.isFinite(recentHigh) && recentHigh !== 0
        ? (lastClose - recentHigh) / recentHigh * 100
        : NaN;
      const lowDistance = Number.isFinite(recentLow) && recentLow !== 0
        ? (lastClose - recentLow) / recentLow * 100
        : NaN;
      const returns = closes.slice(1).map((value, index) => {
        const previous = closes[index];
        return previous ? (value - previous) / previous : NaN;
      }).filter(Number.isFinite);
      const recentReturns = returns.slice(-20);
      const returnAverage = average(recentReturns);
      const variance = recentReturns.length
        ? average(recentReturns.map(value => (value - returnAverage) ** 2))
        : NaN;
      const volatility = Number.isFinite(variance) ? Math.sqrt(variance) * Math.sqrt(252) * 100 : NaN;
      const latestVolume = lastNumber(volumes);
      const volumeBase = volumes.length > 1 ? average(volumes.slice(-21, -1)) : NaN;
      const volumeRatio = Number.isFinite(volumeBase) && volumeBase > 0 ? latestVolume / volumeBase : NaN;
      const rsi = calculateRsi(closes, 14);
      const kdj = calculateKdj(candles, 9);
      const atr = calculateAtr(candles, 14);
      const atrRatio = Number.isFinite(atr) && Number.isFinite(lastClose) && lastClose > 0 ? atr / lastClose * 100 : NaN;
      const bollPosition = Number.isFinite(bollinger.latest.upper) && Number.isFinite(bollinger.latest.lower) && bollinger.latest.upper !== bollinger.latest.lower
        ? (lastClose - bollinger.latest.lower) / (bollinger.latest.upper - bollinger.latest.lower) * 100
        : NaN;
      const ema12 = exponentialAverage(closes, 12);
      const ema26 = exponentialAverage(closes, 26);
      const dif = ema12.map((value, index) => (
        Number.isFinite(value) && Number.isFinite(ema26[index]) ? value - ema26[index] : NaN
      ));
      const dea = exponentialAverage(dif, 9);
      const macdHist = lastNumber(dif) - lastNumber(dea);
      const trendStatus = Number.isFinite(lastClose) && Number.isFinite(latestMa20) && Number.isFinite(latestMa60)
        ? (lastClose >= latestMa20 && latestMa20 >= latestMa60 ? 'positive' : lastClose < latestMa20 ? 'negative' : 'attention')
        : 'attention';
      const momentumStatus = Number.isFinite(twentyDayChange)
        ? (twentyDayChange >= 8 ? 'positive' : twentyDayChange <= -8 ? 'negative' : 'attention')
        : 'attention';
      const rsiStatus = Number.isFinite(rsi)
        ? (rsi >= 70 ? 'attention' : rsi <= 30 ? 'negative' : 'positive')
        : 'attention';
      const macdStatus = Number.isFinite(macdHist)
        ? (macdHist > 0 ? 'positive' : macdHist < 0 ? 'negative' : 'attention')
        : 'attention';
      const kdjStatus = Number.isFinite(kdj.j)
        ? (kdj.j >= 100 ? 'attention' : kdj.j <= 0 ? 'negative' : kdj.k >= kdj.d ? 'positive' : 'attention')
        : 'attention';
      const bollingerStatus = Number.isFinite(bollPosition)
        ? (bollPosition >= 92 ? 'attention' : bollPosition <= 8 ? 'negative' : 'positive')
        : 'attention';
      const atrStatus = Number.isFinite(atrRatio)
        ? (atrRatio >= 7 ? 'attention' : atrRatio <= 2 ? 'positive' : 'neutral')
        : 'attention';
      const volumeStatus = Number.isFinite(volumeRatio)
        ? (volumeRatio >= 1.8 ? 'attention' : volumeRatio >= 1.1 ? 'positive' : 'neutral')
        : 'attention';
      return {
        candles,
        ma5,
        ma20,
        bollinger,
        fields: {
          'technical-trend': Number.isFinite(latestMa20)
            ? (trendStatus === 'positive'
              ? localizedStockText('Above MA20/MA60', '站上 MA20/MA60')
              : trendStatus === 'negative'
                ? localizedStockText('Below MA20', '低于 MA20')
                : localizedStockText('Mixed moving averages', '均线结构分化'))
            : localizedStockText('Need more K-line data', 'K 线数据不足'),
          'technical-momentum': formatSignedPercent(twentyDayChange),
          'technical-ma-spread': Number.isFinite(maSpread)
            ? `${formatNumber(latestMa5)} / ${formatNumber(latestMa20)} (${formatSignedPercent(maSpread)})`
            : '-',
          'technical-rsi': formatNumber(rsi, 1),
          'technical-macd': formatNumber(macdHist, 3),
          'technical-kdj': Number.isFinite(kdj.k)
            ? `K ${formatNumber(kdj.k, 1)} / D ${formatNumber(kdj.d, 1)} / J ${formatNumber(kdj.j, 1)}`
            : '-',
          'technical-bollinger': Number.isFinite(bollPosition)
            ? `${formatNumber(bollPosition, 1)}%`
            : '-',
          'technical-atr': Number.isFinite(atrRatio)
            ? `${formatNumber(atrRatio, 2)}%`
            : '-',
          'technical-volatility': Number.isFinite(volatility)
            ? `${formatNumber(volatility, 1)}%`
            : '-',
          'technical-volume-ratio': Number.isFinite(volumeRatio)
            ? `${formatNumber(volumeRatio, 2)}x`
            : '-',
          'technical-range': Number.isFinite(lowDistance) && Number.isFinite(highDistance)
            ? `${formatSignedPercent(lowDistance)} / ${formatSignedPercent(highDistance)}`
            : '-',
          'technical-drawdown': formatSignedPercent(drawdown),
          'technical-support-pressure': Number.isFinite(recentLow) && Number.isFinite(recentHigh)
            ? `${formatNumber(recentLow)} / ${formatNumber(recentHigh)}`
            : '-',
          'technical-summary': candles.length >= 20
            ? localizedStockText(
              `Local technical read: ${formatSignedPercent(twentyDayChange)} over 20 sessions, RSI ${formatNumber(rsi, 1)}, volume ${formatNumber(volumeRatio, 2)}x.`,
              `本地技术读数：20 个交易日 ${formatSignedPercent(twentyDayChange)}，RSI ${formatNumber(rsi, 1)}，量能 ${formatNumber(volumeRatio, 2)}x。`
            )
            : localizedStockText('Not enough local K-line data for full technical indicators.', '本地 K 线不足，无法完整计算技术指标。'),
          'technical-data-quality': localizedStockText(
            `Calculated from ${candles.length} local K-line rows. Indicators are for screening review only, not live trading signals.`,
            `基于 ${candles.length} 条本地 K 线计算。指标仅用于筛选复核，不是实时交易信号。`
          ),
        },
        statuses: {
          trend: trendStatus,
          momentum: momentumStatus,
          ma: Number.isFinite(maSpread) ? (maSpread >= 0 ? 'positive' : 'negative') : 'attention',
          rsi: rsiStatus,
          macd: macdStatus,
          kdj: kdjStatus,
          bollinger: bollingerStatus,
          atr: atrStatus,
          volatility: Number.isFinite(volatility) && volatility >= 55 ? 'attention' : 'neutral',
          volume: volumeStatus,
          range: Number.isFinite(highDistance) && highDistance > -3 ? 'attention' : 'neutral',
          drawdown: Number.isFinite(drawdown) && drawdown <= -15 ? 'negative' : 'neutral',
          'support-pressure': Number.isFinite(recentLow) && Number.isFinite(recentHigh) ? 'neutral' : 'attention',
        },
      };
    }

    function technicalCacheKey(rows) {
      return JSON.stringify(rows || []);
    }

    function indicatorsForRows(rows) {
      const key = technicalCacheKey(rows);
      if (!technicalCache.has(key)) {
        technicalCache.set(key, calculateTechnicalIndicators(rows));
      }
      return technicalCache.get(key);
    }

    function updateTechnicalIndicators(rows, indicators = indicatorsForRows(rows)) {
      Object.entries(indicators.fields).forEach(([field, value]) => setStockField(field, value));
      if (stockDrawer) {
        stockDrawer.querySelectorAll('[data-stock-tech-card]').forEach(card => {
          const key = card.dataset.stockTechCard || '';
          const status = indicators.statuses[key] || 'neutral';
          card.dataset.status = status;
        });
      }
      return indicators;
    }

    function drawStockCandles() {
      if (!stockChart || !stockDrawer || stockDrawer.hidden) {
        return;
      }
      const rows = stockDataFor(activeStockRow);
      const technical = indicatorsForRows(rows);
      const showEmpty = !rows.length;
      if (stockChartEmpty) {
        stockChartEmpty.hidden = !showEmpty;
        stockChartEmpty.textContent = showEmpty
          ? localizedStockText('No local K-line data was embedded for this row.', '本行没有嵌入本地 K 线数据。')
          : '';
      }
      stockChart.hidden = showEmpty;
      if (showEmpty) {
        return;
      }
      const rect = stockChart.getBoundingClientRect();
      const width = Math.max(1, Math.floor(rect.width || 0));
      const height = Math.max(1, Math.floor(rect.height || 0));
      const dpr = window.devicePixelRatio || 1;
      const canvasWidth = Math.floor(width * dpr);
      const canvasHeight = Math.floor(height * dpr);
      if (stockChart.width !== canvasWidth) {
        stockChart.width = canvasWidth;
      }
      if (stockChart.height !== canvasHeight) {
        stockChart.height = canvasHeight;
      }
      const ctx = stockChart.getContext('2d');
      if (!ctx) {
        return;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, width, height);
      const margin = { top: 18, right: 58, bottom: width < 520 ? 42 : 32, left: width < 520 ? 10 : 14 };
      const plotWidth = width - margin.left - margin.right;
      const plotHeight = height - margin.top - margin.bottom;
      const ma5 = technical.ma5;
      const ma20 = technical.ma20;
      const bollinger = technical.bollinger;
      const values = rows
        .flatMap(item => [Number(item[1]), Number(item[2]), Number(item[3]), Number(item[4])])
        .concat(ma5, ma20, bollinger.upper, bollinger.lower)
        .filter(Number.isFinite);
      if (!values.length) {
        return;
      }
      const range = minMax(values);
      const minValue = range.min;
      const maxValue = range.max;
      const span = Math.max(maxValue - minValue, 1e-6);
      const priceY = value => margin.top + (maxValue - value) / span * plotHeight;
      const candleGap = Math.max(2, plotWidth / rows.length * 0.18);
      const candleWidth = Math.max(3, Math.min(10, plotWidth / rows.length - candleGap));
      ctx.strokeStyle = '#e5e7eb';
      ctx.fillStyle = '#64748b';
      ctx.font = '11px -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i += 1) {
        const y = margin.top + (plotHeight * i / 4);
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(width - margin.right, y);
        ctx.stroke();
        const value = maxValue - span * i / 4;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(value.toFixed(2), width - 6, y);
      }
      const step = rows.length > 1 ? plotWidth / (rows.length - 1) : 0;
      const labelTarget = width < 420 ? 3 : width < 620 ? 4 : 6;
      const labelEvery = Math.max(1, Math.ceil(rows.length / labelTarget));
      rows.forEach((item, index) => {
        const open = Number(item[1]);
        const high = Number(item[2]);
        const low = Number(item[3]);
        const close = Number(item[4]);
        if (![open, high, low, close].every(Number.isFinite)) {
          return;
        }
        const x = margin.left + (rows.length > 1 ? step * index : plotWidth / 2);
        const wickTop = priceY(high);
        const wickBottom = priceY(low);
        const bodyTop = priceY(Math.max(open, close));
        const bodyBottom = priceY(Math.min(open, close));
        const bodyHeight = Math.max(1, bodyBottom - bodyTop);
        const up = close >= open;
        ctx.strokeStyle = up ? '#c73535' : '#0a8f63';
        ctx.fillStyle = up ? '#c73535' : '#0a8f63';
        ctx.beginPath();
        ctx.moveTo(x, wickTop);
        ctx.lineTo(x, wickBottom);
        ctx.stroke();
        ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
        if (index === 0 || index % labelEvery === 0 || index === rows.length - 1) {
          const rawDate = String(item[0] || '');
          const label = width < 520 ? rawDate.slice(5) : rawDate;
          const labelX = Math.min(width - margin.right + 10, Math.max(margin.left + 14, x));
          ctx.save();
          ctx.translate(labelX, height - 15);
          ctx.rotate(width < 520 ? -Math.PI / 6 : -Math.PI / 8);
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = '#64748b';
          ctx.fillText(label, 0, 0);
          ctx.restore();
        }
      });
      const lineSeries = [
        { values: ma5, color: '#1b75d0', label: 'MA5' },
        { values: ma20, color: '#f08a00', label: 'MA20' },
        { values: bollinger.upper, color: '#94a3b8', label: 'BOLL upper' },
        { values: bollinger.lower, color: '#94a3b8', label: 'BOLL lower' },
      ];
      lineSeries.forEach(series => {
        const points = series.values
          .map((value, index) => {
            const source = technical.candles[index];
            const sourceIndex = source ? source.originalIndex : index;
            return Number.isFinite(value)
              ? { x: margin.left + (rows.length > 1 ? step * sourceIndex : plotWidth / 2), y: priceY(value) }
              : null;
          })
          .filter(Boolean);
        if (points.length < 2) {
          return;
        }
        ctx.save();
        ctx.strokeStyle = series.color;
        ctx.lineWidth = series.label.startsWith('BOLL') ? 1 : 2;
        if (series.label.startsWith('BOLL')) {
          ctx.setLineDash([5, 5]);
        }
        ctx.beginPath();
        points.forEach((point, index) => {
          if (index === 0) {
            ctx.moveTo(point.x, point.y);
          } else {
            ctx.lineTo(point.x, point.y);
          }
        });
        ctx.stroke();
        ctx.restore();
      });
      if (stockChartTooltip) {
        if (chartHoverIndex < 0 || chartHoverIndex >= rows.length) {
          stockChartTooltip.hidden = true;
          stockChartTooltip.textContent = '';
          return;
        }
        const hover = rows[chartHoverIndex];
        const hoverClose = Number(hover[4]);
        if (!Number.isFinite(hoverClose)) {
          stockChartTooltip.hidden = true;
          stockChartTooltip.textContent = '';
          return;
        }
        const hoverX = margin.left + (rows.length > 1 ? step * chartHoverIndex : plotWidth / 2);
        const hoverY = priceY(hoverClose);
        ctx.save();
        ctx.strokeStyle = '#94a3b8';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(hoverX, margin.top);
        ctx.lineTo(hoverX, height - margin.bottom);
        ctx.moveTo(margin.left, hoverY);
        ctx.lineTo(width - margin.right, hoverY);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#0f172a';
        ctx.beginPath();
        ctx.arc(hoverX, hoverY, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        const open = Number(hover[1]);
        const high = Number(hover[2]);
        const low = Number(hover[3]);
        const close = Number(hover[4]);
        const volume = Number(hover[5]);
        stockChartTooltip.innerHTML = [
          `<strong>${String(hover[0] || '')}</strong>`,
          `<span>O ${formatNumber(open)} H ${formatNumber(high)} L ${formatNumber(low)} C ${formatNumber(close)}</span>`,
          `<span>V ${Number.isFinite(volume) ? volume.toLocaleString('en-US') : '-'}</span>`,
        ].join('');
        stockChartTooltip.hidden = false;
        const tooltipWidth = Math.min(210, width - 20);
        const tooltipHeight = Math.min(76, height - 20);
        const left = hoverX + tooltipWidth + 14 > width ? hoverX - tooltipWidth - 12 : hoverX + 12;
        const top = hoverY + tooltipHeight + 14 > height ? hoverY - tooltipHeight - 12 : hoverY + 12;
        stockChartTooltip.style.left = `${Math.min(width - tooltipWidth - 10, Math.max(10, left))}px`;
        stockChartTooltip.style.top = `${Math.min(height - tooltipHeight - 10, Math.max(10, top))}px`;
      }
    }

    function ensureStockChartObserver() {
      if (!stockChartWrap || !('ResizeObserver' in window)) {
        return;
      }
      if (!stockChartObserver) {
        stockChartObserver = new ResizeObserver(() => scheduleStockResize());
      }
      stockChartObserver.observe(stockChartWrap);
    }

    function clearStockChartHover() {
      chartHoverIndex = -1;
      if (stockChartTooltip) {
        stockChartTooltip.hidden = true;
        stockChartTooltip.textContent = '';
      }
      scheduleStockResize();
    }

    function updateStockChartHover(event) {
      if (!stockChart || !stockDrawer || stockDrawer.hidden) {
        return;
      }
      const rows = stockDataFor(activeStockRow);
      if (!rows.length) {
        clearStockChartHover();
        return;
      }
      const rect = stockChart.getBoundingClientRect();
      const width = Math.max(1, Math.floor(rect.width || 0));
      const height = Math.max(1, Math.floor(rect.height || 0));
      const margin = { top: 18, right: 58, bottom: width < 520 ? 42 : 32, left: width < 520 ? 10 : 14 };
      const plotWidth = width - margin.left - margin.right;
      const plotHeight = height - margin.top - margin.bottom;
      if (plotWidth <= 0 || plotHeight <= 0) {
        return;
      }
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      if (x < margin.left || x > width - margin.right || y < margin.top || y > height - margin.bottom) {
        clearStockChartHover();
        return;
      }
      const step = rows.length > 1 ? plotWidth / (rows.length - 1) : plotWidth;
      const nextHoverIndex = rows.length > 1
        ? Math.max(0, Math.min(rows.length - 1, Math.round((x - margin.left) / step)))
        : 0;
      if (chartHoverIndex === nextHoverIndex) {
        return;
      }
      chartHoverIndex = nextHoverIndex;
      scheduleStockResize();
    }

    function updateStockDrawer(row) {
      if (!stockDrawer) {
        return;
      }
      activeStockRow = row;
      chartHoverIndex = -1;
      const symbol = row?.dataset?.rowSymbol || '';
      setStockField('board', row?.dataset?.rowBoard || '');
      setStockField('title', row?.dataset?.rowTitle || '');
      setStockField('date', row?.dataset?.rowDate || '-');
      setStockField('industry', row?.dataset?.rowIndustry || '');
      setStockField('symbol', symbol);
      setStockField('name', row?.dataset?.rowName || '');
      setStockField('score', row?.dataset?.rowScore || '');
      setStockField('level', row?.dataset?.rowLevel || '');
      setStockField('close', row?.dataset?.rowClose || '');
      setStockField('one-year', row?.dataset?.rowOneYear || '');
      setStockField('market-cap', row?.dataset?.rowMarketCap || '');
      setStockField('pe', row?.dataset?.rowPe || '');
      setStockField('pb', row?.dataset?.rowPb || '');
      setStockField('summary', row?.dataset?.rowSummary || '');
      setStockField('reason', row?.dataset?.rowReason || '');
      setStockField('field-availability', row?.dataset?.rowFieldAvailability || '');
      setStockField('risk', row?.dataset?.rowRisk || '');
      setStockField('action', row?.dataset?.rowAction || '');
      setStockField('evidence', row?.dataset?.rowEvidence || '');
      const candles = stockDataFor(row);
      setStockField('candle-count', String(candles.length));
      const first = candles[0];
      const last = candles[candles.length - 1];
      setStockField(
        'candle-range',
        candles.length
          ? `${String(first[0] || '')} - ${String(last[0] || '')}`
          : localizedStockText('No local K-line data', '无本地 K 线数据')
      );
      updateTechnicalIndicators(candles);
      stockDrawer.dataset.selectedSymbol = symbol;
      stockDrawer.dataset.selectedName = row?.dataset?.rowName || '';
    }

    function focusableStockElements() {
      return stockDrawer
        ? Array.from(stockDrawer.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'))
            .filter(el => !el.disabled && el.offsetParent !== null)
        : [];
    }

    function trapStockFocus(event) {
      const elements = focusableStockElements();
      if (!elements.length) {
        event.preventDefault();
        return;
      }
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (!elements.includes(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    function openStockDrawer(row) {
      if (!stockDrawer || !row) {
        return;
      }
      updateStockDrawer(row);
      if (activeStockRow) {
        activeStockRow.setAttribute('aria-expanded', 'true');
      }
      stockDrawer.hidden = false;
      stockDrawer.setAttribute('aria-hidden', 'false');
      setModalContentHidden(true, stockDrawer);
      setBodyLocked(true);
      document.removeEventListener('keydown', handleStockKeydown);
      document.addEventListener('keydown', handleStockKeydown);
      setStockActionStatus('');
      ensureStockChartObserver();
      scheduleStockResize();
      stockClose && stockClose.focus();
    }

    function closeStockDrawer() {
      if (!stockDrawer || stockDrawer.hidden || stockClosing) {
        return;
      }
      stockClosing = true;
      stockDrawer.hidden = true;
      stockDrawer.setAttribute('aria-hidden', 'true');
      document.removeEventListener('keydown', handleStockKeydown);
      if (stockChartObserver) {
        stockChartObserver.disconnect();
      }
      if (activeStockRow) {
        activeStockRow.setAttribute('aria-expanded', 'false');
      }
      stockDrawer.dataset.selectedSymbol = '';
      stockDrawer.dataset.selectedName = '';
      clearStockChartHover();
      setBodyLocked(false);
      setModalContentHidden(false, null);
      stockClosing = false;
      if (selectedRow && selectedRow.isConnected) {
        selectedRow.focus();
      }
    }

    function filterCurrentStock(field) {
      if (!activeStockRow) {
        return;
      }
      const target = field === 'board' ? board : level;
      const value = field === 'board' ? activeStockRow.dataset.board : activeStockRow.dataset.level;
      if (!target || !value) {
        setStockActionStatus(localizedStockText('No matching filter is available for this row.', '本行没有可用的同类筛选条件。'));
        return;
      }
      target.value = value;
      currentPage = 1;
      closeStockDrawer();
      applySort();
    }

    function locateCurrentStock() {
      closeStockDrawer();
      if (selectedRow && selectedRow.isConnected) {
        selectedRow.focus();
      }
    }

    async function copyCurrentStockSummary() {
      if (!activeStockRow) {
        return;
      }
      const row = activeStockRow.dataset;
      const summary = [
        `${row.rowName || '-'} ${row.rowSymbol || '-'}`,
        `${localizedStockText('Board', '板块')}: ${row.rowBoard || '-'}`,
        `${localizedStockText('Level', '观察等级')}: ${row.rowLevel || '-'}`,
        `${localizedStockText('Score', '综合评分')}: ${row.rowScore || '-'}`,
        `${localizedStockText('Close', '参考收盘价')}: ${row.rowClose || '-'}`,
        `${localizedStockText('1Y change', '近一年涨跌幅')}: ${row.rowOneYear || '-'}`,
        `${localizedStockText('Summary', '摘要')}: ${row.rowSummary || '-'}`,
        `${localizedStockText('Risk', '风险')}: ${row.rowRisk || '-'}`,
        `${localizedStockText('Report note', '报告提示')}: ${row.rowAction || '-'}`,
      ].join('\\n');
      if (!summary) {
        return;
      }
      try {
        await navigator.clipboard.writeText(summary);
        setStockActionStatus(localizedStockText('Copied. Verify current market data before any decision.', '已复制。做决定前请再次核验实时行情。'));
      } catch (error) {
        const fileHint = window.location.protocol === 'file:'
          ? localizedStockText(' Clipboard access is often blocked for local file reports.', ' 本地文件模式通常会限制剪贴板访问。')
          : '';
        setStockActionStatus(localizedStockText(
          `Copy failed.${fileHint} Select the text manually if needed.`,
          `复制失败。${fileHint} 可手动选择文本。`
        ));
      }
    }

    function scheduleStockResize() {
      if (!stockDrawer || stockDrawer.hidden) {
        return;
      }
      if (stockResizeHandle) {
        cancelAnimationFrame(stockResizeHandle);
      }
      stockResizeHandle = requestAnimationFrame(() => {
        stockResizeHandle = 0;
        drawStockCandles();
      });
    }

    function setDetail(row) {
      if (!row || !detail) {
        return;
      }
      if (row === selectedRow) {
        return;
      }
      if (selectedRow) {
        selectedRow.dataset.selected = 'false';
      }
      selectedRow = row;
      selectedRow.dataset.selected = 'true';
      updateDetail(row.dataset);
    }

    function clearDetail() {
      if (selectedRow) {
        selectedRow.dataset.selected = 'false';
      }
      selectedRow = null;
      updateDetail(emptyDetailDataset(), true);
    }

    function ensureEmptyRow() {
      if (emptyRow || !tbody) {
        return emptyRow;
      }
      emptyRow = document.createElement('tr');
      emptyRow.className = 'candidate-empty-row';
      const cell = document.createElement('td');
      cell.colSpan = rootEl.querySelectorAll('.master-table thead th').length || 1;
      const state = document.createElement('div');
      state.className = 'candidate-empty-state';
      const title = document.createElement('strong');
      title.textContent = localizedStockText('No matching stocks', '暂无匹配股票');
      const hint = document.createElement('span');
      hint.textContent = localizedStockText('Try clearing filters or changing the search keyword.', '请清空筛选或调整搜索关键词。');
      state.append(title, hint);
      cell.appendChild(state);
      emptyRow.appendChild(cell);
      return emptyRow;
    }

    function refreshEmptyRowText() {
      if (!emptyRow) {
        return;
      }
      const title = emptyRow.querySelector('.candidate-empty-state strong');
      const hint = emptyRow.querySelector('.candidate-empty-state span');
      if (title) {
        title.textContent = localizedStockText('No matching stocks', '暂无匹配股票');
      }
      if (hint) {
        hint.textContent = localizedStockText(
          'Try clearing filters or changing the search keyword.',
          '请清空筛选或调整搜索关键词。'
        );
      }
    }

    function findRowBySymbol(symbol) {
      return rows.find(row => row.dataset.rowSymbol === symbol || row.dataset.symbol === symbol) || null;
    }

    function clearFiltersForPreview() {
      let changed = false;
      [search, board, industry, level].forEach(el => {
        if (el && el.value) {
          el.value = '';
          changed = true;
        }
      });
      return changed;
    }

    function showRowOnCurrentPage(row) {
      if (!row) {
        setToolbarStatus(localizedStockText('Stock is not in the complete candidate table.', '完整候选表中没有找到该股票。'));
        return;
      }
      let matchingRows = rows.filter(rowMatches);
      let index = matchingRows.indexOf(row);
      if (index < 0) {
        const cleared = clearFiltersForPreview();
        matchingRows = rows.filter(rowMatches);
        index = matchingRows.indexOf(row);
        setToolbarStatus(cleared
          ? localizedStockText('Filters were cleared to locate this stock.', '已清空筛选以定位该股票。')
          : localizedStockText('Stock is not visible under the current filters.', '当前筛选条件下未显示该股票。'));
      } else {
        setToolbarStatus('');
      }
      if (index >= 0) {
        currentPage = Math.floor(index / pageLimit()) + 1;
      } else {
        setToolbarStatus(localizedStockText('Stock is not in the complete candidate table.', '完整候选表中没有找到该股票。'));
      }
      renderNow();
      setDetail(row);
      row.focus();
    }

    function renderNow(options = {}) {
      if (renderHandle) {
        cancelAnimationFrame(renderHandle);
        renderHandle = 0;
      }
      render(options);
    }

    function scheduleRender() {
      if (renderHandle) {
        cancelAnimationFrame(renderHandle);
      }
      renderHandle = requestAnimationFrame(() => {
        renderHandle = 0;
        render();
      });
    }

    function renderPages(pages) {
      if (!pageNumbers) {
        return;
      }
      pageNumbers.textContent = '';
      const makeButton = page => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'candidate-page-number' + (page === currentPage ? ' active' : '');
        button.textContent = String(page);
        button.addEventListener('click', () => {
          currentPage = page;
          renderNow();
        });
        pageNumbers.appendChild(button);
      };
      const visiblePages = new Set([1, pages, currentPage - 1, currentPage, currentPage + 1]);
      let previousPage = 0;
      [...visiblePages]
        .filter(page => page >= 1 && page <= pages)
        .sort((a, b) => a - b)
        .forEach(page => {
          if (previousPage && page - previousPage > 1) {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'candidate-page-ellipsis';
            ellipsis.textContent = '...';
            pageNumbers.appendChild(ellipsis);
          }
          makeButton(page);
          previousPage = page;
        });
    }

    function pageLimit() {
      return Number(pageSize?.value || 10) || 10;
    }

    function rowMatches(row) {
      const query = (search?.value || '').trim().toLowerCase();
      const terms = query.split(/\\s+/).filter(Boolean);
      const haystack = row.dataset.search || '';
      return (!terms.length || terms.every(term => haystack.includes(term)))
        && (!(board?.value || '') || row.dataset.board === board.value)
        && (!(industry?.value || '') || row.dataset.industry === industry.value)
        && (!(level?.value || '') || row.dataset.level === level.value);
    }

    function render(options = {}) {
      const visible = rows.filter(rowMatches);
      const pages = Math.max(1, Math.ceil(visible.length / pageLimit()));
      currentPage = Math.min(currentPage, pages);
      const start = (currentPage - 1) * pageLimit();
      const shownRows = visible.slice(start, start + pageLimit());
      if (total) {
        total.textContent = String(rows.length);
      }
      if (count) {
        count.textContent = String(visible.length);
      }
      if (pageCurrent) {
        pageCurrent.textContent = String(currentPage);
      }
      if (pageTotal) {
        pageTotal.textContent = String(pages);
      }
      if (prev) {
        prev.disabled = currentPage <= 1;
      }
      if (next) {
        next.disabled = currentPage >= pages;
      }
      renderPages(pages);
      if (tbody && !options.skipDomMount) {
        const fragment = document.createDocumentFragment();
        if (shownRows.length) {
          shownRows.forEach(row => {
            row.hidden = false;
            fragment.appendChild(row);
          });
        } else {
          fragment.appendChild(ensureEmptyRow());
        }
        tbody.replaceChildren(fragment);
        mountedRows = shownRows;
      } else if (tbody) {
        mountedRows = shownRows;
      }
      if (!visible.length) {
        clearDetail();
        return;
      }
      const selected = selectedRow && mountedRows.includes(selectedRow) ? selectedRow : shownRows[0];
      setDetail(selected);
    }

    function applyFilters() {
      setToolbarStatus('');
      currentPage = 1;
      scheduleRender();
    }

    function applySort() {
      if (!tbody) {
        return;
      }
      setToolbarStatus('');
      currentPage = 1;
      rows = [...rows].sort((a, b) => {
        if ((sort?.value || 'score') === 'score') {
          const scoreA = Number(a.dataset.score);
          const scoreB = Number(b.dataset.score);
          return (Number.isFinite(scoreB) ? scoreB : -Infinity) - (Number.isFinite(scoreA) ? scoreA : -Infinity);
        }
        const rankA = Number(a.dataset.rank);
        const rankB = Number(b.dataset.rank);
        return (Number.isFinite(rankA) ? rankA : Infinity) - (Number.isFinite(rankB) ? rankB : Infinity);
      });
      mountedRows = [];
      renderNow();
    }

    if (tbody) {
      tbody.addEventListener('click', event => {
        const target = event.target instanceof Element ? event.target : null;
        const row = target ? target.closest('[data-candidate-row]') : null;
        if (!row || !tbody.contains(row)) {
          return;
        }
        setDetail(row);
      });
      tbody.addEventListener('dblclick', event => {
        const target = event.target instanceof Element ? event.target : null;
        const row = target ? target.closest('[data-candidate-row]') : null;
        if (!row || !tbody.contains(row)) {
          return;
        }
        setDetail(row);
        openStockDrawer(row);
      });
      tbody.addEventListener('keydown', event => {
        if (!(event.target instanceof Element)) {
          return;
        }
        const row = event.target.closest('[data-candidate-row]');
        if (!row || !tbody.contains(row)) {
          return;
        }
        if (event.key !== 'Enter' && event.key !== ' ') {
          return;
        }
        event.preventDefault();
        if (event.key === 'Enter' && row === selectedRow) {
          openStockDrawer(row);
          return;
        }
        setDetail(row);
      });
    }

    detailOpenStock && detailOpenStock.addEventListener('click', () => {
      if (selectedRow) {
        openStockDrawer(selectedRow);
      }
    });
    previewTriggers.forEach(trigger => {
      trigger.addEventListener('click', () => showRowOnCurrentPage(findRowBySymbol(trigger.dataset.previewSymbol || '')));
      trigger.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') {
          return;
        }
        event.preventDefault();
        showRowOnCurrentPage(findRowBySymbol(trigger.dataset.previewSymbol || ''));
      });
    });

    search && search.addEventListener('input', applyFilters);
    search && search.addEventListener('search', applyFilters);
    [board, industry, level].forEach(el => el && el.addEventListener('change', applyFilters));
    sort && sort.addEventListener('change', applySort);
    pageSize && pageSize.addEventListener('change', applyFilters);
    prev && prev.addEventListener('click', () => {
      currentPage = Math.max(1, currentPage - 1);
      renderNow();
    });
    next && next.addEventListener('click', () => {
      currentPage += 1;
      renderNow();
    });
    reset && reset.addEventListener('click', () => {
      if (search) { search.value = ''; }
      if (board) { board.value = ''; }
      if (industry) { industry.value = ''; }
      if (level) { level.value = ''; }
      if (sort) { sort.value = 'score'; }
      applySort();
    });
    stockClose && stockClose.addEventListener('click', closeStockDrawer);
    stockCopy && stockCopy.addEventListener('click', copyCurrentStockSummary);
    stockFilterBoard && stockFilterBoard.addEventListener('click', () => filterCurrentStock('board'));
    stockFilterLevel && stockFilterLevel.addEventListener('click', () => filterCurrentStock('level'));
    stockLocateRow && stockLocateRow.addEventListener('click', locateCurrentStock);
    stockChart && stockChart.addEventListener('pointermove', updateStockChartHover);
    stockChart && stockChart.addEventListener('pointerleave', clearStockChartHover);
    stockChart && stockChart.addEventListener('pointerdown', updateStockChartHover);
    stockDrawer && stockDrawer.addEventListener('click', event => {
      if (event.target === stockDrawer) {
        closeStockDrawer();
      }
    });
    function handleStockKeydown(event) {
      if (!stockDrawer || stockDrawer.hidden) {
        return;
      }
      if (event.key === 'Escape') {
        closeStockDrawer();
      } else if (event.key === 'Tab') {
        trapStockFocus(event);
      }
    }
    window.addEventListener('resize', scheduleStockResize, { passive: true });
    document.addEventListener('report-language-change', () => {
      if (stockDrawer && !stockDrawer.hidden && activeStockRow) {
        updateStockDrawer(activeStockRow);
        drawStockCandles();
      }
      refreshEmptyRowText();
      if (!selectedRow) {
        updateDetail(emptyDetailDataset(), true);
      }
    });
    window.addEventListener('beforeunload', () => setBodyLocked(false), { once: true });
    mountedRows = rows.filter(row => !row.hidden);
    renderNow();
  });
}
  function initInsightDrawer() {
    const drawer = document.querySelector('[data-insight-drawer]');
    if (!drawer) {
      return;
    }
    const title = drawer.querySelector('[data-insight-title]');
    const summary = drawer.querySelector('[data-insight-summary]');
    const kind = drawer.querySelector('[data-insight-kind]');
    const facts = drawer.querySelector('[data-insight-facts]');
    const actions = drawer.querySelector('[data-insight-actions]');
    const closeButton = drawer.querySelector('[data-insight-close]');
    let activeTrigger = null;
    function langSuffix() {
      return root.dataset.lang === 'zh' ? 'Zh' : 'En';
    }
    function localizedDataset(trigger, key) {
      return trigger.dataset[key + langSuffix()] || trigger.dataset[key + 'En'] || '';
    }
    function splitItems(text) {
      return (text || '').split('|').map(item => item.trim()).filter(Boolean);
    }
    function renderFacts(text) {
      facts.textContent = '';
      splitItems(text).forEach(item => {
        const index = item.indexOf('::');
        const labelText = index >= 0 ? item.slice(0, index) : item;
        const valueText = index >= 0 ? item.slice(index + 2) : '';
        const dt = document.createElement('dt');
        const dd = document.createElement('dd');
        dt.textContent = labelText;
        dd.textContent = valueText || '-';
        facts.append(dt, dd);
      });
    }
    function renderActions(text) {
      actions.textContent = '';
      splitItems(text).forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        actions.appendChild(li);
      });
    }
    function render(trigger) {
      activeTrigger = trigger;
      title.textContent = localizedDataset(trigger, 'insightTitle');
      summary.textContent = localizedDataset(trigger, 'insightSummary');
      kind.textContent = localizedDataset(trigger, 'insightKind');
      renderFacts(localizedDataset(trigger, 'insightFacts'));
      renderActions(localizedDataset(trigger, 'insightActions'));
    }
    function focusableElements() {
      return Array.from(drawer.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'))
        .filter(el => !el.disabled && el.offsetParent !== null);
    }
    function trapFocus(event) {
      const elements = focusableElements();
      if (!elements.length) {
        event.preventDefault();
        return;
      }
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (!elements.includes(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    function handleKeydown(event) {
      if (event.key === 'Escape' && !drawer.hidden) {
        closeDrawer();
      } else if (event.key === 'Tab' && !drawer.hidden) {
        trapFocus(event);
      }
    }
    function open(trigger) {
      render(trigger);
      drawer.hidden = false;
      drawer.setAttribute('aria-hidden', 'false');
      setModalContentHidden(true, drawer);
      setBodyLocked(true);
      document.removeEventListener('keydown', handleKeydown);
      document.addEventListener('keydown', handleKeydown);
      closeButton && closeButton.focus();
    }
    function closeDrawer() {
      drawer.hidden = true;
      drawer.setAttribute('aria-hidden', 'true');
      setBodyLocked(false);
      setModalContentHidden(false, null);
      document.removeEventListener('keydown', handleKeydown);
      activeTrigger && activeTrigger.focus();
      activeTrigger = null;
    }
    document.querySelectorAll('[data-insight-trigger]').forEach(trigger => {
      trigger.addEventListener('click', () => open(trigger));
    });
    closeButton && closeButton.addEventListener('click', closeDrawer);
    drawer.addEventListener('click', event => {
      if (event.target === drawer) {
        closeDrawer();
      }
    });
    document.addEventListener('report-language-change', () => {
      if (activeTrigger && !drawer.hidden) {
        render(activeTrigger);
      }
    });
  }
  document.querySelectorAll('[data-set-lang]').forEach(btn => {
    btn.addEventListener('click', () => setLang(btn.dataset.setLang));
  });
  setLang(initial, { forceText: initial !== generated, silent: true });
  runAfterFirstPaint(() => {
    initCandidateMasterDetail();
    initInsightDrawer();
    root.dataset.uiReady = 'true';
  });
})();
"""
if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli
    fail_not_cli(__file__)
