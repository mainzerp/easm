"""Step registry: ordered pipeline steps filtered by config enable flags."""

from pipeline.steps import (
    StepDefinition,
    alterx_step,
    dnsx_step,
    extract_urls_step,
    httpx_step,
    nmap_step,
    nuclei_step,
    subfinder_step,
)


def build_steps(cfg: dict) -> list[StepDefinition]:
    """Return the pipeline steps in execution order for the given config."""
    steps = [subfinder_step()]
    if cfg.get("enable_alterx", False):
        steps.append(alterx_step())
    steps.append(dnsx_step())
    if cfg.get("enable_httpx", True):
        steps.append(httpx_step())
    steps.append(extract_urls_step())
    if cfg.get("enable_nmap", True):
        steps.append(nmap_step())
    if cfg.get("enable_nuclei", True):
        steps.append(nuclei_step())
    return steps
