from config import settings

# Broker usa DB 0, results usa DB 1
broker_url = settings.redis_uri
result_backend = settings.redis_uri.rstrip("/0") + "/1"

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

timezone = "UTC"
enable_utc = True

# Acknowledge task only after it completes (not on delivery)
task_acks_late = True
worker_prefetch_multiplier = 1

# Separate queues per concern
task_routes = {
    "tasks.ingest.*":   {"queue": "ingest"},
    "tasks.validate.*": {"queue": "validate"},
    "tasks.load.*":     {"queue": "load"},
    "tasks.pipeline.*": {"queue": "pipeline"},
}
task_default_queue = "default"

# Result expiry: 24 h
result_expires = 86_400

# Max task retries / backoff
task_max_retries = 3
task_retry_backoff = True
task_retry_backoff_max = 600   # cap at 10 min
task_retry_jitter = True
