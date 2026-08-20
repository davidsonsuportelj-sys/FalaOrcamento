# FalaOrçamento v1.6.18 — Git/Render

Pacote de deploy para Render.

## Start
`gunicorn backend.app:app`

## v1.6.18
- sessão atual mostra usuário/empresa/e-mail;
- botão explícito `Sair da conta`;
- logout retorna para a tela de login;
- PostgreSQL, SMTP, Google Login e links públicos preservados.

## Google Auth dependency fix

O pacote inclui `google-auth` e `google-auth-oauthlib`, necessários para validar
o token do botão "Continuar com o Google" no backend em produção.
