from __future__ import annotations

import os
from datetime import datetime, timezone

import psutil
from flask import Flask, jsonify

from detector.baseline import BaselineManager
from detector.state import RuntimeState


class DashboardServer:
    def __init__(self, state: RuntimeState, baseline_manager: BaselineManager) -> None:
        self.state = state
        self.baseline_manager = baseline_manager
        self.app = Flask(__name__)
        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.get("/")
        def index() -> str:
            return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>cloud.ng detector</title>
    <style>
      :root { color-scheme: light; --bg: #f5efe4; --card: #fffaf2; --ink: #14213d; --accent: #d97706; --muted: #5f6b7a; --danger: #b91c1c; }
      * { box-sizing: border-box; }
      body { margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif; background:
        radial-gradient(circle at top left, #fde68a 0, transparent 24%),
        linear-gradient(135deg, #f5efe4, #e0f2fe); color: var(--ink); }
      main { padding: 24px; max-width: 1200px; margin: 0 auto; }
      h1 { margin: 0 0 16px; font-size: 2rem; letter-spacing: -0.04em; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
      .card { background: rgba(255,250,242,0.88); backdrop-filter: blur(8px); border: 1px solid rgba(20,33,61,0.08); border-radius: 20px; padding: 18px; box-shadow: 0 10px 30px rgba(20,33,61,0.08); }
      .stat { font-size: 2rem; font-weight: 700; margin: 8px 0 0; }
      .label { color: var(--muted); text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.08em; }
      table { width: 100%; border-collapse: collapse; margin-top: 10px; }
      th, td { text-align: left; padding: 8px 0; border-bottom: 1px solid rgba(20,33,61,0.08); font-size: 0.95rem; }
      .danger { color: var(--danger); font-weight: 700; }
      .muted { color: var(--muted); }
      pre { white-space: pre-wrap; margin: 0; font-family: "IBM Plex Mono", monospace; font-size: 0.9rem; }
      .bars { display: flex; align-items: end; gap: 10px; min-height: 220px; margin-top: 16px; }
      .bar-wrap { display: flex; flex-direction: column; align-items: center; gap: 8px; flex: 1; }
      .bar { width: 100%; max-width: 80px; background: linear-gradient(180deg, #f59e0b, #b45309); border-radius: 14px 14px 6px 6px; min-height: 4px; transition: height 0.3s ease; }
      .bar-label { font-size: 0.75rem; color: var(--muted); text-align: center; }
    </style>
  </head>
  <body>
    <main>
      <h1>cloud.ng anomaly detector</h1>
      <div class="grid">
        <section class="card"><div class="label">Global req/s</div><div id="global-rps" class="stat">0.000</div></section>
        <section class="card"><div class="label">CPU</div><div id="cpu" class="stat">0%</div></section>
        <section class="card"><div class="label">Memory</div><div id="memory" class="stat">0%</div></section>
        <section class="card"><div class="label">Uptime</div><div id="uptime" class="stat">0s</div></section>
      </div>
      <div class="grid" style="margin-top:16px;">
        <section class="card">
          <div class="label">Top 10 Source IPs</div>
          <table><thead><tr><th>IP</th><th>Total</th><th>req/s</th></tr></thead><tbody id="top-ips"></tbody></table>
        </section>
        <section class="card">
          <div class="label">Banned IPs</div>
          <table><thead><tr><th>IP</th><th>Reason</th><th>Release</th></tr></thead><tbody id="banned"></tbody></table>
        </section>
      </div>
      <div class="grid" style="margin-top:16px;">
        <section class="card"><div class="label">Effective Baseline</div><pre id="baseline"></pre></section>
        <section class="card">
          <div class="label">Baseline Graph</div>
          <div id="chart" class="bars"></div>
          <pre id="hourly"></pre>
        </section>
      </div>
    </main>
    <script>
      function formatUptime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h}h ${m}m ${s}s`;
      }
      async function refresh() {
        const response = await fetch('/api/metrics');
        const data = await response.json();
        document.getElementById('global-rps').textContent = data.global_rps.toFixed(3);
        document.getElementById('cpu').textContent = `${data.cpu_percent.toFixed(1)}%`;
        document.getElementById('memory').textContent = `${data.memory_percent.toFixed(1)}%`;
        document.getElementById('uptime').textContent = formatUptime(data.uptime_seconds);
        document.getElementById('baseline').textContent = JSON.stringify(data.global_baseline, null, 2);
        document.getElementById('hourly').textContent = JSON.stringify(data.hourly_slots, null, 2);
        const hourlyEntries = Object.entries(data.hourly_slots);
        const maxValue = hourlyEntries.reduce((max, [, value]) => Math.max(max, value), 1);
        document.getElementById('chart').innerHTML = hourlyEntries.map(([hour, value]) => {
          const label = hour.slice(11, 16);
          const height = Math.max((value / maxValue) * 180, 6);
          return `<div class="bar-wrap"><div class="bar" style="height:${height}px"></div><div>${value.toFixed(2)}</div><div class="bar-label">${label}</div></div>`;
        }).join('');
        document.getElementById('top-ips').innerHTML = data.top_ips.map(item =>
          `<tr><td>${item.ip}</td><td>${item.total}</td><td>${item.rate.toFixed(3)}</td></tr>`).join('');
        document.getElementById('banned').innerHTML = data.banned_ips.map(item =>
          `<tr><td class="danger">${item.ip}</td><td>${item.reason}</td><td>${item.release_at}</td></tr>`).join('');
      }
      refresh();
      setInterval(refresh, 3000);
    </script>
  </body>
</html>
"""

        @self.app.get("/api/metrics")
        def metrics():
            payload = self.state.get_metrics()
            baseline = payload["global_baseline"]
            baseline_payload = None
            if baseline is not None:
                baseline_payload = {
                    "mean_rps": baseline.mean_rps,
                    "stddev_rps": baseline.stddev_rps,
                    "error_rate": baseline.error_rate,
                    "sample_count": baseline.sample_count,
                    "computed_at": baseline.computed_at,
                    "source": baseline.source,
                }

            return jsonify(
                {
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "hostname": os.uname().nodename,
                    "global_rps": payload["global_rps"],
                    "uptime_seconds": payload["uptime_seconds"],
                    "top_ips": payload["top_ips"],
                    "banned_ips": payload["banned_ips"],
                    "global_baseline": baseline_payload,
                    "hourly_slots": self.baseline_manager.get_hourly_means("global"),
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "memory_percent": psutil.virtual_memory().percent,
                }
            )

    def run(self, host: str, port: int) -> None:
        self.app.run(host=host, port=port, debug=False, use_reloader=False)
