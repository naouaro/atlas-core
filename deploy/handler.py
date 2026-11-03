"""AWS Lambda entrypoint — a thin wrapper over your sync job's run().

Keep the handler trivial: the SAME run() is used for the one-time backfill and the
scheduled delta, so the two never drift. atlas.sync() is incremental (re-embeds only
changed/new, prunes deletes), so each scheduled invocation finishes fast and fits
inside the 15-min Lambda ceiling.
"""
from sync_job import run


def handler(event, context):
    stats = run()
    return {"ok": True, "stats": {str(k): v for k, v in (stats or {}).items()}}
