import multiprocessing
import os

bind = os.getenv("BIND", "127.0.0.1:8000")
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
# gevent workers so SSE / streaming passthrough isn't blocked.
worker_class = os.getenv("WORKER_CLASS", "gevent")
timeout = int(os.getenv("TIMEOUT", "60"))
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
