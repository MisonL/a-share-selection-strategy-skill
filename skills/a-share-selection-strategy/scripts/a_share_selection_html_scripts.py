"""JavaScript behavior for the local A-share HTML report."""

from __future__ import annotations

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
        const tooltipDate = document.createElement('strong');
        tooltipDate.textContent = String(hover[0] || '');
        const tooltipPrices = document.createElement('span');
        tooltipPrices.textContent = `O ${formatNumber(open)} H ${formatNumber(high)} L ${formatNumber(low)} C ${formatNumber(close)}`;
        const tooltipVolume = document.createElement('span');
        tooltipVolume.textContent = `V ${Number.isFinite(volume) ? volume.toLocaleString('en-US') : '-'}`;
        stockChartTooltip.replaceChildren(tooltipDate, tooltipPrices, tooltipVolume);
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
      stockDrawer.setAttribute('aria-hidden', 'true');
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
      setBodyLocked(false);
      setModalContentHidden(false, null);
      drawer.setAttribute('aria-hidden', 'true');
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
