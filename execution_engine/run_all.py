"""Unified local runner for the API and background services."""

import argparse
import logging
import signal
import threading
import time

import uvicorn

from execution_engine.api.main import app as api_app
from execution_engine.container import execution_repository, execution_service
from execution_engine.executor.executor import Executor
from execution_engine.health_checker.checker import HealthChecker
from execution_engine.run_retry_worker import RetryWorker
from execution_engine.status_updater.updater import StatusUpdater

logger = logging.getLogger(__name__)


class ManagedUvicorn:
    """Run a uvicorn server in a managed thread."""

    def __init__(self, app, host: str, port: int, name: str):
        self.name = name
        self.config = uvicorn.Config(app, host=host, port=port, log_level="info")
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, name=name, daemon=True)

    def start(self):
        logger.info("Starting %s", self.name)
        self.thread.start()

    def stop(self):
        logger.info("Stopping %s", self.name)
        self.server.should_exit = True
        self.thread.join(timeout=10)


class ThreadedService:
    """Run a blocking service.start method in a managed thread."""

    def __init__(self, service, name: str):
        self.service = service
        self.name = name
        self.thread = threading.Thread(target=service.start, name=name, daemon=True)

    def start(self):
        logger.info("Starting %s", self.name)
        self.thread.start()

    def stop(self):
        logger.info("Stopping %s", self.name)
        if hasattr(self.service, "stop"):
            self.service.stop()
        self.thread.join(timeout=10)


def build_services(args):
    services = []

    if args.api:
        services.append(ManagedUvicorn(api_app, args.host, args.api_port, "api"))

    if args.runtime_agent:
        from runtime_agent.server import app as runtime_agent_app

        services.append(
            ManagedUvicorn(
                runtime_agent_app,
                args.host,
                args.runtime_agent_port,
                "runtime-agent",
            )
        )

    if args.workers:
        executor = Executor(
            executor_id=args.executor_id,
            service=execution_service,
            repository=execution_repository,
            poll_interval=args.executor_poll_interval,
            max_slots=args.executor_slots,
            lease_seconds=args.lease_seconds,
        )
        services.append(executor)
        services.append(ThreadedService(StatusUpdater(poll_interval=args.status_poll_interval), "status-updater"))
        services.append(
            ThreadedService(
                HealthChecker(
                    check_interval=args.health_check_interval,
                    failure_threshold=args.health_failure_threshold,
                    restart_delay=args.health_restart_delay,
                ),
                "health-checker",
            )
        )
        services.append(ThreadedService(RetryWorker(poll_interval=args.retry_poll_interval), "retry-worker"))

    return services


def parse_args():
    parser = argparse.ArgumentParser(description="Run local App-as-Service components.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--runtime-agent-port", type=int, default=9000)

    parser.add_argument("--api", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--workers", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--runtime-agent", action=argparse.BooleanOptionalAction, default=False)

    parser.add_argument("--executor-id", default="worker-1")
    parser.add_argument("--executor-slots", type=int, default=2)
    parser.add_argument("--executor-poll-interval", type=float, default=2.0)
    parser.add_argument("--lease-seconds", type=int, default=30)

    parser.add_argument("--status-poll-interval", type=int, default=5)
    parser.add_argument("--health-check-interval", type=int, default=10)
    parser.add_argument("--health-failure-threshold", type=int, default=3)
    parser.add_argument("--health-restart-delay", type=int, default=60)
    parser.add_argument("--retry-poll-interval", type=int, default=5)
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    args = parse_args()
    services = build_services(args)
    stop_requested = threading.Event()

    def request_stop(signum, frame):
        logger.info("Received signal %s, shutting down", signum)
        stop_requested.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    for service in services:
        service.start()

    logger.info("Local runner started. API: http://%s:%s/ui/applications", args.host, args.api_port)

    try:
        while not stop_requested.is_set():
            time.sleep(1)
    finally:
        for service in reversed(services):
            try:
                service.stop()
            except Exception:
                logger.exception("Error stopping service")


if __name__ == "__main__":
    main()
