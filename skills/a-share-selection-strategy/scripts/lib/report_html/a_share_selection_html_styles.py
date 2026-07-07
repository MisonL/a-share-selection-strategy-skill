"""CSS styles for the local A-share HTML report."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)


CSS = """
:root{color-scheme:light;--bg:#f8fafc;--surface:#fff;--ink:#111d2f;--text:#243247;--muted:#637083;--line:#d8e0ea;--line-strong:#c5d0dd;--soft:#f7fafc;--green:#0a8f63;--green-dark:#047857;--blue:#1b75d0;--orange:#d97706;--red:#c73535;--surface-highlight:inset 0 1px 0 rgba(255,255,255,.82);--hairline:0 0 0 1px rgba(15,23,42,.075);--hairline-soft:0 0 0 1px rgba(15,23,42,.055);--hairline-blue:0 0 0 1px rgba(27,117,208,.18);--hairline-green:0 0 0 1px rgba(10,143,99,.18);--hairline-warn:0 0 0 1px rgba(217,119,6,.2);--hairline-danger:0 0 0 1px rgba(199,53,53,.18);--control-shadow:var(--hairline-soft),var(--surface-highlight),0 3px 9px rgba(15,23,42,.035);--shadow:var(--hairline),var(--surface-highlight),0 10px 26px rgba(15,23,42,.06);--shadow-soft:var(--hairline-soft),var(--surface-highlight),0 14px 34px rgba(15,23,42,.075);--shadow-float:var(--hairline),var(--surface-highlight),0 24px 64px rgba(15,23,42,.22)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
	body{margin:0;max-width:100%;overflow-x:hidden;background:linear-gradient(180deg,#fbfdff 0,#f8fafc 340px,#f8fafc 100%);color:var(--text);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
		.page{width:min(2048px,calc(100% - 40px));margin:0 auto;padding:8px 0 20px}
h1,h2,h3,h4,p{margin:0}h2{font-size:21px;line-height:1.25;color:var(--ink)}h3{font-size:20px;line-height:1.25;color:var(--ink)}
.section,.panel-card{background:var(--surface);border:0;border-radius:8px;box-shadow:var(--shadow)}
	.hero-copy h1{font-family:Georgia,"Times New Roman","Songti SC",serif;font-size:56px;line-height:.96;letter-spacing:0;color:#101b2d}
	.hero-badges{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
	.hero-badge{display:inline-flex;align-items:center;min-height:30px;border:0;border-radius:6px;background:#fff;color:#26384f;font-weight:800;padding:5px 13px;box-shadow:var(--hairline-soft)}
.hero-badge.ok{color:#047857;background:#f5fbf8;box-shadow:var(--hairline-green),var(--surface-highlight)}.hero-badge.blue{color:#1b65b8;background:#f5f9ff;box-shadow:var(--hairline-blue),var(--surface-highlight)}.hero-badge.warn{color:#a15c00;background:#fff9ee;box-shadow:var(--hairline-warn),var(--surface-highlight)}.hero-badge.purple{color:#5f43a6;background:#faf7ff;box-shadow:0 0 0 1px rgba(95,67,166,.16),var(--surface-highlight)}.hero-badge.danger{color:#b42318;background:#fff7f6;box-shadow:var(--hairline-danger),var(--surface-highlight)}
.hero-note{display:flex;align-items:center;gap:8px;margin-top:9px;color:#334155;font-size:14px}
.hero-note::before{content:"i";display:inline-grid;place-items:center;width:18px;height:18px;border:1px solid #64748b;border-radius:50%;font-size:12px;font-weight:900;color:#334155}
	.hero-machine-note{margin:0;border:0;border-left:4px solid #1b75d0;border-radius:8px;background:#f8fbff;padding:11px 12px;color:#334155;font-size:13px;line-height:1.5;overflow-wrap:anywhere;box-shadow:var(--hairline-blue),var(--surface-highlight),0 8px 18px rgba(15,23,42,.045)}
.hero-machine-note strong{color:#102033}
.field-coverage-card{display:grid;gap:12px;margin:10px 0 12px;border:0;border-radius:8px;background:linear-gradient(180deg,#fbfdff 0,#f7fbff 100%);padding:12px 14px;box-shadow:var(--hairline-blue),var(--surface-highlight),0 8px 18px rgba(15,23,42,.045)}
.field-coverage-head{display:grid;gap:4px}.field-coverage-head strong{color:var(--ink);font-size:15px;line-height:1.2}.field-coverage-head p{color:var(--muted);font-size:12px;line-height:1.45}
.field-coverage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}
.field-coverage-chip{display:grid;gap:3px;min-width:0;border:0;border-radius:8px;background:#fff;padding:10px 11px;box-shadow:var(--hairline-soft),0 3px 10px rgba(15,23,42,.032)}
.field-coverage-chip span{color:var(--muted);font-size:12px;font-weight:800}
.field-coverage-chip strong{color:var(--ink);font-size:15px;line-height:1.2}
.field-coverage-chip b{color:#0b8f63;font-size:12px;line-height:1.2}
.field-coverage-chip[data-field-missing="true"]{background:#fffaf2;box-shadow:var(--hairline-warn),var(--surface-highlight),0 3px 10px rgba(217,119,6,.045)}
.field-coverage-chip[data-field-missing="true"] b{color:#a15c00}
.hero-fact-card{position:relative;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 14px;width:100%;min-height:112px;border:0;border-radius:8px;background:#fff;padding:10px 16px;box-shadow:var(--shadow-soft)}
.hero-fact-card::after{display:none}
.hero-fact-card div{position:relative;display:grid;grid-template-columns:86px minmax(0,1fr);gap:10px;min-width:0;padding:2px 0 2px 22px}
.hero-fact-card div::before{content:"";position:absolute;left:0;top:6px;width:13px;height:13px;border:1px solid #9aa8b7;border-radius:3px;background:linear-gradient(#9aa8b7,#9aa8b7) 3px 3px/7px 1px no-repeat,linear-gradient(#9aa8b7,#9aa8b7) 3px 7px/7px 1px no-repeat,#fff}
.hero-fact-card span{min-width:0;color:#526173;font-size:13px;font-weight:800;overflow-wrap:anywhere}.hero-fact-card strong{min-width:0;color:#1e293b;font-weight:800;overflow-wrap:anywhere}
.section{margin-top:8px;padding:10px}.section>h2{display:flex;align-items:center;gap:10px;margin-bottom:14px}.section>h2::before{content:"";display:block;width:6px;height:22px;border-radius:5px;background:var(--green)}
.dashboard-section,.watchlist-section{padding:0;background:transparent;border:0;box-shadow:none}
	.overview-shell{display:grid;grid-template-columns:minmax(0,1fr) minmax(520px,1fr);grid-template-areas:"lead facts" "preview flow" "open open";gap:12px;align-items:start}
	.overview-lead,.overview-title,.overview-facts,.overview-metrics,.overview-flow,.overview-preview,.overview-open{min-width:0}
	.overview-lead{grid-area:lead;display:grid;gap:12px}.overview-facts{grid-area:facts;display:grid;gap:12px}.overview-flow{grid-area:flow}.overview-preview{grid-area:preview}.overview-open{grid-area:open}
button.pipeline-card,button.flow-step{font:inherit;color:inherit;cursor:pointer}
.pipeline-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;align-items:stretch;border:0;border-radius:8px;background:#fff;overflow:hidden;box-shadow:var(--shadow)}
		.pipeline-card{display:grid;grid-template-columns:54px minmax(0,1fr);gap:14px;align-items:center;min-height:74px;border:0;border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:8px 18px;background:#fff;text-align:left}
.pipeline-card:nth-child(2n){border-right:0}.pipeline-card:nth-last-child(-n+2){border-bottom:0}
.pipeline-card:hover,.pipeline-card:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f8fcff;box-shadow:inset 0 0 0 2px #9cc7ee}.pipeline-card:active{background:#f2f8ff}
	.pipeline-icon{position:relative;width:48px;height:48px;border-radius:50%;background:#13a266;box-shadow:inset 0 -8px 16px rgba(0,0,0,.08)}
.pipeline-icon::before,.pipeline-icon::after{content:"";position:absolute;left:50%;top:50%;background:#fff;transform:translate(-50%,-50%)}.pipeline-icon::before{width:50%;height:42%;clip-path:polygon(0 0,100% 0,64% 45%,64% 100%,36% 100%,36% 45%)}.pipeline-icon::after{display:none}
.pipeline-icon.circle::before{width:10px;height:10px;border-radius:50%;box-shadow:-11px 0 0 #fff,11px 0 0 #fff,0 15px 0 5px #fff;clip-path:none;transform:translate(-50%,-72%)}.pipeline-icon.eye::before{width:30px;height:20px;border:4px solid #fff;border-radius:50%;background:transparent;clip-path:none}.pipeline-icon.eye::after{display:block;width:6px;height:6px;border-radius:50%;background:#fff}.pipeline-icon.shield::before{width:46%;height:58%;background:#fff;clip-path:polygon(50% 0,88% 14%,80% 70%,50% 100%,20% 70%,12% 14%)}.pipeline-icon.shield::after{display:block;width:4px;height:10px;border-radius:2px;background:#f59e0b;box-shadow:0 14px 0 -1px #f59e0b;transform:translate(-50%,-61%)}
.pipeline-card.input .pipeline-icon{background:#1f7eea}.pipeline-card.passed .pipeline-icon{background:#12a36f}.pipeline-card.watch .pipeline-icon{background:#1e88e5}.pipeline-card.risk .pipeline-icon{background:#f59e0b}.pipeline-copy{display:grid;grid-template-columns:minmax(0,max-content) minmax(0,max-content) minmax(0,1fr);align-items:center;column-gap:10px;min-width:0}.pipeline-copy>span{display:block;color:#174034;font-size:16px;font-weight:900;line-height:1;white-space:nowrap}
.pipeline-card.passed .pipeline-copy>span{color:#174a82}.pipeline-card.watch .pipeline-copy>span{color:#7a4300}.pipeline-card.risk .pipeline-copy>span{color:#991b1b}.pipeline-card strong{display:block;color:#111827;font-size:30px;line-height:1;letter-spacing:0;font-variant-numeric:tabular-nums}.pipeline-card small{display:block;min-width:0;color:#475569;font-size:13px;line-height:1.1;white-space:normal;overflow-wrap:anywhere}
.selection-flow-card{border:0;border-radius:8px;background:#fff;padding:9px 20px;box-shadow:var(--shadow)}
.selection-flow-card h2{display:flex;align-items:baseline;gap:8px;margin-bottom:7px}.selection-flow-card h2 span{color:#667085;font-size:15px;font-weight:600}
.selection-flow{display:grid;grid-template-columns:minmax(0,1fr) 36px minmax(0,1fr) 36px minmax(0,1fr) 36px minmax(0,1fr);align-items:center;gap:10px;min-width:0}
.flow-step{display:grid;justify-items:center;min-width:0;border:0;border-radius:8px;background:transparent;color:#1e293b;text-align:center;padding:8px 8px;overflow-wrap:anywhere}
.flow-step:hover,.flow-step:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f8fbff;box-shadow:0 0 0 2px #bfdbfe}.flow-step:active{background:#eef6ff}
	.flow-index{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;background:#1b75d0;color:#fff;font-size:19px;font-weight:900}
.flow-step.input .flow-index{background:#1b75d0}.flow-step.passed .flow-index{background:#0b8f63}.flow-step.watch .flow-index{background:#1b75d0}.flow-step.risk .flow-index{background:#f08a00}
.flow-step span:not(.flow-index){display:block;min-width:0;margin-top:7px;color:#0f172a;font-weight:900;line-height:1.2;overflow-wrap:anywhere}
.flow-step strong{display:block;margin-top:2px;color:#334155;font-weight:700}
.flow-step small{display:block;min-width:0;margin-top:1px;color:#64748b;font-size:12px;line-height:1.2;overflow-wrap:anywhere}
.flow-arrow{width:100%;min-width:18px;height:2px;background:#64748b;position:relative}
.flow-arrow::after{content:"";position:absolute;right:-1px;top:-5px;width:11px;height:11px;border-top:2px solid #64748b;border-right:2px solid #64748b;transform:rotate(45deg)}
.insight-drawer[hidden]{display:none}.insight-drawer{position:fixed;inset:0;z-index:80;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.45);contain:layout paint}
.insight-dialog{position:relative;width:min(580px,100%);max-height:min(720px,calc(100vh - 48px));overflow:auto;border:0;border-radius:8px;background:#fff;padding:20px 22px 18px;box-shadow:var(--shadow-float);contain:content}
.insight-close{position:absolute;right:14px;top:14px;min-height:34px;border:0;border-radius:6px;background:#fff;color:#1e293b;font:inherit;font-weight:800;padding:5px 12px;cursor:pointer;box-shadow:var(--control-shadow)}.insight-close:hover,.insight-close:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f7fbff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.055)}
.insight-eyebrow{display:inline-flex;align-items:center;min-height:26px;border:0;border-radius:6px;background:#f8fbff;color:#175cd3;font-size:12px;font-weight:900;padding:3px 9px;box-shadow:var(--hairline-blue)}
.insight-dialog h3{margin-top:14px;padding-right:74px}.insight-summary{margin-top:8px;color:#475569;line-height:1.55}.insight-facts{display:grid;grid-template-columns:minmax(140px,190px) minmax(0,1fr);gap:8px 14px;margin:16px 0 0;padding-top:14px;border-top:1px solid var(--line)}
.insight-facts dt{color:#526173;font-size:12px;font-weight:900}.insight-facts dd{margin:0;min-width:0;color:#172033;font-weight:800;overflow-wrap:anywhere}
.insight-actions{display:grid;gap:7px;margin:16px 0 0;padding:13px 16px 13px 30px;border:0;border-radius:8px;background:#f5fbf8;color:#205044;box-shadow:var(--hairline-green),var(--surface-highlight),0 4px 12px rgba(10,143,99,.035)}
.metrics,.note-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.metric,.note-card{border:0;border-radius:8px;padding:16px;background:#fff;box-shadow:var(--hairline-soft),0 4px 12px rgba(15,23,42,.035)}
.metric>span,.facts dt,.note-card .note-label{color:var(--muted);font-size:12px;font-weight:800}
.metric strong{display:block;margin-top:7px;color:var(--ink);font-size:28px;line-height:1}
.note-card strong{display:block;margin-top:7px;color:var(--ink);font-size:17px}
.limit-panel{margin-top:14px;border:0;border-left:5px solid var(--green);border-radius:8px;padding:16px 18px;background:#f5fbf8;box-shadow:var(--hairline-green),var(--surface-highlight),0 4px 12px rgba(10,143,99,.035)}
.limit-panel strong{display:block;margin-bottom:4px}.limit-panel p{color:var(--muted)}
	.disclosure-alerts{margin:8px 0 0;padding:0;list-style:none;display:grid;gap:6px}
	.disclosure-alerts li{border:0;border-left:5px solid var(--orange);border-radius:8px;background:#fff8ed;padding:8px 12px;color:#6c3d00;font-size:14px;box-shadow:var(--hairline-warn)}
.boundary{margin-top:14px;color:var(--muted);overflow-wrap:anywhere}
.technical-details,.report-details{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.technical-details summary,.report-details summary{cursor:pointer;color:var(--muted);font-weight:700}
.technical-details summary{display:inline-flex;align-items:center;gap:8px;width:max-content;max-width:100%;min-height:34px;border:0;border-radius:8px;background:#fff;color:var(--green-dark);padding:8px 12px;box-shadow:var(--control-shadow)}
.technical-details summary::marker{content:""}.technical-details summary::-webkit-details-marker{display:none}
.report-details summary{width:max-content;max-width:100%;border:0;border-radius:8px;background:#fff;padding:9px 12px;color:var(--green-dark);box-shadow:var(--control-shadow)}
.technical-details[open] summary,.report-details[open] summary{margin-bottom:12px}
.technical-details summary::after{content:">";margin-left:2px;color:#0b8f63;font-size:12px;line-height:1;transition:transform .18s ease}
.technical-details[open] summary::after{transform:rotate(90deg)}
.technical-details summary span{display:block;font-size:12px;font-weight:400;color:#64748b}
.report-note,.diagnostic-intro{color:var(--muted);margin-bottom:12px}
.facts{display:grid;grid-template-columns:minmax(170px,230px) 1fr;gap:10px 18px;margin:14px 0}
.facts dt{overflow-wrap:anywhere}.facts dd{margin:0;min-width:0;overflow-wrap:anywhere}
.empty{color:var(--muted)}
.watchlist-preview-pane{min-width:0;border:0;border-radius:8px;background:#fff;padding:11px;box-shadow:var(--shadow)}
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
			.candidate-open-banner{display:grid;grid-template-columns:max-content minmax(0,1fr) max-content;grid-template-areas:"title body button" "foot foot button";gap:5px 16px;align-items:center;justify-items:start;width:100%;min-height:0;border:0;border-radius:8px;background:linear-gradient(180deg,#fbfffd 0,#f2fbf6 100%);padding:14px 18px;color:#1e293b;text-align:left;text-decoration:none;box-shadow:var(--hairline-green),var(--surface-highlight),0 6px 16px rgba(10,143,99,.07)}
.candidate-open-banner:hover,.candidate-open-banner:focus-visible{outline:2px solid #0a8f63;outline-offset:2px;background:linear-gradient(180deg,#f4fbf7 0,#e9f8f1 100%);box-shadow:inset 0 0 0 2px rgba(10,143,99,.16)}
	.candidate-open-title{grid-area:title;position:relative;display:inline-flex;align-items:center;gap:8px;color:var(--green-dark);font-size:18px;line-height:1.2;font-weight:900;white-space:nowrap}.candidate-open-title::before{content:"";width:18px;height:20px;border:2px solid var(--green);border-radius:3px;background:linear-gradient(var(--green),var(--green)) 5px 5px/7px 2px no-repeat,linear-gradient(var(--green),var(--green)) 5px 10px/7px 2px no-repeat,linear-gradient(var(--green),var(--green)) 5px 15px/7px 2px no-repeat}
	.candidate-open-body{grid-area:body;max-width:100%;min-width:0;color:#475569;font-size:13px;line-height:1.45;overflow-wrap:anywhere}.candidate-open-button{grid-area:button;display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:0;border-radius:7px;background:#fff;color:#1e293b;font-weight:800;padding:7px 18px;box-shadow:var(--control-shadow);white-space:nowrap}
	.candidate-open-foot{grid-area:foot;position:relative;color:#334155;font-size:12px;font-weight:700;text-align:left;width:100%;padding-bottom:0}.candidate-open-foot::after{display:none}
		.candidate-master-detail{margin-top:8px;max-width:100%;overflow:hidden;border:0;border-radius:8px;background:#fff;padding:10px;box-shadow:var(--shadow);scroll-margin-top:18px}
		.master-detail-header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:10px}
	.master-detail-header h3{font-size:20px}.master-detail-header p{margin-top:4px;max-width:760px;color:var(--muted);font-size:13px;line-height:1.35}
.candidate-file-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.file-chip{display:inline-block;border:0;border-radius:7px;background:#f4fbf8;padding:6px 11px;color:var(--green-dark);box-shadow:var(--hairline-green)}
.candidate-download-link{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:0;border-radius:7px;background:#047857;color:#fff;font-weight:900;padding:7px 14px;text-decoration:none;box-shadow:0 0 0 1px rgba(4,120,87,.28),0 4px 12px rgba(10,143,99,.15)}
.candidate-download-link:hover,.candidate-download-link:focus-visible{outline:2px solid #0a8f63;outline-offset:2px;background:#065f46;box-shadow:inset 0 0 0 1px rgba(255,255,255,.18),0 0 0 3px rgba(10,143,99,.16)}
.field-notice{margin:-2px 0 9px;border:0;border-left:5px solid var(--orange);border-radius:8px;background:#fffaf0;padding:8px 12px;color:#6c3d00;font-size:13px;line-height:1.4;box-shadow:var(--hairline-warn)}
.candidate-toolbar{display:grid;grid-template-columns:2fr repeat(3,minmax(130px,1fr)) max-content;gap:9px;margin-bottom:7px;align-items:end}
.candidate-toolbar.has-industry{grid-template-columns:2fr repeat(4,minmax(130px,1fr)) max-content}
.candidate-toolbar label{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;font-weight:800}
.candidate-toolbar label span{white-space:nowrap}
.candidate-toolbar label input,.candidate-toolbar label select{flex:1;min-width:0}
.candidate-toolbar input,.candidate-toolbar select{width:100%;height:40px;border:0;border-radius:7px;background:#fff;color:var(--ink);font:inherit;padding:7px 10px;box-shadow:var(--control-shadow)}
.candidate-toolbar button{height:40px;min-width:82px;border:0;border-radius:7px;background:#fff;color:#64748b;font:inherit;padding:7px 14px;cursor:pointer;box-shadow:var(--control-shadow)}
.candidate-toolbar input:focus-visible,.candidate-toolbar select:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f7fbff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.055)}
.candidate-toolbar button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f7fbff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.055)}
.candidate-toolbar-status{min-height:20px;margin:-2px 0 7px;color:#0f766e;font-size:12px;font-weight:750;line-height:1.35}
		.master-detail-grid{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(420px,.88fr);gap:12px;align-items:start}
.master-list-panel{min-width:0;max-width:100%;overflow:clip}
.candidate-detail-panel{position:sticky;top:12px}
.detail-head-copy{display:grid;gap:4px;min-width:0}
.detail-head-note{color:#64748b;font-size:12px;font-weight:700;line-height:1.35}
			.master-table{max-height:420px;overflow:auto;border:0;border-radius:8px;background:#fff;contain:content;box-shadow:var(--hairline-soft)}
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
.risk-badge.notice{background:#ecfdf3;color:#067647;box-shadow:var(--hairline-green)}
.risk-badge.attention{background:#fffaeb;color:#b54708;box-shadow:var(--hairline-warn)}
.risk-badge.high{background:#fef3f2;color:#b42318;box-shadow:var(--hairline-danger)}
		.candidate-detail-panel{align-self:stretch;height:100%;max-height:560px;border:0;border-radius:8px;background:#fff;min-width:0;overflow:auto;box-shadow:var(--shadow);contain:content;scrollbar-gutter:stable}
.stock-detail-drawer[hidden]{display:none}.stock-detail-drawer{position:fixed;inset:0;z-index:90;display:grid;place-items:center;padding:20px;background:rgba(15,23,42,.58);backdrop-filter:blur(8px);contain:layout paint}
.stock-dialog{width:min(1120px,100%);max-height:min(92vh,920px);overflow:auto;border:0;border-radius:10px;background:linear-gradient(180deg,#fff 0,#fbfdff 100%);box-shadow:var(--shadow-float);contain:content;scrollbar-gutter:stable}
		.stock-dialog-head{position:sticky;top:0;z-index:3;display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:18px 20px 14px;border-bottom:1px solid #e3eaf2;background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(250,252,255,.96))}.stock-dialog-head > div{min-width:0;max-width:100%}
	.stock-dialog-head h3{margin-top:4px;font-size:22px;line-height:1.15;overflow-wrap:anywhere}.stock-dialog-head p{display:flex;flex-wrap:wrap;gap:12px;margin-top:6px;color:var(--muted);font-size:13px;overflow-wrap:anywhere}
	.stock-dialog-eyebrow{display:inline-flex;align-items:center;min-height:26px;border:0;border-radius:6px;background:#f5fbf8;color:#0b8f63;font-size:12px;font-weight:900;padding:3px 9px;box-shadow:var(--hairline-green)}
		.stock-dialog-close{min-height:44px;border:0;border-radius:7px;background:#fff;color:#1e293b;font:inherit;font-weight:800;padding:7px 16px;cursor:pointer;box-shadow:var(--control-shadow)}
	.stock-dialog-close:hover,.stock-dialog-close:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f7fbff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.055)}
		.stock-dialog-grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(360px,.95fr);gap:14px;padding:14px;align-items:start}
	.stock-chart-panel,.stock-facts-panel{border:0;border-radius:9px;background:#fff;min-width:0;box-shadow:var(--shadow-soft)}
	.stock-chart-panel{display:grid;gap:10px;padding:14px;background:linear-gradient(180deg,#fff 0,#f9fbfd 100%);min-height:0}
	.stock-chart-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;color:#1e293b}.stock-chart-head strong{display:block;font-size:16px}.stock-chart-head span{display:block;color:var(--muted);font-size:12px;margin-top:3px}
	.stock-chart-head [data-stock-field="candle-count"]{display:inline-flex;align-items:center;min-height:28px;border:0;border-radius:6px;background:#f5fbf8;color:#0b8f63;font-weight:800;padding:2px 10px;box-shadow:var(--hairline-green)}
.stock-chart-wrap{position:relative;min-height:380px;aspect-ratio:16/11;border:0;border-radius:9px;background:#fff;overflow:hidden;contain:content;max-width:100%;width:100%;box-shadow:var(--hairline-soft)}
.stock-chart-wrap canvas{display:block;width:100%;height:100%;touch-action:none}
	.stock-chart-empty{position:absolute;inset:0;display:grid;place-items:center;padding:18px;color:var(--muted);text-align:center;white-space:pre-line}
		.stock-chart-tooltip{position:absolute;z-index:2;display:grid;gap:3px;width:210px;max-width:calc(100% - 20px);border:0;border-radius:8px;background:rgba(255,255,255,.98);box-shadow:var(--hairline-green),var(--surface-highlight),0 12px 28px rgba(15,23,42,.16);padding:8px 10px;color:#1e293b;font-size:12px;line-height:1.35;pointer-events:none;transform:none}
	.stock-chart-tooltip strong{font-size:13px;line-height:1.25;color:#0f172a}
	.stock-chart-tooltip span{display:block;color:#475569}
	.stock-chart-note{color:#64748b;font-size:12px;line-height:1.45}
	.stock-facts-panel{display:grid;align-content:start;gap:12px;padding:14px;background:#f8fafc;min-width:0;max-width:100%;width:100%}
	.stock-panel-section{display:grid;gap:10px;min-width:0;border:0;border-radius:9px;background:#fff;padding:12px;box-shadow:var(--hairline-soft),0 4px 12px rgba(15,23,42,.035)}
	.stock-panel-title{display:flex;align-items:center;gap:8px;color:#1e293b;font-size:13px;line-height:1.25;font-weight:900}
	.stock-panel-title::before{content:"";width:4px;height:16px;border-radius:3px;background:#1b75d0}
	.stock-action-section{background:#f8fbff;box-shadow:var(--hairline-blue),var(--surface-highlight),0 4px 12px rgba(27,117,208,.045)}
	.stock-action-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
	.stock-action-grid button{min-height:40px;border:0;border-radius:7px;background:#fff;color:#1e293b;font:inherit;font-size:13px;font-weight:850;padding:8px 10px;cursor:pointer;box-shadow:var(--control-shadow)}
	.stock-action-grid button:hover,.stock-action-grid button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#eef7ff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.055)}
	.stock-action-status{min-height:18px;color:#0b8f63;font-size:12px;font-weight:800}
	.stock-next-section{background:#fff;box-shadow:var(--hairline-blue),var(--surface-highlight),0 4px 12px rgba(27,117,208,.035)}
	.stock-next-list{display:grid;gap:6px;margin:0;padding-left:20px;color:#334155;font-size:13px;line-height:1.45}
	.stock-fact-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
	.stock-fact-grid.secondary{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
	.stock-fact-grid div,.stock-text-section{border:0;border-radius:8px;background:#fff;padding:11px 12px;box-shadow:var(--hairline-soft),0 3px 10px rgba(15,23,42,.026)}
	.stock-fact-grid.secondary div{background:#fbfdff;box-shadow:var(--hairline-soft)}
	.stock-fact-grid span,.stock-text-section span{display:block;color:var(--muted);font-size:12px;font-weight:800}
	.stock-fact-grid strong{display:block;margin-top:6px;color:var(--ink);font-size:16px;line-height:1.2;word-break:break-all}
	.stock-fact-grid.primary strong{font-size:17px}
	.stock-fact-grid.secondary strong{font-size:14px;color:#334155}
	.stock-tech-summary{border:0;border-radius:8px;background:#f8fbff;padding:10px 12px;color:#1e293b;font-size:13px;line-height:1.45;font-weight:750;box-shadow:var(--hairline-blue)}
.stock-technical-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
	.stock-tech-card{display:grid;gap:5px;min-width:0;border:0;border-left:4px solid #d6e0eb;border-radius:8px;background:#fff;padding:10px 11px;box-shadow:var(--hairline-soft)}
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
	.stock-text-section.summary,.stock-text-section.reason{box-shadow:var(--hairline-blue),var(--surface-highlight),0 3px 10px rgba(27,117,208,.025)}
	.stock-text-section.risk{background:#fff7f6;box-shadow:var(--hairline-danger),var(--surface-highlight),0 3px 10px rgba(199,53,53,.025)}
	.stock-text-section.action{background:#f8fbff;box-shadow:var(--hairline-blue),var(--surface-highlight),0 3px 10px rgba(27,117,208,.025)}
	.stock-text-section.evidence{background:#fbfdff}
	.stock-text-section.evidence p{font-variant-numeric:tabular-nums}
			.detail-head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding:11px 14px 9px}
		.detail-head h3{font-size:21px}.detail-head span{color:var(--muted);font-weight:700}.detail-head b{color:#334155}
.detail-action-button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;border:0;border-radius:7px;background:#fff;color:#1e293b;font:inherit;font-size:13px;font-weight:850;padding:8px 12px;cursor:pointer;box-shadow:var(--control-shadow)}
.detail-action-button:hover,.detail-action-button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#eef7ff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.055)}
	.detail-body{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(220px,.92fr);min-height:0}
	.detail-main{min-width:0;border-right:1px solid var(--line)}
	.detail-main .detail-grid:last-child{border-bottom:0}
	.detail-evidence-card{display:grid;align-content:start;gap:9px;padding:12px 14px;background:#f8fafc;border-left:1px solid #e7edf4}
	.detail-evidence-card span{color:#1e293b;font-weight:900;font-size:13px;line-height:1.35}
.detail-evidence-card p{margin:0;border:0;border-radius:7px;background:#fff;padding:11px 12px;color:var(--text);line-height:1.62;white-space:pre-line;word-break:break-word;box-shadow:var(--hairline-soft),0 3px 10px rgba(15,23,42,.03)}
	.detail-grid{display:grid;grid-template-columns:146px 1fr;border-bottom:1px solid #e7edf4}
	.detail-grid:last-child{border-bottom:0}
		.detail-grid>span{display:flex;align-items:center;gap:8px;background:#fbfdff;color:#1e293b;font-weight:900;padding:9px 12px;border-right:1px solid #e7edf4;font-size:13px;line-height:1.35}
		.detail-grid p{min-width:0;padding:9px 12px;color:var(--text);line-height:1.5}
	.master-table-footer{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:8px;color:#475569}
.candidate-pager{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.candidate-pager button,.candidate-pager select{min-height:40px;border:0;border-radius:7px;background:#fff;color:#1e293b;font:inherit;padding:7px 12px;box-shadow:var(--control-shadow)}
.candidate-pager button{cursor:pointer}.candidate-pager button:not(:disabled):hover,.candidate-pager button:not(:disabled):focus-visible{outline:2px solid #1b75d0;outline-offset:2px;background:#f7fbff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.055)}.candidate-pager button:disabled{opacity:.48;cursor:not-allowed;box-shadow:none}
.candidate-page-numbers{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}.candidate-page-number{min-width:44px;min-height:44px;border:0;border-radius:7px;background:#fff;color:#1e293b;font:inherit;box-shadow:var(--control-shadow);cursor:pointer}.candidate-page-number.active{background:#1b75d0;color:#fff;box-shadow:var(--hairline-blue),0 4px 12px rgba(27,117,208,.16)}.candidate-page-ellipsis{color:#64748b;padding:0 2px}.candidate-page-status{color:#334155}
	.final-notice-grid{display:grid;grid-template-columns:.88fr 1fr;gap:16px}
			.result-notice-card,.disclaimer-card{min-height:112px;display:grid;grid-template-columns:1fr;gap:12px;align-items:center;border:0;border-radius:8px;background:#fff;padding:18px 22px}
.result-notice-card{background:#fffaf2;box-shadow:var(--hairline-warn),var(--surface-highlight),0 8px 20px rgba(217,119,6,.075)}.disclaimer-card{background:#f8fbff;box-shadow:var(--hairline-blue),var(--surface-highlight),0 8px 20px rgba(27,117,208,.075)}
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
@media(max-width:1500px){.overview-shell{grid-template-columns:minmax(0,1fr) minmax(420px,.9fr)}.selection-flow{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.flow-arrow{display:none}.master-detail-grid{grid-template-columns:minmax(0,1fr) minmax(420px,.82fr)}.candidate-detail-panel .detail-body{grid-template-columns:1fr}.candidate-detail-panel .detail-main{border-right:0;border-bottom:1px solid var(--line)}.candidate-detail-panel .detail-evidence-card{border-left:0;border-top:1px solid #e7edf4}}
@media(max-width:1280px){.overview-shell,.final-notice-grid{grid-template-columns:minmax(0,1fr)}.overview-shell{grid-template-areas:"lead" "facts" "flow" "preview" "open"}.hero-copy,.overview-lead,.overview-title,.overview-facts,.overview-metrics,.overview-flow,.overview-preview,.overview-open{min-width:0}.selection-flow{grid-template-columns:repeat(4,1fr);gap:12px}.flow-arrow{display:none}.candidate-open-banner{min-height:150px}.master-detail-grid{grid-template-columns:minmax(0,1fr) minmax(360px,.8fr)}.candidate-detail-panel{max-height:520px;position:relative;top:auto}.hero-fact-card{max-width:100%;min-width:0}.hero-machine-note{font-size:12px}.master-table{max-height:52vh}}
@media(max-width:1100px){.candidate-toolbar{grid-template-columns:repeat(2,minmax(0,1fr))}.candidate-toolbar label:first-child{grid-column:1/-1}.candidate-toolbar button{align-self:end}.master-detail-grid{grid-template-columns:1fr}.candidate-detail-panel{max-height:none}.detail-body{grid-template-columns:1fr}.detail-main{border-right:0;border-bottom:1px solid var(--line)}.detail-evidence-card{border-left:0;border-top:1px solid #e7edf4}.master-table-footer{display:grid;grid-template-columns:1fr;align-items:start}.candidate-pager{margin-top:8px}.field-coverage-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:900px){.page{width:min(100% - 20px,1200px);padding-top:10px}.hero-copy h1{font-size:34px;line-height:1}.hero-badges{gap:8px}.hero-badge{min-height:34px;padding:5px 11px}.hero-note{margin-top:7px}.hero-fact-card{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;min-height:0;padding:8px 14px}.hero-fact-card div{grid-template-columns:78px minmax(0,1fr);gap:8px;padding:4px 8px 4px 20px}.hero-fact-card::after{display:none}.pipeline-card{grid-template-columns:44px minmax(0,1fr);justify-content:normal;gap:12px;min-height:66px;padding:9px 14px}.pipeline-icon{width:40px;height:40px}.pipeline-icon.circle::before{width:8px;height:8px;box-shadow:-9px 0 0 #fff,9px 0 0 #fff,0 12px 0 4px #fff}.pipeline-icon.eye::before{width:25px;height:17px;border-width:3px}.pipeline-icon.shield::after{height:8px;box-shadow:0 11px 0 -1px #f59e0b}.selection-flow-card{padding:9px 14px}.selection-flow{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.flow-step{min-width:0}.flow-index{width:32px;height:32px;font-size:17px}.flow-step span:not(.flow-index){margin-top:5px}.flow-step strong{font-size:13px}.flow-step small{font-size:11px}.candidate-toolbar{grid-template-columns:1fr}.master-detail-header,.detail-table-heading,.preview-heading,.master-table-footer{display:block}.facts,.evidence li,.detail-grid{grid-template-columns:1fr}.detail-grid>span{border-right:0;border-bottom:1px solid var(--line)}.field-coverage-grid{grid-template-columns:1fr}.section{padding:14px}}
@media(max-width:640px){body{font-size:14px;line-height:1.5}.page{width:min(100% - 16px,1200px);padding:8px 0 16px}.hero-copy h1{font-size:32px;line-height:1.02}.hero-badges{gap:8px}.hero-badge{flex:1 1 calc(50% - 8px);justify-content:center;min-width:0;min-height:36px;overflow-wrap:anywhere}.hero-note{align-items:flex-start;max-width:100%;overflow-wrap:anywhere}.hero-fact-card{padding:8px 10px}.hero-fact-card div{grid-template-columns:minmax(0,1fr);min-width:0;gap:2px;padding:5px 8px 5px 18px}.hero-fact-card span,.hero-fact-card strong{min-width:0;overflow-wrap:anywhere}.hero-machine-note{padding:9px 10px;font-size:12px}.pipeline-card{min-height:72px;padding:9px 10px}.pipeline-copy{grid-template-columns:max-content max-content;grid-template-areas:"label value" "note note";align-items:center;column-gap:6px;row-gap:3px}.pipeline-copy>span{grid-area:label;font-size:15px}.pipeline-copy>strong{grid-area:value}.pipeline-card strong{font-size:25px}.pipeline-card small{grid-area:note;font-size:12px;line-height:1.2}.insight-drawer{place-items:end center;padding:12px}.insight-dialog{width:100%;max-height:calc(100vh - 24px);padding:18px 16px}.insight-close{min-width:44px;min-height:44px}.insight-dialog h3{padding-right:70px}.insight-facts{grid-template-columns:1fr;gap:3px}.candidate-file-actions{display:grid;grid-template-columns:1fr;justify-content:stretch;width:100%}.candidate-download-link{min-height:44px}.candidate-toolbar,.candidate-toolbar.has-industry{grid-template-columns:1fr}.candidate-toolbar label{display:grid;gap:5px}.candidate-toolbar label span{white-space:normal}.candidate-toolbar input,.candidate-toolbar select,.candidate-toolbar button,.candidate-pager button,.candidate-pager select{min-height:44px}.candidate-cards[data-preview-table] th,.candidate-cards[data-preview-table] td{padding:8px}.candidate-master-detail{padding:8px}.master-table{max-height:58vh}.master-table table{min-width:860px}.candidate-detail-panel{box-shadow:var(--hairline-soft);position:relative;top:auto}.detail-head{gap:8px}.detail-head h3{font-size:19px}.detail-grid p,.detail-grid>span{padding:10px}.candidate-pager{display:grid;grid-template-columns:1fr 1fr;align-items:stretch}.candidate-pager [data-candidate-prev]{grid-column:1;grid-row:1}.candidate-pager [data-candidate-next]{grid-column:2;grid-row:1}.candidate-page-numbers{grid-column:1/-1;grid-row:2;justify-content:center}.candidate-page-status{grid-column:1;grid-row:3;align-self:center}.candidate-pager label{grid-column:2;grid-row:3;display:flex;align-items:center;justify-content:flex-end;gap:6px}.candidate-pager label select{min-width:0}.file-chip{display:block;width:100%;padding:8px 10px}.field-coverage-card{padding:10px 12px}.result-notice-card,.disclaimer-card{padding:14px 16px}.section{padding:12px}}
@media(hover:none){.candidate-open-button,.candidate-download-link,.candidate-toolbar input,.candidate-toolbar select,.candidate-toolbar button,.candidate-pager button,.candidate-pager select,.stock-dialog-close,.stock-action-grid button,.detail-action-button{min-height:44px}}
@media(max-width:640px){.candidate-cards[data-preview-table] .table-wrap{display:none}.preview-mobile-cards{display:grid;gap:10px}.preview-mobile-card{border:0;border-radius:8px;background:#fff;padding:11px 12px;box-shadow:var(--hairline-soft),var(--surface-highlight),0 4px 12px rgba(15,23,42,.03);cursor:pointer}.preview-mobile-card:hover,.preview-mobile-card:focus-visible{outline:2px solid #6daff0;outline-offset:2px;background:#f8fcfa}.preview-mobile-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.preview-mobile-head .stock-anchor{font-size:16px;line-height:1.25}.preview-mobile-head .stock-code{margin-top:2px}.preview-mobile-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}.preview-mobile-meta-item{display:grid;gap:2px;min-width:0;border:0;border-radius:8px;background:#fbfdff;padding:8px 9px;color:#334155;font-size:13px;line-height:1.35;overflow-wrap:anywhere;box-shadow:var(--hairline-soft),var(--surface-highlight)}.preview-mobile-meta-item b{color:var(--muted);font-size:12px;font-weight:850}.preview-mobile-summary{margin-top:10px;color:var(--text);font-size:13px;line-height:1.5;overflow-wrap:anywhere}}
@media(max-width:520px){.hero-fact-card,.pipeline-metrics{grid-template-columns:1fr}.selection-flow{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.pipeline-card{border-right:0}.pipeline-card:nth-last-child(2){border-bottom:1px solid var(--line)}.flow-step small{display:none}}
@media(max-width:900px){.stock-detail-drawer{place-items:end center;padding:12px;padding-bottom:calc(12px + env(safe-area-inset-bottom))}.stock-dialog{width:100%;max-height:calc(100vh - 24px);padding-bottom:env(safe-area-inset-bottom)}.stock-dialog-grid{grid-template-columns:1fr}.stock-dialog-head{position:relative}.stock-chart-wrap{min-height:320px;aspect-ratio:auto}}
	@media(max-width:640px){.stock-dialog-head{position:relative;display:grid;grid-template-columns:minmax(0,1fr) max-content;align-items:start;gap:12px;padding:14px 16px 12px}.stock-dialog-head h3{font-size:24px;line-height:1.12}.stock-dialog-head p{gap:8px}.stock-dialog-close{min-width:44px;min-height:44px;margin-top:0;padding:5px 12px}.stock-action-grid{grid-template-columns:1fr}.stock-action-grid button{min-height:44px}.stock-fact-grid,.stock-fact-grid.secondary{grid-template-columns:1fr}.stock-technical-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.stock-chart-wrap{min-height:280px}}
"""
