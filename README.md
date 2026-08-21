# FalaOrçamento v1.6.19 — Git/Render

Correção de acabamento da área **Negócio / Conta**.

## Ajustes
- removido o bloco duplicado `Sessão atual`;
- removido o botão duplicado `Sair da conta`;
- mantido o botão original `SAIR DA CONTA`;
- dados de responsável, empresa, e-mail e tipo de acesso permanecem na área `Conta e empresa`;
- Google Login, PostgreSQL, SMTP/Brevo, PWA e links públicos preservados.

## Render
Start command:

`gunicorn backend.app:app`
