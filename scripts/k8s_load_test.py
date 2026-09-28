"""
CivicPulse Kubernetes Load Test & HPA Scaling Demonstration Script.

Sends concurrent HTTP requests to trigger Horizontal Pod Autoscaler (HPA v2)
activity and measures throughput, response latencies, and error rates.
Uses Python standard library to ensure zero-dependency portability.
"""

import argparse
import concurrent.futures
import json
import statistics
import sys
import time
import urllib.error
import urllib.request


def make_request(url: str, method: str = "GET", payload: bytes | None = None) -> tuple[int, float]:
    """Execute a single HTTP request and record status code and elapsed latency in milliseconds."""
    req = urllib.request.Request(url, data=payload, method=method)
    if payload:
        req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "CivicPulse-K8s-LoadTest/1.0")

    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            status = resp.status
            resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return status, elapsed_ms


def run_load_test(
    url: str,
    concurrency: int,
    duration_seconds: int,
    method: str = "GET",
    post_payload: dict | None = None,
) -> dict:
    """Run concurrent load test for the given duration."""
    encoded_payload = json.dumps(post_payload).encode("utf-8") if post_payload else None

    print(f"=== CivicPulse Kubernetes HPA Load Test ===")
    print(f"Target URL:    {url}")
    print(f"Concurrency:   {concurrency} workers")
    print(f"Duration:      {duration_seconds} seconds")
    print(f"Method:        {method}")
    print(f"Starting test at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("-" * 50)

    latencies: list[float] = []
    status_counts: dict[int, int] = {}
    total_requests = 0

    end_time = time.time() + duration_seconds
    start_time = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        while time.time() < end_time:
            futures = [
                executor.submit(make_request, url, method, encoded_payload)
                for _ in range(concurrency * 2)
            ]
            for future in concurrent.futures.as_completed(futures):
                status, latency = future.result()
                total_requests += 1
                latencies.append(latency)
                status_counts[status] = status_counts.get(status, 0) + 1

            if total_requests % 500 == 0:
                elapsed = time.perf_counter() - start_time
                current_rps = total_requests / elapsed if elapsed > 0 else 0
                print(f"Progress: {total_requests:5d} reqs completed | {current_rps:6.1f} RPS | Statuses: {dict(status_counts)}")

    total_duration = time.perf_counter() - start_time
    rps = total_requests / total_duration if total_duration > 0 else 0

    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0.0
    p90 = latencies[int(len(latencies) * 0.90)] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    avg = statistics.mean(latencies) if latencies else 0.0

    print("-" * 50)
    print("=== Load Test Summary Results ===")
    print(f"Total Requests:     {total_requests}")
    print(f"Total Duration:     {total_duration:.2f} s")
    print(f"Average Throughput: {rps:.2f} req/s")
    print(f"Status Distribution: {dict(status_counts)}")
    print(f"Latency Avg:        {avg:.2f} ms")
    print(f"Latency P50:        {p50:.2f} ms")
    print(f"Latency P90:        {p90:.2f} ms")
    print(f"Latency P95:        {p95:.2f} ms")
    print(f"Latency P99:        {p99:.2f} ms")
    print(f"Latency Min / Max:  {min(latencies):.2f} ms / {max(latencies):.2f} ms")
    print("=" * 50)

    return {
        "total_requests": total_requests,
        "duration_seconds": total_duration,
        "rps": rps,
        "status_distribution": status_counts,
        "p50_ms": p50,
        "p90_ms": p90,
        "p95_ms": p95,
        "p99_ms": p99,
        "avg_ms": avg,
    }


def main():
    parser = argparse.ArgumentParser(description="CivicPulse K8s HPA Load Test Generator")
    parser.add_argument("--url", default="http://localhost:8000/api/stats", help="Target URL (default: http://localhost:8000/api/stats)")
    parser.add_argument("-c", "--concurrency", type=int, default=25, help="Number of concurrent worker threads (default: 25)")
    parser.add_argument("-d", "--duration", type=int, default=45, help="Duration in seconds (default: 45)")
    parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST"], help="HTTP Method (default: GET)")

    args = parser.parse_args()
    payload = None
    if args.method == "POST":
        payload = {
            "title": "HPA Load Simulation Issue",
            "description": "Load testing civic issue intake for horizontal pod autoscaler verification and metric tracking.",
            "location": "Sector G-9 Islamabad",
        }

    run_load_test(args.url, args.concurrency, args.duration, args.method, payload)


if __name__ == "__main__":
    main()
