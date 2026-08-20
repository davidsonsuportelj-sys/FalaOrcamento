# FalaOrçamento v1.6.17 — Git/Render

Pacote mínimo para o repositório que alimenta o serviço Web no Render.

## Build
`pip install -r requirements.txt`

## Start
`gunicorn backend.app:app`

## Variáveis obrigatórias no Render
- `DATABASE_URL`
- `SECRET_KEY`
- `APP_ENV=production`
- `BOOTSTRAP_ADMIN=false`
- `SESSION_COOKIE_SECURE=true`
- `TRUST_PROXY_HEADERS=true`
- `PUBLIC_APP_URL`

As credenciais reais devem ficar apenas em **Render > Environment** e nunca no Git.

## Não incluído neste pacote
Banco SQLite local, logs, launchers Windows, testes manuais, ferramentas de migração, documentação histórica e arquivos de infraestrutura local.
