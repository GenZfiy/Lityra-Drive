import multiprocessing
import os

bind = os.getenv("BIND", "127.0.0.1:8001")
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
timeout = int(os.getenv("TIMEOUT", "30"))
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
