#!/bin/bash
#
# Monta o pacote distribuivel -- o ZIP que se entrega a quem vai usar.
#
# Leva apenas o necessario para rodar: lancadores, instalador, servidor,
# interface ja compilada e o manual. Nao leva codigo-fonte da interface,
# testes, ambiente virtual nem banco: quem usa nao compila nada.
#
# Antes de rodar, garanta que a interface esta compilada e atualizada:
#     cd frontend && npm run build
#
# Uso:
#     ./instalador/montar-pacote.sh [pasta-de-saida]
#
set -e
ORIGEM="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="${1:-$ORIGEM/../dist}"
NOME="sistema-precificacao-reciclagem"

rm -rf "$DESTINO"
mkdir -p "$DESTINO/$NOME"
cd "$DESTINO/$NOME"

# Lancadores e instrucoes
cp "$ORIGEM"/INICIAR-* .
cp "$ORIGEM"/LEIA-ME.txt .

# Instalador
mkdir -p instalador && cp "$ORIGEM/instalador/instalar.py" instalador/

# Servidor: codigo, migracoes e configuracao. Sem testes nem cache.
mkdir -p backend
cp "$ORIGEM/backend/pyproject.toml" "$ORIGEM/backend/alembic.ini" "$ORIGEM/backend/.env.example" backend/
cp -r "$ORIGEM/backend/app" backend/
cp -r "$ORIGEM/backend/alembic" backend/
find backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find backend -name "*.pyc" -delete 2>/dev/null || true

# Interface ja compilada. O codigo-fonte dela nao vai: o usuario nao compila nada.
mkdir -p frontend
cp -r "$ORIGEM/frontend/out" frontend/

# Manual
mkdir -p docs
cp "$ORIGEM/docs/manual-instalacao-e-primeiros-passos.pdf" docs/

chmod +x INICIAR-Mac.command INICIAR-Linux.sh

cd "$DESTINO"
zip -qr "$NOME.zip" "$NOME"
echo "pacote: $DESTINO/$NOME.zip"
du -sh "$NOME.zip" "$NOME"
