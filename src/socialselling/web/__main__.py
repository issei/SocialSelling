"""Entrypoint da UI local: `py -m socialselling.web` → http://127.0.0.1:8000.

Localhost apenas (ADR-002). As chaves de API continuam no .env (nunca na UI).
"""

from __future__ import annotations

import uvicorn

from socialselling.web.app import app


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
