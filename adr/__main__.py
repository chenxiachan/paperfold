"""PaperFold.

  python -m adr serve [--port 3017]                 the local app (landing, sidebar, reader)
  python -m adr <arxiv id or url> [--lang zh] ...   generate from the command line, then export
  python -m adr export <arxiv id>                   one self-contained HTML file in out/<id>/
"""
import argparse
import sys
import time

from . import build, pipeline


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        ap = argparse.ArgumentParser(prog="adr serve")
        ap.add_argument("--port", type=int, default=3017)
        a = ap.parse_args(sys.argv[2:])
        from .server import serve
        return serve(a.port)
    if len(sys.argv) > 1 and sys.argv[1] == "export":
        print(build.export(sys.argv[2]))
        return
    ap = argparse.ArgumentParser(prog="adr", description="Generate a zoomable reader for an arXiv paper.")
    ap.add_argument("paper", help="arXiv id or URL, e.g. 2512.23916")
    ap.add_argument("--lang", action="append", default=[], help="also generate this language (zh, ja, es, ...); repeatable")
    ap.add_argument("--model", default="sonnet", help="model alias for `claude -p` (default: sonnet)")
    ap.add_argument("--jobs", type=int, default=4, help="parallel model calls")
    ap.add_argument("--force", action="store_true", help="regenerate (ignore what is stored and cached)")
    a = ap.parse_args()
    t0 = time.time()
    pid = None
    for lang in ["en"] + a.lang:
        pid = pipeline.generate(a.paper, lang, a.model, force=a.force, jobs=a.jobs, log=print,
                                progress=lambda s, d, t: print(f"  {s} {d}/{t}", end="\r"))
    print(f"\n  → {build.export(pid)}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
