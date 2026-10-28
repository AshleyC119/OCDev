"""Translation pipeline: ordered mapping steps producing CLI blocks.

The order mirrors the structure of the paired native CLI reference supplied for
development: global objects first, then per-interface feature passes, then
system/telemetry service blocks.  Each step adds one or more ``system-view``
blocks to the context emitter.
"""
from . import sections


def translate(doc, report):
    """Run all mapping steps. Returns the Ctx containing completed groups."""
    from .context import Ctx
    ctx = Ctx(doc, report)
    for step in sections.STEPS:
        step(ctx)
    return ctx


def render_groups(ctx):
    from .emitter import render
    return render(ctx.groups)
