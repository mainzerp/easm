"""Pipeline runner: executes scan steps, emits events, returns a ScanOutcome.

DB-free and Redis-free: log/event output goes through the injected
publisher, cancellation through the injected stop_check callable.
"""

import os
import queue
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field

from pipeline.registry import build_steps
from pipeline.steps import StepDefinition

COUNTER_KEYS = ("subdomains", "resolved", "http", "findings")

# Windows lacks SIGKILL; tests run cross-platform.
_SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)


@dataclass
class ScanOutcome:
    status: str  # done | failed | canceled
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)


def _count_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, errors="replace") as f:
        return sum(1 for line in f if line.strip())


def _pump(stream, q: "queue.Queue") -> None:
    """Reader thread: forward stdout lines into the queue; None marks EOF."""
    try:
        for line in iter(stream.readline, ""):
            q.put(line)
    finally:
        q.put(None)


class PipelineRunner:
    POLL_INTERVAL = 0.5
    KILL_GRACE_S = 10

    def __init__(self, scan_id: int, out_dir: str, domains: list[str], cfg: dict, publisher, stop_check):
        self.scan_id = scan_id
        self.out_dir = out_dir
        self.domains = domains
        self.cfg = cfg
        self.publisher = publisher
        self.stop_check = stop_check
        self.counters = {k: 0 for k in COUNTER_KEYS}

    # ── public API ────────────────────────────────────────────────────────

    def run(self) -> ScanOutcome:
        os.makedirs(self.out_dir, exist_ok=True)
        steps = build_steps(self.cfg)
        ctx = {"out_dir": self.out_dir, "domains": self.domains, "cfg": self.cfg}
        total = len(steps)

        for seq, step in enumerate(steps, start=1):
            self._phase(step, "queued", seq, total)
        self.publisher.event({"type": "status", "status": "running", "error": None})
        self._emit_counters()

        warnings: list[str] = []
        for seq, step in enumerate(steps, start=1):
            if self.stop_check():
                self.publisher.event({"type": "status", "status": "canceled", "error": None})
                return self._outcome("canceled", warnings)

            skip_reason = step.skip_if(ctx)
            if skip_reason:
                self._phase(step, "skipped", seq, total, reason=skip_reason)
                self._ensure_output(step)
                self._emit_counters()
                continue

            self._phase(step, "running", seq, total)
            started = time.monotonic()
            error, canceled = self._execute(step, ctx)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self._ensure_output(step)
            self._update_counter(step)

            if canceled:
                self._phase(step, "failed", seq, total, elapsed_ms=elapsed_ms, error="Canceled by user")
                self.publisher.event({"type": "status", "status": "canceled", "error": None})
                return self._outcome("canceled", warnings)

            if error is not None:
                self._phase(step, "failed", seq, total, elapsed_ms=elapsed_ms, error=error)
                if step.critical:
                    self.publisher.event({"type": "status", "status": "failed", "error": error})
                    return self._outcome("failed", warnings, error=error)
                warnings.append(f"{step.key} failed: {error}")
            else:
                self._phase(step, "done", seq, total, elapsed_ms=elapsed_ms)

            self._emit_counters()

        self.publisher.event({"type": "status", "status": "done", "error": None})
        return self._outcome("done", warnings)

    # ── internals ─────────────────────────────────────────────────────────

    def _outcome(self, status: str, warnings: list[str], error: str | None = None) -> ScanOutcome:
        return ScanOutcome(status=status, error=error, warnings=warnings, counters=dict(self.counters))

    def _phase(
        self,
        step: StepDefinition,
        status: str,
        seq: int,
        total: int,
        elapsed_ms: int | None = None,
        reason: str | None = None,
        error: str | None = None,
    ) -> None:
        self.publisher.event(
            {
                "type": "phase",
                "phase": step.key,
                "title": step.title,
                "status": status,
                "seq": seq,
                "total": total,
                "elapsed_ms": elapsed_ms,
                "reason": reason,
                "error": error,
            }
        )

    def _emit_counters(self) -> None:
        self.publisher.event({"type": "counter", "counters": dict(self.counters)})

    def _update_counter(self, step: StepDefinition) -> None:
        if step.counter_key:
            self.counters[step.counter_key] = _count_lines(os.path.join(self.out_dir, step.output_file))

    def _ensure_output(self, step: StepDefinition) -> None:
        """Guarantee the result-file contract even for skipped/failed steps."""
        path = os.path.join(self.out_dir, step.output_file)
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            with open(path, "a"):
                pass
        except OSError:
            pass

    def _execute(self, step: StepDefinition, ctx: dict) -> tuple[str | None, bool]:
        """Returns (error, canceled)."""
        if step.kind == "python":
            try:
                action = step.build(ctx)
                action()
            except Exception as e:
                return f"{type(e).__name__}: {e}", False
            return None, False
        error, canceled = self._run_command(step, ctx)
        if error is None and not canceled and step.post is not None:
            try:
                step.post(ctx)
            except Exception as e:
                return f"post-hook failed: {type(e).__name__}: {e}", False
        return error, canceled

    def _run_command(self, step: StepDefinition, ctx: dict) -> tuple[str | None, bool]:
        argv = step.build(ctx)
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        q: queue.Queue = queue.Queue()
        threading.Thread(target=_pump, args=(proc.stdout, q), daemon=True).start()
        deadline = time.monotonic() + step.timeout_s if step.timeout_s else None

        canceled = False
        failure = None
        while True:
            try:
                item = q.get(timeout=self.POLL_INTERVAL)
            except queue.Empty:
                item = ""
            if item:
                self.publisher.log(item.rstrip())
            if self.stop_check():
                canceled = True
                self._kill_process(proc)
                break
            if deadline is not None and time.monotonic() > deadline:
                failure = f"timeout after {step.timeout_s}s"
                self._kill_process(proc)
                break
            if item is None and proc.poll() is not None:
                break
        proc.wait()

        if canceled:
            return None, True
        if failure is not None:
            return failure, False
        if proc.returncode != 0:
            return f"exit code {proc.returncode}", False
        return None, False

    def _kill_process(self, proc) -> None:
        """SIGTERM the process group, SIGKILL after a grace period."""
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=self.KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), _SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            proc.wait()
