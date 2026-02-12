from __future__ import annotations

import argparse
import json
import time

from daemon.config import DaemonConfig
from daemon.service import JarvisDaemon
from daemon.supervisor import start_daemon, status_daemon, stop_daemon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JARVIS automation daemon CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("start", "stop", "status"):
        sub.add_parser(name)

    sub.add_parser("dry-run")
    run_loop = sub.add_parser("run-loop")
    run_loop.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "start":
        config = DaemonConfig.from_env(dry_run=False)
        print(start_daemon(config))
        return 0

    if args.command == "stop":
        config = DaemonConfig.from_env(dry_run=False)
        print(stop_daemon(config))
        return 0

    if args.command == "status":
        config = DaemonConfig.from_env(dry_run=False)
        print(status_daemon(config))
        return 0

    if args.command == "dry-run":
        config = DaemonConfig.from_env(dry_run=True)
        daemon = JarvisDaemon(config)
        daemon.start()
        print(json.dumps(daemon.status().__dict__, ensure_ascii=True))
        # Keep command-line dry-run short and non-blocking.
        daemon.stop()
        return 0

    if args.command == "run-loop":
        config = DaemonConfig.from_env(dry_run=bool(args.dry_run))
        daemon = JarvisDaemon(config)
        daemon.start()
        try:
            while True:
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            daemon.stop()
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
