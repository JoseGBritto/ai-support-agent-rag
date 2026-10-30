"""CLI:  python -m supportbot serve | ask "question" | index"""
from __future__ import annotations

import argparse
import json
import logging

from .agent import SupportAgent
from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m supportbot", description="AI support agent (RAG)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="run the web server with the demo page and widget")
    serve.add_argument("--port", type=int, default=8000)
    ask = sub.add_parser("ask", help="ask one question from the terminal")
    ask.add_argument("question")
    sub.add_parser("index", help="show how the knowledge base was split into chunks")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = Settings.from_env()
    if args.cmd == "serve":
        from .server import create_app
        print(f"Open http://localhost:{args.port}  (mode: {'AI' if settings.ai_enabled else 'demo, no API key'})")
        create_app(settings).run(host="0.0.0.0", port=args.port)
    elif args.cmd == "ask":
        print(json.dumps(SupportAgent(settings).ask(args.question, "cli").to_dict(), ensure_ascii=False, indent=2))
    else:
        for c in SupportAgent(settings).chunks:
            print(f"#{c.id:<3} {c.source:<22} {c.title}  ({len(c.text)} chars)")


if __name__ == "__main__":
    main()
