/* ═══════════════════════════════════════════════════════════════════════════
   MedFL Dashboard — Application Logic
   Vanilla JS + Chart.js + SSE for real-time monitoring
   ═══════════════════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin;
// Orchestrator is accessed from the browser (outside Docker) via port mapping
const ORCHESTRATOR_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8001'
    : `http://${window.location.hostname}:8001`;
const POLL_INTERVAL = 5000;

// ── State ─────────────────────────────────────────────────────────────────
let accuracyChart = null;
let lossChart = null;
let eventSource = null;
let pollTimer = null;

// ── Chart Configuration ───────────────────────────────────────────────────
const CHART_COLORS = {
    indigo: 'rgba(99, 102, 241, 1)',
    indigoFaded: 'rgba(99, 102, 241, 0.2)',
    cyan: 'rgba(6, 182, 212, 1)',
    cyanFaded: 'rgba(6, 182, 212, 0.2)',
    emerald: 'rgba(16, 185, 129, 1)',
    emeraldFaded: 'rgba(16, 185, 129, 0.2)',
    rose: 'rgba(244, 63, 94, 1)',
    roseFaded: 'rgba(244, 63, 94, 0.2)',
    amber: 'rgba(245, 158, 11, 1)',
    amberFaded: 'rgba(245, 158, 11, 0.2)',
};

const DIST_COLORS = [
    '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#f43f5e',
    '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#3b82f6'
];

function chartDefaults() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 600, easing: 'easeOutQuart' },
        plugins: {
            legend: {
                labels: {
                    color: '#94a3b8',
                    font: { family: "'Inter', sans-serif", size: 11 },
                    padding: 16,
                    usePointStyle: true,
                    pointStyleWidth: 8,
                }
            },
            tooltip: {
                backgroundColor: 'rgba(17, 24, 39, 0.95)',
                titleColor: '#f1f5f9',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(99, 102, 241, 0.2)',
                borderWidth: 1,
                padding: 12,
                cornerRadius: 8,
                titleFont: { family: "'Inter', sans-serif", weight: '600' },
                bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
            }
        },
        scales: {
            x: {
                grid: { color: 'rgba(99, 102, 241, 0.06)', drawBorder: false },
                ticks: { color: '#64748b', font: { family: "'Inter', sans-serif", size: 11 } },
                title: { display: true, text: 'Round', color: '#64748b', font: { family: "'Inter', sans-serif", size: 12 } }
            },
            y: {
                grid: { color: 'rgba(99, 102, 241, 0.06)', drawBorder: false },
                ticks: { color: '#64748b', font: { family: "'JetBrains Mono', monospace", size: 11 } },
            }
        }
    };
}

// ── Initialize Charts ─────────────────────────────────────────────────────
function initCharts() {
    const accCtx = document.getElementById('accuracy-chart').getContext('2d');
    accuracyChart = new Chart(accCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Global Accuracy',
                data: [],
                borderColor: CHART_COLORS.emerald,
                backgroundColor: CHART_COLORS.emeraldFaded,
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointRadius: 4,
                pointHoverRadius: 7,
                pointBackgroundColor: CHART_COLORS.emerald,
                pointBorderColor: '#111827',
                pointBorderWidth: 2,
            }]
        },
        options: {
            ...chartDefaults(),
            scales: {
                ...chartDefaults().scales,
                y: {
                    ...chartDefaults().scales.y,
                    min: 0,
                    max: 1,
                    title: { display: true, text: 'Accuracy', color: '#64748b' },
                    ticks: {
                        ...chartDefaults().scales.y.ticks,
                        callback: v => (v * 100).toFixed(0) + '%'
                    }
                }
            }
        }
    });

    const lossCtx = document.getElementById('loss-chart').getContext('2d');
    lossChart = new Chart(lossCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Global Loss',
                data: [],
                borderColor: CHART_COLORS.rose,
                backgroundColor: CHART_COLORS.roseFaded,
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointRadius: 4,
                pointHoverRadius: 7,
                pointBackgroundColor: CHART_COLORS.rose,
                pointBorderColor: '#111827',
                pointBorderWidth: 2,
            }]
        },
        options: {
            ...chartDefaults(),
            scales: {
                ...chartDefaults().scales,
                y: {
                    ...chartDefaults().scales.y,
                    title: { display: true, text: 'Loss', color: '#64748b' },
                }
            }
        }
    });
}

// ── Clock ─────────────────────────────────────────────────────────────────
function updateClock() {
    const now = new Date();
    const el = document.getElementById('clock');
    if (el) {
        el.textContent = now.toLocaleTimeString('en-US', { hour12: false }) +
            ' · ' + now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
}

// ── Animated Number Update ────────────────────────────────────────────────
function animateValue(el, newText) {
    if (el.textContent !== newText) {
        el.style.transform = 'translateY(-4px)';
        el.style.opacity = '0.5';
        setTimeout(() => {
            el.textContent = newText;
            el.style.transform = 'translateY(0)';
            el.style.opacity = '1';
        }, 150);
    }
}

// ── Fetch Data ────────────────────────────────────────────────────────────
async function fetchJSON(url) {
    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.warn(`Fetch failed: ${url}`, e);
        return null;
    }
}

async function refreshDashboard() {
    // Summary
    const summary = await fetchJSON(`${API_BASE}/metrics/summary`);
    if (summary) {
        animateValue(document.getElementById('total-rounds'), String(summary.total_rounds));
        animateValue(document.getElementById('global-accuracy'), (summary.latest_accuracy * 100).toFixed(2) + '%');
        animateValue(document.getElementById('global-loss'), summary.latest_loss.toFixed(4));
        animateValue(document.getElementById('active-hospitals'), String(summary.active_hospitals || 0));
        animateValue(document.getElementById('best-accuracy'), (summary.best_accuracy * 100).toFixed(2) + '%');
        animateValue(document.getElementById('audit-count'), `${summary.total_audit_events} events`);

        const algos = summary.algorithms_used || [];
        animateValue(document.getElementById('current-algorithm'),
            algos.length > 0 ? algos[algos.length - 1].toUpperCase() : '—');

        // Accuracy trend badge
        const accBadge = document.getElementById('acc-trend-badge');
        if (summary.latest_accuracy > 0) {
            accBadge.textContent = (summary.latest_accuracy * 100).toFixed(1) + '%';
            accBadge.className = 'badge' + (summary.latest_accuracy > 0.7 ? ' badge-secure' : '');
        }

        // System status
        const statusEl = document.getElementById('system-status');
        statusEl.className = 'status-badge online';
        statusEl.querySelector('.status-text').textContent = 'Online';
    }

    // Convergence data
    const conv = await fetchJSON(`${API_BASE}/metrics/convergence`);
    if (conv && conv.rounds.length > 0) {
        const labels = conv.rounds.map(r => `R${r}`);

        accuracyChart.data.labels = labels;
        accuracyChart.data.datasets[0].data = conv.accuracies;
        accuracyChart.update('none');

        lossChart.data.labels = labels;
        lossChart.data.datasets[0].data = conv.losses;
        lossChart.update('none');

        // Loss trend badge
        const lossBadge = document.getElementById('loss-trend-badge');
        const lastLoss = conv.losses[conv.losses.length - 1];
        lossBadge.textContent = lastLoss.toFixed(4);
    }

    // Round status from orchestrator
    const roundStatus = await fetchJSON(`${ORCHESTRATOR_URL}/rounds/status`);
    if (roundStatus) {
        const stateEl = document.getElementById('round-state');
        stateEl.textContent = roundStatus.state.toUpperCase();
        stateEl.className = 'round-state ' + roundStatus.state;
        document.getElementById('round-progress').textContent =
            roundStatus.state === 'waiting'
                ? `${roundStatus.updates_received}/${roundStatus.waiting_for} updates`
                : '';
    }

    // Hospital statuses from orchestrator
    const hospitals = await fetchJSON(`${ORCHESTRATOR_URL}/hospitals`);
    if (hospitals) {
        renderHospitals(hospitals);
    }

    // Round history
    const history = await fetchJSON(`${API_BASE}/metrics/history`);
    if (history) {
        renderHistoryTable(history);
        document.getElementById('history-count-badge').textContent = `${history.length} rounds`;
    }

    // Audit log
    const audit = await fetchJSON(`${API_BASE}/audit/log`);
    if (audit && audit.length > 0) {
        renderAuditLog(audit);
    }
}

// ── Render Hospitals ──────────────────────────────────────────────────────
function renderHospitals(hospitals) {
    const grid = document.getElementById('hospital-grid');
    const entries = Object.entries(hospitals);
    document.getElementById('hospital-count-badge').textContent = `${entries.length} nodes`;

    if (entries.length === 0) {
        grid.innerHTML = '<div class="hospital-placeholder">No hospital nodes registered</div>';
        return;
    }

    grid.innerHTML = entries.map(([hid, data]) => {
        const status = data.status || 'unreachable';
        const acc = data.last_accuracy != null ? (data.last_accuracy * 100).toFixed(2) + '%' : '—';
        const loss = data.last_loss != null ? data.last_loss.toFixed(4) : '—';
        const rounds = data.rounds_completed || 0;
        const name = (data.hospital_id || hid).replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase());

        return `
            <div class="hospital-node-card">
                <div class="hospital-node-header">
                    <span class="hospital-node-name">${name}</span>
                    <span class="hospital-node-status ${status}">${status}</span>
                </div>
                <div class="hospital-node-metrics">
                    <div class="hospital-metric">
                        <span class="hospital-metric-label">Accuracy</span>
                        <span class="hospital-metric-value">${acc}</span>
                    </div>
                    <div class="hospital-metric">
                        <span class="hospital-metric-label">Loss</span>
                        <span class="hospital-metric-value">${loss}</span>
                    </div>
                    <div class="hospital-metric">
                        <span class="hospital-metric-label">Rounds</span>
                        <span class="hospital-metric-value">${rounds}</span>
                    </div>
                    <div class="hospital-metric">
                        <span class="hospital-metric-label">Token</span>
                        <span class="hospital-metric-value">${data.token_set ? '✓' : '✗'}</span>
                    </div>
                </div>
            </div>`;
    }).join('');
}

// ── Render History Table ──────────────────────────────────────────────────
function renderHistoryTable(history) {
    const tbody = document.getElementById('history-tbody');
    tbody.innerHTML = history.slice().reverse().map(r => {
        const participants = r.participants ? r.participants.join(', ') : '—';
        const ish = r.ish_weights ? Object.entries(r.ish_weights).map(([k, v]) =>
            `${k.replace('hospital-', 'H')}: ${v}`).join(', ') : '—';
        const ts = r.timestamp ? new Date(r.timestamp).toLocaleTimeString('en-US', { hour12: false }) : '—';

        return `<tr>
            <td><strong>R${r.round_id}</strong></td>
            <td>${(r.algorithm || '—').toUpperCase()}</td>
            <td>${(r.accuracy * 100).toFixed(2)}%</td>
            <td>${r.loss.toFixed(4)}</td>
            <td>${r.duration_sec || 0}s</td>
            <td>${participants}</td>
            <td style="font-family: var(--font-mono); font-size: 0.75rem;">${ish}</td>
            <td style="color: var(--text-muted);">${ts}</td>
        </tr>`;
    }).join('');
}

// ── Render Audit Log ──────────────────────────────────────────────────────
function renderAuditLog(audit) {
    const container = document.getElementById('audit-log');
    container.innerHTML = audit.slice().reverse().slice(0, 20).map(e => {
        const ts = e.timestamp ? new Date(e.timestamp).toLocaleTimeString('en-US', { hour12: false }) : '';
        return `<div class="audit-item">
            <span class="audit-time">${ts}</span>
            <span class="audit-round">R${e.round_id}</span>
            ${e.algorithm.toUpperCase()} · ${e.hospitals ? e.hospitals.length : 0} hospitals ·
            Acc: ${((e.accuracy || 0) * 100).toFixed(1)}% ·
            🔒 ${e.encryption || 'AES'}
        </div>`;
    }).join('');
}

// ── Activity Feed ─────────────────────────────────────────────────────────
function addActivityItem(text) {
    const feed = document.getElementById('activity-feed');
    const placeholder = feed.querySelector('.activity-placeholder');
    if (placeholder) placeholder.remove();

    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `<span class="activity-time">${time}</span><span class="activity-text">${text}</span>`;

    feed.insertBefore(item, feed.firstChild);

    // Keep max 50 items
    while (feed.children.length > 50) {
        feed.removeChild(feed.lastChild);
    }
}

// ── SSE Connection ────────────────────────────────────────────────────────
function connectSSE() {
    if (eventSource) eventSource.close();

    eventSource = new EventSource(`${API_BASE}/metrics/live`);

    eventSource.addEventListener('update', (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'round_complete') {
                const acc = (data.accuracy * 100).toFixed(2);
                addActivityItem(
                    `<strong>Round ${data.round_id}</strong> completed — ` +
                    `${data.algorithm.toUpperCase()} · Accuracy: <strong>${acc}%</strong> · ` +
                    `${data.participants ? data.participants.length : 0} hospitals · ` +
                    `${data.duration_sec}s`
                );
                // Immediate refresh
                refreshDashboard();
            }
        } catch (err) {
            console.warn('SSE parse error:', err);
        }
    });

    eventSource.addEventListener('ping', () => { /* keepalive */ });

    eventSource.onerror = () => {
        console.warn('SSE connection lost, reconnecting in 5s...');
        setTimeout(connectSSE, 5000);
    };
}

// ── Training Controls ─────────────────────────────────────────────────────
document.getElementById('btn-start-auto').addEventListener('click', async () => {
    const algo = document.getElementById('algo-select').value;
    const nRounds = parseInt(document.getElementById('rounds-input').value) || 5;

    addActivityItem(`<strong>Starting</strong> ${nRounds} auto rounds with <strong>${algo.toUpperCase()}</strong>`);

    try {
        const resp = await fetch(`${ORCHESTRATOR_URL}/rounds/auto`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                n_rounds: nRounds,
                algorithm: algo,
                hospital_ids: ['hospital-a', 'hospital-b', 'hospital-c']
            })
        });
        const result = await resp.json();
        addActivityItem(`Auto training <strong>initiated</strong>: ${result.status}`);
    } catch (e) {
        addActivityItem(`<strong style="color: var(--accent-rose);">Error</strong>: ${e.message}`);
    }
});

document.getElementById('btn-start-single').addEventListener('click', async () => {
    const algo = document.getElementById('algo-select').value;

    addActivityItem(`<strong>Starting</strong> single round with <strong>${algo.toUpperCase()}</strong>`);

    try {
        const resp = await fetch(`${ORCHESTRATOR_URL}/rounds/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                algorithm: algo,
                hospital_ids: ['hospital-a', 'hospital-b', 'hospital-c']
            })
        });
        const result = await resp.json();
        addActivityItem(`Round <strong>${result.round_id}</strong> started — triggered: ${result.triggered ? result.triggered.join(', ') : 'none'}`);
    } catch (e) {
        addActivityItem(`<strong style="color: var(--accent-rose);">Error</strong>: ${e.message}`);
    }
});

// ── Initialization ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    updateClock();
    setInterval(updateClock, 1000);

    // Initial data load
    refreshDashboard();

    // Polling
    pollTimer = setInterval(refreshDashboard, POLL_INTERVAL);

    // SSE for real-time updates
    connectSSE();

    addActivityItem('<strong>Dashboard</strong> connected to MedFL monitoring service');
});
