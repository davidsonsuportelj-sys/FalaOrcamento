# FalaOrçamento v0.7 — pronto para publicação

Base visual: v0.6.3 aprovada.

## Principais mudanças

- Backend migrado para Flask.
- Banco compatível com PostgreSQL.
- SQLite continua disponível para testes locais.
- Blueprint `render.yaml` pronto para Render.
- `requirements.txt` incluído.
- Gunicorn configurado para produção.
- Login administrativo por senha.
- Histórico e cadastro do prestador protegidos por sessão.
- Orçamento público continua acessível por token individual.
- Cliente pode aceitar/recusar sem acessar a área administrativa.
- Cache desativado para evitar o problema que ocorreu nas versões anteriores.

## Teste local

Windows:
`INICIAR_LOCAL.bat`

A senha local padrão é:
`admin`

Abra:
`http://localhost:8000`

## Publicação

Leia:
`DEPLOY_RENDER.md`

## Observação

O plano gratuito do Render é indicado somente para validar o MVP. A configuração de produção pode ser atualizada depois sem alterar o design ou o fluxo do FalaOrçamento.
