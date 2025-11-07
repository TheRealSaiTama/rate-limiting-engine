from flask import Flask, jsonify, request
from prometheus_client import Counter, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from src.token_bucket import is_allowed

app = Flask(__name__)

# Expose Prometheus metrics at /metrics alongside the Flask app
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app,
    {
        "/metrics": make_wsgi_app(),
    },
)

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)


@app.before_request
def before_request() -> None:
    """Apply rate limiting to every request using the caller's IP address."""
    ip = request.remote_addr or "unknown"
    if not is_allowed(ip, max_tokens=100, refill_per_minute=100):
        return jsonify({"error": "Rate limit exceeded"}), 429


@app.route("/api/data", methods=["GET", "POST"])
def protected_endpoint():
    if request.method == "GET":
        http_requests_total.labels("GET", "/api/data", "200").inc()
        return jsonify({"message": "Protected data"})

    if request.method == "POST":
        http_requests_total.labels("POST", "/api/data", "200").inc()
        return jsonify({"status": "created"})


@app.errorhandler(429)
def ratelimit_handler(error):
    http_requests_total.labels("ANY", "ANY", "429").inc()
    return jsonify({"error": str(error)}), 429


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
