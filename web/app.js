// Day Trader Pro - Dual-Market Web Application Logic (India NSE/BSE & US NYSE/NASDAQ)

let state = {
  active_market: 'IN',
  market_info: {},
  config: {},
  watchlist: [],
  watchlist_in: [],
  watchlist_us: [],
  scanner: null,
  plan: null,
  entry: null,
  orders: null,
  timemachine: null,
  risk: null,
  clock: null,
  clocks: {},
  selectedTicker: 'RELIANCE.NS'
};

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  setupEventListeners();
  await refreshStatus();
  await loadTimeMachineData();
  startClockTicker();
}

function setupEventListeners() {
  // Market Switcher Segmented Control
  const btnIN = document.getElementById('btnMarketIN');
  const btnUS = document.getElementById('btnMarketUS');
  if (btnIN) btnIN.addEventListener('click', () => setMarket('IN'));
  if (btnUS) btnUS.addEventListener('click', () => setMarket('US'));

  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  // Action Buttons
  document.getElementById('btnTestLoop').addEventListener('click', () => runCommand('test-loop'));
  document.getElementById('btnScanDaily').addEventListener('click', () => runCommand('scan-daily'));
  document.getElementById('btnScanOrb').addEventListener('click', () => runCommand('scan-orb'));
  document.getElementById('btnScanFixture').addEventListener('click', () => runCommand('scan-fixture'));
  document.getElementById('btnRefreshStatus').addEventListener('click', refreshStatus);
  document.getElementById('btnRunSim').addEventListener('click', () => {
    if (!state.plan) return;
    runCommand('sim', {
      symbol: state.plan.symbol,
      entry: state.plan.entry,
      stop: state.plan.stop,
      target: state.plan.target
    });
  });
  document.getElementById('btnRecalcPlan').addEventListener('click', () => {
    const isIN = (state.active_market === 'IN');
    runCommand('plan', {
      symbol: state.selectedTicker,
      entry: state.plan ? state.plan.entry : (isIN ? 1195.00 : 348.22),
      or_high: isIN ? 1195.00 : 348.00,
      or_low: isIN ? 1183.00 : 344.00
    });
  });

  // Watchlist Add
  document.getElementById('btnAddTicker').addEventListener('click', handleAddTicker);
  document.getElementById('inputAddTicker').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleAddTicker();
  });

  // Drawer Toggle
  document.getElementById('drawerHeader').addEventListener('click', (e) => {
    if (e.target.id === 'btnClearLogs') return;
    document.getElementById('terminalDrawer').classList.toggle('minimized');
    const isMin = document.getElementById('terminalDrawer').classList.contains('minimized');
    document.getElementById('btnToggleDrawer').innerHTML = isMin ? 'Expand &uarr;' : 'Minimize &darr;';
  });
  document.getElementById('btnClearLogs').addEventListener('click', () => {
    document.getElementById('logStream').textContent = 'Logs cleared.';
  });

  // Settings Modal
  document.getElementById('btnSettings').addEventListener('click', openSettingsModal);
  document.getElementById('btnCloseSettings').addEventListener('click', closeSettingsModal);
  document.getElementById('btnCancelSettings').addEventListener('click', closeSettingsModal);
  document.getElementById('btnSaveSettings').addEventListener('click', saveSettings);

  // Approve Paper / MIS Order
  document.getElementById('btnPlaceOrder').addEventListener('click', () => {
    const isIN = (state.active_market === 'IN');
    const sym = state.plan ? state.plan.symbol : (isIN ? 'RELIANCE.NS' : 'TSLA');
    const qty = state.orders && state.orders.orders ? state.orders.orders[0].qty : '10';
    if (isIN) {
      if (confirm(`Send INTRADAY MIS Bracket Order to Zerodha Kite Sandbox?\n\nBUY ${qty} ${sym} (NSE MIS, Market)\nStop-Loss & Take-Profit Brackets Attached.`)) {
        appendLog(`[BROKER] Order for ${qty} ${sym} staged in Zerodha Kite Connect sandbox.`);
        alert(`Zerodha Kite MIS order staged for ${sym}. In Claude/Chat, reply "yes" to confirm submission.`);
      }
    } else {
      if (confirm(`Send PAPER Bracket Order to Alpaca Sandbox?\n\nBUY ${qty} ${sym} (Day, Market)\nStop-Loss & Take-Profit Brackets Attached.`)) {
        appendLog(`[BROKER] Order for ${qty} ${sym} staged in Alpaca paper sandbox.`);
        alert(`Paper trade order staged for ${sym}. In Claude/Chat, reply "yes" to confirm submission.`);
      }
    }
  });

  // Window resize re-draws canvas
  window.addEventListener('resize', () => {
    if (state.timemachine) renderFanChart(state.timemachine);
  });
}

// Market Switch Handler
async function setMarket(marketCode) {
  if (state.active_market === marketCode) return;
  const mktName = (marketCode === 'IN') ? 'Indian Markets (NSE/BSE, ₹ INR)' : 'US Markets (NYSE/NASDAQ, $ USD)';
  appendLog(`[MARKET] Switching active market to ${mktName}...`);

  // Optimistically toggle switcher button classes
  document.getElementById('btnMarketIN').classList.toggle('active', marketCode === 'IN');
  document.getElementById('btnMarketUS').classList.toggle('active', marketCode === 'US');
  document.getElementById('clockBadgeIN').classList.toggle('active-market-clock', marketCode === 'IN');
  document.getElementById('clockBadgeUS').classList.toggle('active-market-clock', marketCode === 'US');

  try {
    const res = await fetch('/api/set-market', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ market: marketCode })
    });
    const data = await res.json();
    if (data.status) {
      state = { ...state, ...data.status };
      if (state.watchlist && state.watchlist.length > 0) {
        state.selectedTicker = state.watchlist[0];
      }
      renderUI();
      await loadTimeMachineData();
    }
    appendLog(data.output || `[MARKET] Successfully switched active market to ${marketCode}.`);
  } catch (err) {
    appendLog(`[ERROR] Failed to switch market: ${err.message}`);
    await refreshStatus();
  }
}

async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state = { ...state, ...data };
    if (!state.selectedTicker && state.watchlist && state.watchlist.length > 0) {
      state.selectedTicker = state.watchlist[0];
    }
    renderUI();
  } catch (err) {
    appendLog(`[ERROR] Failed to fetch status: ${err.message}`);
  }
}

async function loadTimeMachineData() {
  try {
    const res = await fetch('/api/timemachine');
    const tm = await res.json();
    state.timemachine = tm;
    renderFanChart(tm);
  } catch (err) {
    appendLog(`[WARN] No timemachine chart data available.`);
  }
}

function formatCurrency(val, decimals = 2) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  const isIN = (state.active_market === 'IN' || (state.market_info && state.market_info.currency === 'INR'));
  const sym = (state.market_info && state.market_info.currency_symbol) || (isIN ? '₹' : '$');
  const num = Number(val);
  const locale = isIN ? 'en-IN' : 'en-US';
  return `${sym}${num.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

function renderUI() {
  renderHeader();
  renderWatchlist();
  renderScannerHits();
  renderSetupCard();
  renderSizingCard();
  renderRiskCheck();
  renderTicket();
}

function renderHeader() {
  const isIN = (state.active_market === 'IN');

  // Switch buttons
  const btnIN = document.getElementById('btnMarketIN');
  const btnUS = document.getElementById('btnMarketUS');
  if (btnIN) btnIN.classList.toggle('active', isIN);
  if (btnUS) btnUS.classList.toggle('active', !isIN);

  // Active clock highlight
  const bIN = document.getElementById('clockBadgeIN');
  const bUS = document.getElementById('clockBadgeUS');
  if (bIN) bIN.classList.toggle('active-market-clock', isIN);
  if (bUS) bUS.classList.toggle('active-market-clock', !isIN);

  // Metrics HUD
  const cfg = state.config || {};
  const budget = cfg.budget || (isIN ? 100000 : 5000);
  const maxRisk = cfg.max_loss_per_trade_usd || (isIN ? 1000 : 50);
  const dailyCap = cfg.max_daily_loss_usd || (isIN ? 3000 : 150);

  document.getElementById('hdrBudget').textContent = formatCurrency(budget, 0);
  document.getElementById('hdrMaxRisk').textContent = formatCurrency(maxRisk, 0);
  document.getElementById('hdrDailyCap').textContent = formatCurrency(dailyCap, 0);

  // Dual Live Clocks & Countdown Timers
  updateLiveClocks();


  // Input placeholder
  const input = document.getElementById('inputAddTicker');
  if (input) {
    input.placeholder = isIN ? 'Add symbol (e.g. RELIANCE, TCS)...' : 'Add symbol (e.g. TSLA, NVDA)...';
  }
}

function renderWatchlist() {
  const container = document.getElementById('watchlistContainer');
  container.innerHTML = '';
  const list = state.watchlist || [];
  document.getElementById('watchlistCount').textContent = list.length;

  list.forEach(sym => {
    const row = document.createElement('div');
    row.className = `ticker-row ${sym === state.selectedTicker ? 'selected' : ''}`;
    row.innerHTML = `
      <div class="ticker-sym-box">
        <span class="ticker-name mono">${sym}</span>
        <span class="ticker-tag-sub">${state.active_market === 'IN' ? 'NSE &middot; Equity' : 'US &middot; Common'}</span>
      </div>
      <div class="ticker-data-box">
        <span class="ticker-price mono">&mdash;</span>
        <div class="ticker-change mono up">Active</div>
      </div>
    `;
    row.addEventListener('click', () => {
      state.selectedTicker = sym;
      document.querySelectorAll('.ticker-row').forEach(r => r.classList.remove('selected'));
      row.classList.add('selected');
      fetchNews(sym);
    });
    container.appendChild(row);
  });
}

function renderScannerHits() {
  const scanner = state.scanner;
  const dailyContainer = document.getElementById('dailyHitsContainer');
  const orbContainer = document.getElementById('orbHitsContainer');

  dailyContainer.innerHTML = '';
  orbContainer.innerHTML = '';

  if (!scanner || !scanner.hits || scanner.hits.length === 0) {
    document.getElementById('dailyHitsMeta').textContent = 'No active scanner hits recorded.';
    document.getElementById('orbHitsMeta').textContent = 'No active ORB hits recorded.';
    return;
  }

  if (scanner.mode === 'daily') {
    document.getElementById('dailyHitsCount').textContent = scanner.hits.length;
    document.getElementById('dailyHitsMeta').textContent = `Scanned ${scanner.scanned} symbols on ${scanner.as_of}. Found ${scanner.hits.length} hit(s).`;
    scanner.hits.forEach(hit => {
      const row = createHitRow(hit);
      dailyContainer.appendChild(row);
    });
  } else if (scanner.mode === 'orb') {
    document.getElementById('orbHitsCount').textContent = scanner.hits.length;
    document.getElementById('orbHitsMeta').textContent = `ORB scan: ${scanner.hits.length} stocks closed above 15-min range.`;
    scanner.hits.forEach(hit => {
      const row = createHitRow(hit);
      orbContainer.appendChild(row);
    });
  }
}

function createHitRow(hit) {
  const row = document.createElement('div');
  row.className = `ticker-row ${hit.symbol === state.selectedTicker ? 'selected' : ''}`;
  const setups = (hit.setups || ['Breakout']).join(', ');
  row.innerHTML = `
    <div class="ticker-sym-box">
      <span class="ticker-name mono">${hit.symbol}</span>
      <span class="ticker-tag-sub text-accent">${setups}</span>
    </div>
    <div class="ticker-data-box">
      <span class="ticker-price mono">${hit.price ? formatCurrency(hit.price) : '--'}</span>
      <div class="ticker-change mono up">${hit.rsi ? `RSI ${hit.rsi.toFixed(1)}` : '+0.55%'}</div>
    </div>
  `;
  row.addEventListener('click', () => {
    state.selectedTicker = hit.symbol;
    document.querySelectorAll('.ticker-row').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');
    fetchNews(hit.symbol);
  });
  return row;
}

function renderSetupCard() {
  const plan = state.plan;
  const isIN = (state.active_market === 'IN');
  const defaultSym = isIN ? 'RELIANCE.NS' : 'TSLA';
  const sym = plan ? (plan.symbol || defaultSym) : defaultSym;

  document.getElementById('setupSymbol').textContent = sym;
  document.getElementById('setupTypeBadge').textContent = (plan && plan.setup ? plan.setup : 'OPENING RANGE BREAKOUT').toUpperCase();

  if (plan) {
    document.getElementById('valTargetPrice').textContent = formatCurrency(plan.target);
    document.getElementById('valEntryPrice').textContent = formatCurrency(plan.entry);
    document.getElementById('valStopPrice').textContent = formatCurrency(plan.stop);

    const riskPerShare = plan.risk_per_share || (plan.entry && plan.stop ? Math.abs(plan.entry - plan.stop) : 1);
    document.getElementById('specRiskPerShare').textContent = formatCurrency(riskPerShare);
    document.getElementById('specRewardRisk').textContent = plan.reward_risk ? plan.reward_risk.toFixed(2) : '1.00';

    const flatBy = plan.flat_by || (isIN ? '15:15' : '15:55');
    const tz = isIN ? 'IST' : 'ET';
    document.getElementById('specFlatBy').textContent = `${flatBy} ${tz}`;

    document.getElementById('valTargetGain').textContent = `+${formatCurrency(riskPerShare)} / sh`;
    document.getElementById('valStopLoss').textContent = `-${formatCurrency(riskPerShare)} / sh`;
  }
}

function renderSizingCard() {
  const orders = state.orders;
  const plan = state.plan;
  const cfg = state.config || {};
  const isIN = (state.active_market === 'IN');
  const maxLossLimit = cfg.max_loss_per_trade_usd || (isIN ? 1000 : 50);

  if (orders && orders.orders && orders.orders.length > 0) {
    const o = orders.orders[0];
    document.getElementById('sizeSharesNum').textContent = o.qty;
    document.getElementById('sizeSharesSymbol').textContent = o.symbol;
    const maxLoss = (o.plan && o.plan.max_loss) ? o.plan.max_loss : (parseFloat(o.qty) * (o.plan ? o.plan.risk_per_share : 1));
    document.getElementById('sizeMaxLossNum').textContent = formatCurrency(maxLoss);
    document.getElementById('sizeLimitSub').textContent = `Risk Limit: ${formatCurrency(maxLossLimit)}`;

    if (o.plan) {
      const rps = o.plan.risk_per_share || 1;
      const entry = o.plan.entry || 1;
      const budget = cfg.budget || (isIN ? 100000 : 5000);
      document.getElementById('lblLimitLoss').textContent = `1. Max Loss Limit (${formatCurrency(maxLossLimit, 0)} / ${formatCurrency(rps)})`;
      document.getElementById('lblLimitCap').textContent = `2. Position Cap (${cfg.max_position_pct || 75}% / ${formatCurrency(entry)})`;
      document.getElementById('lblLimitOrder').textContent = `3. Max Order Limit (${formatCurrency(budget * 0.75, 0)} / ${formatCurrency(entry)})`;
      document.getElementById('lblLimitCash').textContent = `4. Cash Buffer (${formatCurrency(budget * 0.90, 0)} / ${formatCurrency(entry)})`;
    }
  } else if (plan) {
    document.getElementById('sizeSharesSymbol').textContent = plan.symbol;
  }
}

function renderRiskCheck() {
  const risk = state.risk;
  const badge = document.getElementById('riskStatusBadge');
  if (risk && risk.results && risk.results.length > 0) {
    const r = risk.results[0];
    if (r.verdict === 'PASS') {
      badge.className = 'status-badge pass';
      badge.textContent = 'PASS';
    } else {
      badge.className = 'status-badge block';
      badge.textContent = 'BLOCK';
    }
  } else {
    badge.className = 'status-badge pass';
    badge.textContent = 'PASS';
  }
}

function renderTicket() {
  const orders = state.orders;
  const isIN = (state.active_market === 'IN');

  const brokerTag = document.getElementById('ticketBrokerTag');
  const tktType = document.getElementById('tktType');
  const btnPlaceOrderText = document.getElementById('btnPlaceOrderText');
  const jsonSummary = document.getElementById('ticketJsonSummary');

  if (isIN) {
    brokerTag.textContent = 'ZERODHA KITE (NSE MIS)';
    tktType.textContent = 'MIS DAY';
    btnPlaceOrderText.textContent = 'Approve & Stage MIS Order';
    jsonSummary.textContent = 'View Zerodha Kite API JSON';
  } else {
    brokerTag.textContent = 'ALPACA PAPER TRADING';
    tktType.textContent = 'DAY BRACKET';
    btnPlaceOrderText.textContent = 'Approve & Stage Paper Order';
    jsonSummary.textContent = 'View Alpaca Bracket API JSON';
  }

  if (orders && orders.orders && orders.orders.length > 0) {
    const o = orders.orders[0];
    document.getElementById('tktQty').textContent = o.qty;
    document.getElementById('tktSym').textContent = o.symbol;

    const stopPrice = o.stop_loss_stop_price || o.stoploss || (o.plan ? o.plan.stop : 0);
    const targetPrice = o.take_profit_limit_price || o.squareoff || (o.plan ? o.plan.target : 0);

    document.getElementById('tktStop').textContent = formatCurrency(parseFloat(stopPrice));
    document.getElementById('tktTarget').textContent = formatCurrency(parseFloat(targetPrice));

    if (isIN || (o.symbol && (o.symbol.endsWith('.NS') || o.symbol.endsWith('.BO')))) {
      const cleanSym = o.symbol.replace(/\.(NS|BO)$/, '');
      const zerodhaPayload = {
        tradingsymbol: cleanSym,
        exchange: o.symbol.endsWith('.BO') ? 'BSE' : 'NSE',
        transaction_type: 'BUY',
        order_type: 'MARKET',
        quantity: parseInt(o.qty, 10),
        product: 'MIS',
        validity: 'DAY',
        stoploss: parseFloat(stopPrice),
        squareoff: parseFloat(targetPrice),
        tag: 'quantdesk_orb'
      };
      document.getElementById('ticketJsonPreview').textContent = JSON.stringify(zerodhaPayload, null, 2);
    } else {
      document.getElementById('ticketJsonPreview').textContent = JSON.stringify(o, null, 2);
    }
  }
}

// Interactive Fan Chart Canvas Renderer
function renderFanChart(tm) {
  const canvas = document.getElementById('fanChartCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;
  const pad = { top: 25, bottom: 35, left: 65, right: 25 };

  ctx.clearRect(0, 0, W, H);

  if (!tm || !tm.mc || !tm.mc.bands || tm.mc.bands.length === 0) {
    ctx.fillStyle = '#53627a';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No Monte Carlo simulation data available. Click "Replay Setup".', W / 2, H / 2);
    return;
  }

  const mc = tm.mc;
  const bands = mc.bands; // array of [p5, p25, median, p75, p95]
  const isIN = (state.active_market === 'IN');
  const defaultPlan = isIN ? { entry: 1195.0, stop: 1183.0, target: 1207.0 } : { entry: 348.22, stop: 344.0, target: 352.44 };
  const plan = tm.plan || state.plan || defaultPlan;

  // Update HUD odds
  document.getElementById('oddTargetVal').textContent = `${(mc.p_target * 100).toFixed(1)}%`;
  document.getElementById('oddTargetFill').style.width = `${(mc.p_target * 100).toFixed(1)}%`;
  document.getElementById('oddStopVal').textContent = `${(mc.p_stop * 100).toFixed(1)}%`;
  document.getElementById('oddStopFill').style.width = `${(mc.p_stop * 100).toFixed(1)}%`;
  document.getElementById('oddNeitherVal').textContent = `${(mc.p_neither * 100).toFixed(1)}%`;
  document.getElementById('oddNeitherFill').style.width = `${(mc.p_neither * 100).toFixed(1)}%`;
  document.getElementById('oddGreenVal').textContent = `${(mc.p_green * 100).toFixed(1)}%`;
  document.getElementById('oddGreenFill').style.width = `${(mc.p_green * 100).toFixed(1)}%`;

  // Verdict update
  const diff = Math.abs(mc.p_target - mc.p_stop) * 100;
  if (diff < 5) {
    document.getElementById('verdictTitle').textContent = 'CLOSE TO A COIN FLIP';
    document.getElementById('verdictSub').textContent = `Target first in ${(mc.p_target * 100).toFixed(1)}% vs stop in ${(mc.p_stop * 100).toFixed(1)}%.`;
  } else if (mc.p_target > mc.p_stop) {
    document.getElementById('verdictTitle').textContent = 'LEANS TOWARD THE TARGET';
    document.getElementById('verdictSub').textContent = `Target hit in ${(mc.p_target * 100).toFixed(1)}% vs stop in ${(mc.p_stop * 100).toFixed(1)}%. Average R: +${mc.avg_R.toFixed(3)}.`;
  } else {
    document.getElementById('verdictTitle').textContent = 'LEANS TOWARD THE STOP';
    document.getElementById('verdictSub').textContent = `Stop hit in ${(mc.p_stop * 100).toFixed(1)}% vs target in ${(mc.p_target * 100).toFixed(1)}%.`;
  }

  // Min / Max price scaling
  let minP = plan.stop * 0.995;
  let maxP = plan.target * 1.005;
  bands.forEach(b => {
    if (b[0] < minP) minP = b[0];
    if (b[4] > maxP) maxP = b[4];
  });

  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;
  const n = bands.length;

  const getX = (i) => pad.left + (i / (n - 1)) * chartW;
  const getY = (price) => pad.top + chartH - ((price - minP) / (maxP - minP)) * chartH;

  const curSym = (state.market_info && state.market_info.currency_symbol) || (isIN ? '₹' : '$');

  // Grid lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
  ctx.lineWidth = 1;
  for (let step = 0; step <= 4; step++) {
    const p = minP + (step / 4) * (maxP - minP);
    const y = getY(p);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();

    ctx.fillStyle = '#53627a';
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`${curSym}${p.toFixed(1)}`, pad.left - 8, y + 3);
  }

  // 1. Fill P5 to P95 (Outer 90% Fan)
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const x = getX(i);
    const y = getY(bands[i][4]); // p95
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  for (let i = n - 1; i >= 0; i--) {
    const x = getX(i);
    const y = getY(bands[i][0]); // p5
    ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = 'rgba(0, 243, 255, 0.12)';
  ctx.fill();

  // 2. Fill P25 to P75 (Middle 50% Fan)
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const x = getX(i);
    const y = getY(bands[i][3]); // p75
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  for (let i = n - 1; i >= 0; i--) {
    const x = getX(i);
    const y = getY(bands[i][1]); // p25
    ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = 'rgba(0, 243, 255, 0.25)';
  ctx.fill();

  // 3. Median Path (Cyan Line)
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const x = getX(i);
    const y = getY(bands[i][2]); // median
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = '#00f3ff';
  ctx.lineWidth = 2;
  ctx.stroke();

  // 4. Target Line (Green Dashed)
  const targetY = getY(plan.target);
  ctx.setLineDash([5, 5]);
  ctx.strokeStyle = '#00ff88';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(pad.left, targetY);
  ctx.lineTo(W - pad.right, targetY);
  ctx.stroke();

  // 5. Stop Line (Red Dashed)
  const stopY = getY(plan.stop);
  ctx.strokeStyle = '#ff3366';
  ctx.beginPath();
  ctx.moveTo(pad.left, stopY);
  ctx.lineTo(W - pad.right, stopY);
  ctx.stroke();

  // 6. Entry Line (White Dotted)
  const entryY = getY(plan.entry);
  ctx.setLineDash([2, 4]);
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
  ctx.beginPath();
  ctx.moveTo(pad.left, entryY);
  ctx.lineTo(W - pad.right, entryY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Time Axis Labels
  ctx.fillStyle = '#8c9bb3';
  ctx.font = '10px Inter, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(isIN ? '09:35 AM (Entry)' : '10:15 AM (Entry)', pad.left, H - 12);
  ctx.textAlign = 'center';
  ctx.fillText(isIN ? '12:20 PM' : '1:10 PM', pad.left + chartW / 2, H - 12);
  ctx.textAlign = 'right';
  ctx.fillText(isIN ? '15:15 IST (Cutoff)' : '4:00 PM (Close)', W - pad.right, H - 12);
}

// Execute Command API call
async function runCommand(command, params = {}) {
  appendLog(`[CMD] Running desk command: ${command}...`);
  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, ...params })
    });
    const data = await res.json();
    appendLog(data.output);
    if (data.status) {
      state = { ...state, ...data.status };
      renderUI();
      await loadTimeMachineData();
    }
  } catch (err) {
    appendLog(`[ERROR] Execution failed: ${err.message}`);
  }
}

// Fetch News API call
async function fetchNews(ticker) {
  document.getElementById('newsTickerTag').textContent = ticker;
  document.getElementById('newsFeedContainer').innerHTML = '<div class="empty-feed">Fetching breaking news & filings...</div>';
  appendLog(`[NEWS] Pulling headlines and filings for ${ticker}...`);

  try {
    const res = await fetch(`/api/news?ticker=${ticker}`);
    const data = await res.json();
    appendLog(data.output);

    const container = document.getElementById('newsFeedContainer');
    container.innerHTML = '';
    const lines = data.output.split('\n');
    let hasItems = false;

    lines.forEach(l => {
      if ((l.includes('IST') || l.includes('ET')) && (l.includes('http') || l.includes('Google') || l.includes('Yahoo') || l.includes('EDGAR'))) {
        hasItems = true;
        const item = document.createElement('div');
        item.className = 'news-item';
        item.innerHTML = `
          <div class="news-meta-row">
            <span>${ticker}</span>
            <span>Live Feed</span>
          </div>
          <div class="news-headline">${escapeHtml(l)}</div>
        `;
        container.appendChild(item);
      }
    });

    if (!hasItems) {
      container.innerHTML = `<div class="news-item"><div class="news-headline mono">${escapeHtml(data.output)}</div></div>`;
    }
  } catch (err) {
    document.getElementById('newsFeedContainer').innerHTML = `<div class="empty-feed text-danger">Error: ${err.message}</div>`;
  }
}

function handleAddTicker() {
  const input = document.getElementById('inputAddTicker');
  let val = input.value.trim().toUpperCase();
  if (!val) return;

  if (state.active_market === 'IN' && !val.endsWith('.NS') && !val.endsWith('.BO')) {
    val = val + '.NS';
  }

  if (!state.watchlist.includes(val)) {
    state.watchlist.push(val);
    input.value = '';
    renderWatchlist();
    fetch('/api/save-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols: state.watchlist })
    });
    appendLog(`[WATCHLIST] Added ${val} to watchlist.`);
  }
}

function openSettingsModal() {
  const cfg = state.config || {};
  const isIN = (state.active_market === 'IN');
  const cur = isIN ? '₹' : '$';

  document.getElementById('lblCfgBudget').textContent = `Account Budget (${cur}):`;
  document.getElementById('lblCfgMaxLoss').textContent = `Max Loss Per Trade (${cur}):`;
  document.getElementById('lblCfgMaxDaily').textContent = `Max Daily Loss Limit (${cur}):`;
  document.getElementById('lblCfgFlatBy').textContent = `Flat-by Close Time (${isIN ? 'IST' : 'ET'}):`;

  document.getElementById('cfgBudget').value = cfg.budget || (isIN ? 100000 : 5000);
  document.getElementById('cfgMaxLoss').value = cfg.max_loss_per_trade_usd || (isIN ? 1000 : 50);
  document.getElementById('cfgMaxDaily').value = cfg.max_daily_loss_usd || (isIN ? 3000 : 150);
  document.getElementById('cfgCashBuffer').value = cfg.cash_buffer_pct || 10;
  document.getElementById('cfgPositionCap').value = cfg.max_position_pct || 75;
  document.getElementById('cfgFlatBy').value = cfg.flat_by || (isIN ? '15:15' : '15:55');
  document.getElementById('cfgSecUserAgent').value = cfg.sec_user_agent || 'Trader desk@uwuda.trading';
  document.getElementById('settingsModal').classList.add('open');
}

function closeSettingsModal() {
  document.getElementById('settingsModal').classList.remove('open');
}

async function saveSettings() {
  const updated = {
    ...state.config,
    budget: parseFloat(document.getElementById('cfgBudget').value),
    max_loss_per_trade_usd: parseFloat(document.getElementById('cfgMaxLoss').value),
    max_daily_loss_usd: parseFloat(document.getElementById('cfgMaxDaily').value),
    cash_buffer_pct: parseFloat(document.getElementById('cfgCashBuffer').value),
    max_position_pct: parseFloat(document.getElementById('cfgPositionCap').value),
    flat_by: document.getElementById('cfgFlatBy').value,
    sec_user_agent: document.getElementById('cfgSecUserAgent').value
  };

  try {
    const res = await fetch('/api/save-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: updated })
    });
    const d = await res.json();
    if (d.success) {
      state.config = updated;
      renderHeader();
      renderSizingCard();
      closeSettingsModal();
      appendLog('[SETTINGS] Rules updated successfully.');
    }
  } catch (err) {
    alert('Failed to save settings: ' + err.message);
  }
}

function appendLog(msg) {
  const stream = document.getElementById('logStream');
  if (!stream) return;
  stream.textContent += `\n${msg}`;
  const drawerBody = stream.parentElement;
  if (drawerBody) drawerBody.scrollTop = drawerBody.scrollHeight;
}

function updateLiveClocks() {
  const now = new Date();

  // 1. Indian Standard Time (IST - Asia/Kolkata)
  try {
    const inFormatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Kolkata',
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      weekday: 'short'
    });
    const inParts = inFormatter.formatToParts(now);
    const inHour = parseInt(inParts.find(p => p.type === 'hour').value, 10);
    const inMin = parseInt(inParts.find(p => p.type === 'minute').value, 10);
    const inSec = parseInt(inParts.find(p => p.type === 'second').value, 10);
    const inWeekday = inParts.find(p => p.type === 'weekday').value;
    const inMinutes = inHour * 60 + inMin;
    const isWeekendIN = (inWeekday === 'Sat' || inWeekday === 'Sun');

    // NSE timings: Pre-market 09:00 - 09:15, Regular Open 09:15 - 15:30 (555 to 930 mins)
    const isINOpen = !isWeekendIN && (inMinutes >= 555 && inMinutes < 930);
    const isINPre = !isWeekendIN && (inMinutes >= 540 && inMinutes < 555);

    let inStatusText = 'NSE CLOSED';
    let inStatusClass = 'closed';
    let inCountdown = '';

    if (isINOpen) {
      inStatusText = 'NSE OPEN';
      inStatusClass = 'open';
      const remSec = (930 * 60) - (inMinutes * 60 + inSec);
      const remH = Math.floor(remSec / 3600);
      const remM = Math.floor((remSec % 3600) / 60);
      const remS = remSec % 60;
      inCountdown = `Closes in ${remH}h ${remM.toString().padStart(2, '0')}m ${remS.toString().padStart(2, '0')}s`;
    } else if (isINPre) {
      inStatusText = 'NSE PRE-MKT';
      inStatusClass = 'pre';
      const remSec = (555 * 60) - (inMinutes * 60 + inSec);
      inCountdown = `Opens in ${Math.floor(remSec / 60)}m ${remSec % 60}s`;
    } else {
      inStatusText = 'NSE CLOSED';
      inStatusClass = 'closed';
      if (isWeekendIN) {
        inCountdown = 'Opens Monday 09:15 IST';
      } else if (inMinutes < 540) {
        const remSec = (555 * 60) - (inMinutes * 60 + inSec);
        const remH = Math.floor(remSec / 3600);
        const remM = Math.floor((remSec % 3600) / 60);
        inCountdown = `Opens in ${remH}h ${remM}m`;
      } else {
        inCountdown = 'Opens Tomorrow 09:15 IST';
      }
    }

    const inTimeStr = `${inHour.toString().padStart(2, '0')}:${inMin.toString().padStart(2, '0')}:${inSec.toString().padStart(2, '0')} IST`;
    const inTimeEl = document.getElementById('inTimeDisplay');
    if (inTimeEl) inTimeEl.textContent = inTimeStr;
    const inPill = document.getElementById('inStatusPill');
    const inText = document.getElementById('inStatusText');
    if (inPill && inText) {
      inPill.className = `market-status-pill ${inStatusClass}`;
      inText.textContent = inStatusText;
    }
    const inCdEl = document.getElementById('inCountdown');
    if (inCdEl) inCdEl.textContent = inCountdown;
  } catch (_) {}

  // 2. US Eastern Time (ET - America/New_York)
  try {
    const usFormatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'America/New_York',
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      weekday: 'short'
    });
    const usParts = usFormatter.formatToParts(now);
    const usHour = parseInt(usParts.find(p => p.type === 'hour').value, 10);
    const usMin = parseInt(usParts.find(p => p.type === 'minute').value, 10);
    const usSec = parseInt(usParts.find(p => p.type === 'second').value, 10);
    const usWeekday = usParts.find(p => p.type === 'weekday').value;
    const usMinutes = usHour * 60 + usMin;
    const isWeekendUS = (usWeekday === 'Sat' || usWeekday === 'Sun');

    // NYSE timings: Pre-market 04:00 - 09:30, Regular Open 09:30 - 16:00 (570 to 960 mins)
    const isUSOpen = !isWeekendUS && (usMinutes >= 570 && usMinutes < 960);
    const isUSPre = !isWeekendUS && (usMinutes >= 240 && usMinutes < 570);

    let usStatusText = 'MARKET CLOSED';
    let usStatusClass = 'closed';
    let usCountdown = '';

    if (isUSOpen) {
      usStatusText = 'NYSE OPEN';
      usStatusClass = 'open';
      const remSec = (960 * 60) - (usMinutes * 60 + usSec);
      const remH = Math.floor(remSec / 3600);
      const remM = Math.floor((remSec % 3600) / 60);
      const remS = remSec % 60;
      usCountdown = `Closes in ${remH}h ${remM.toString().padStart(2, '0')}m ${remS.toString().padStart(2, '0')}s`;
    } else if (isUSPre) {
      usStatusText = 'NYSE PRE-MKT';
      usStatusClass = 'pre';
      const remSec = (570 * 60) - (usMinutes * 60 + usSec);
      const remH = Math.floor(remSec / 3600);
      const remM = Math.floor((remSec % 3600) / 60);
      const remS = remSec % 60;
      usCountdown = `Opens in ${remH > 0 ? remH + 'h ' : ''}${remM}m ${remS}s`;
    } else {
      usStatusText = 'MARKET CLOSED';
      usStatusClass = 'closed';
      if (isWeekendUS) {
        usCountdown = 'Opens Monday 09:30 ET';
      } else if (usMinutes < 240) {
        const remSec = (570 * 60) - (usMinutes * 60 + usSec);
        const remH = Math.floor(remSec / 3600);
        const remM = Math.floor((remSec % 3600) / 60);
        usCountdown = `Opens in ${remH}h ${remM}m`;
      } else {
        usCountdown = 'Opens Tomorrow 09:30 ET';
      }
    }

    const usTimeStr = `${usHour.toString().padStart(2, '0')}:${usMin.toString().padStart(2, '0')}:${usSec.toString().padStart(2, '0')} ET`;
    const usTimeEl = document.getElementById('usTimeDisplay');
    if (usTimeEl) usTimeEl.textContent = usTimeStr;
    const usPill = document.getElementById('usStatusPill');
    const usText = document.getElementById('usStatusText');
    if (usPill && usText) {
      usPill.className = `market-status-pill ${usStatusClass}`;
      usText.textContent = usStatusText;
    }
    const usCdEl = document.getElementById('usCountdown');
    if (usCdEl) usCdEl.textContent = usCountdown;
  } catch (_) {}
}

function startClockTicker() {
  // 1. Immediately render initial live clock values
  updateLiveClocks();

  // 2. High-precision 1000ms interval for smooth second-by-second live ticking & countdowns
  setInterval(updateLiveClocks, 1000);

  // 3. Background periodic status sync with server every 10 seconds
  setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data) {
        state.config = data.config || state.config;
        state.market_info = data.market_info || state.market_info;
      }
    } catch (_) {}
  }, 10000);
}


function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
