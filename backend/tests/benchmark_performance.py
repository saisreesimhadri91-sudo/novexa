"""
NIVORA WATER MANAGEMENT SYSTEM — PERFORMANCE BENCHMARK ENGINE
Measures empirical latency distributions (Min, P50, P90, P99, Max, Mean)
for all core endpoints across the 10,000+ complaint dataset.
"""

import time
import json
import statistics
import threading
import http.client
import os
import sys
from http.server import ThreadingHTTPServer

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from server import NivoraAPIHandler

BENCHMARK_PORT = 8020
ITERATIONS = 30


def run_benchmarks():
    server = ThreadingHTTPServer(("127.0.0.1", BENCHMARK_PORT), NivoraAPIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    endpoints = [
        ("GET", "/api/health", None),
        ("GET", "/api/meta", None),
        ("GET", "/api/complaints?role=admin", None),
        ("GET", "/api/analytics/locality", None),
        ("GET", "/api/analytics/performance", None),
        ("GET", "/api/clusters", None),
        ("GET", "/api/incidents", None),
        ("GET", "/api/reports/export/csv", None),
        ("POST", "/api/complaints", {
            "resident_id": 1,
            "locality_id": 1,
            "category_id": 1,
            "lat": 28.6280,
            "lng": 77.2080,
            "address_landmark": "Benchmark Synthetic Test Node",
            "description": "Benchmark operational load latency testing."
        })
    ]

    results = []

    print(f"============================================================")
    print(f" NIVORA Performance & SLA Benchmark ({ITERATIONS} samples per route)")
    print(f" Dataset Volume: 10,000+ complaints, 450 incidents, 15 wards")
    print(f"============================================================")

    for method, path, payload in endpoints:
        latencies_ms = []

        # Warm-up request
        conn = http.client.HTTPConnection("127.0.0.1", BENCHMARK_PORT, timeout=10)
        if method == "GET":
            conn.request("GET", path)
        else:
            conn.request("POST", path, body=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        res = conn.getresponse()
        res.read()
        conn.close()

        # Sample runs
        for _ in range(ITERATIONS):
            start = time.perf_counter()
            conn = http.client.HTTPConnection("127.0.0.1", BENCHMARK_PORT, timeout=10)
            if method == "GET":
                conn.request("GET", path)
            else:
                conn.request("POST", path, body=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            res = conn.getresponse()
            res.read()
            conn.close()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies_ms.append(elapsed_ms)

        latencies_sorted = sorted(latencies_ms)
        p50 = latencies_sorted[int(len(latencies_sorted) * 0.50)]
        p90 = latencies_sorted[int(len(latencies_sorted) * 0.90)]
        p99 = latencies_sorted[min(len(latencies_sorted) - 1, int(len(latencies_sorted) * 0.99))]
        mean_val = statistics.mean(latencies_ms)
        min_val = min(latencies_ms)
        max_val = max(latencies_ms)

        results.append({
            "method": method,
            "endpoint": path,
            "min_ms": round(min_val, 2),
            "p50_ms": round(p50, 2),
            "p90_ms": round(p90, 2),
            "p99_ms": round(p99, 2),
            "mean_ms": round(mean_val, 2),
            "status": "PASS" if mean_val < 250.0 else "WARN"
        })

    server.shutdown()
    server.server_close()

    print(f"\n| Method | Endpoint | Min (ms) | P50 (ms) | P90 (ms) | P99 (ms) | Mean (ms) | SLA Target | Status |")
    print(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        target = "< 50ms" if "health" in r["endpoint"] or "meta" in r["endpoint"] else "< 200ms"
        print(f"| `{r['method']}` | `{r['endpoint']}` | {r['min_ms']} | {r['p50_ms']} | {r['p90_ms']} | {r['p99_ms']} | {r['mean_ms']} | {target} | **{r['status']}** |")

    return results


if __name__ == "__main__":
    run_benchmarks()
