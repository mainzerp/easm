"""Step definitions for the scan pipeline.

Each step knows how to build its argv (command steps) or its action
(python steps) from a context dict: {"out_dir": str, "domains": list[str],
"cfg": dict}. A ``post`` hook may post-process output files after a
successful run.
"""

import os
import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class StepDefinition:
    key: str
    title: str
    kind: str  # "command" | "python"
    build: Callable[[dict], object]  # ctx -> argv list (command) | zero-arg callable (python)
    timeout_s: int  # 0 = no timeout
    output_file: str
    critical: bool = False
    skip_if: Callable[[dict], str | None] = lambda ctx: None
    counter_key: str | None = None
    post: Callable[[dict], None] | None = None


def _out(ctx: dict, name: str) -> str:
    return os.path.join(ctx["out_dir"], name)


def _is_empty(ctx: dict, name: str) -> bool:
    path = _out(ctx, name)
    if not os.path.exists(path):
        return True
    with open(path, errors="replace") as f:
        return not any(line.strip() for line in f)


def _skip_when_empty(filename: str) -> Callable[[dict], str | None]:
    def check(ctx: dict) -> str | None:
        if _is_empty(ctx, filename):
            return f"{filename} is empty"
        return None

    return check


def subfinder_step() -> StepDefinition:
    def build(ctx: dict) -> list[str]:
        argv = ["subfinder"]
        for d in ctx["domains"]:
            argv += ["-d", d]
        argv += ["-silent", "-o", _out(ctx, "subdomains.txt")]
        return argv

    return StepDefinition(
        key="subfinder",
        title="Subdomain Discovery",
        kind="command",
        build=build,
        timeout_s=300,
        output_file="subdomains.txt",
        critical=True,
        counter_key="subdomains",
    )


def _merge_alterx(ctx: dict) -> None:
    """Merge alterx.txt into subdomains.txt (dedup, sorted)."""
    names = set()
    for fname in ("subdomains.txt", "alterx.txt"):
        path = _out(ctx, fname)
        if os.path.exists(path):
            with open(path, errors="replace") as f:
                names.update(line.strip() for line in f if line.strip())
    with open(_out(ctx, "subdomains.txt"), "w") as f:
        for name in sorted(names):
            f.write(name + "\n")


def alterx_step() -> StepDefinition:
    def build(ctx: dict) -> list[str]:
        return [
            "alterx",
            "-l",
            _out(ctx, "subdomains.txt"),
            "-silent",
            "-o",
            _out(ctx, "alterx.txt"),
        ]

    return StepDefinition(
        key="alterx",
        title="Subdomain Permutation",
        kind="command",
        build=build,
        timeout_s=300,
        output_file="alterx.txt",
        skip_if=_skip_when_empty("subdomains.txt"),
        post=_merge_alterx,
    )


def dnsx_step() -> StepDefinition:
    def build(ctx: dict) -> list[str]:
        return [
            "dnsx",
            "-l",
            _out(ctx, "subdomains.txt"),
            "-silent",
            "-o",
            _out(ctx, "resolved.txt"),
        ]

    return StepDefinition(
        key="dnsx",
        title="DNS Resolution",
        kind="command",
        build=build,
        timeout_s=300,
        output_file="resolved.txt",
        critical=True,
        skip_if=_skip_when_empty("subdomains.txt"),
        counter_key="resolved",
    )


def httpx_step() -> StepDefinition:
    def build(ctx: dict) -> list[str]:
        return [
            "httpx-pd",
            "-l",
            _out(ctx, "resolved.txt"),
            "-silent",
            "-title",
            "-status-code",
            "-tech-detect",
            "-o",
            _out(ctx, "http-results.txt"),
        ]

    return StepDefinition(
        key="httpx",
        title="HTTP Probing",
        kind="command",
        build=build,
        timeout_s=300,
        output_file="http-results.txt",
        skip_if=_skip_when_empty("resolved.txt"),
        counter_key="http",
    )


def extract_urls_step() -> StepDefinition:
    def build(ctx: dict) -> Callable[[], None]:
        def action() -> None:
            urls = set()
            path = _out(ctx, "http-results.txt")
            if os.path.exists(path):
                with open(path, errors="replace") as f:
                    for line in f:
                        urls.update(re.findall(r"https?://[^ ]+", line))
            with open(_out(ctx, "urls.txt"), "w") as f:
                for url in sorted(urls):
                    f.write(url + "\n")

        return action

    return StepDefinition(
        key="extract_urls",
        title="URL Extraction",
        kind="python",
        build=build,
        timeout_s=0,
        output_file="urls.txt",
    )


def nmap_step() -> StepDefinition:
    def build(ctx: dict) -> list[str]:
        ports = ctx["cfg"].get("ports", "80,443")
        return [
            "nmap",
            "-iL",
            _out(ctx, "resolved.txt"),
            "-p",
            ports,
            "--open",
            "-oN",
            _out(ctx, "ports.txt"),
            "-T4",
        ]

    return StepDefinition(
        key="nmap",
        title="Port Scan",
        kind="command",
        build=build,
        timeout_s=600,
        output_file="ports.txt",
        skip_if=_skip_when_empty("resolved.txt"),
    )


def nuclei_step() -> StepDefinition:
    def build(ctx: dict) -> list[str]:
        severity = ",".join(ctx["cfg"].get("nuclei_severity", ["critical", "high"]))
        return [
            "nuclei",
            "-l",
            _out(ctx, "urls.txt"),
            "-severity",
            severity,
            "-o",
            _out(ctx, "vulns.txt"),
            "-silent",
            "-stats",
            "-stats-interval",
            "30",
        ]

    return StepDefinition(
        key="nuclei",
        title="Vulnerability Scan",
        kind="command",
        build=build,
        timeout_s=1200,
        output_file="vulns.txt",
        skip_if=_skip_when_empty("urls.txt"),
        counter_key="findings",
    )
