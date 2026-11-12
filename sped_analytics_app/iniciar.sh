#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || ./instalar.sh
exec .venv/bin/python -m app.main "$@"
