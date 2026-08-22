# FalaOrçamento v1.6.30 — confirmação do cliente

Baseada na v1.6.29 validada no Render. Preserva autenticação, PostgreSQL, isolamento multiempresa, Google OAuth, Brevo, Groq/fallback, PDF, WhatsApp e PWA.

## Segurança da resposta pública

O link `/q/{token}` continua público para visualização do orçamento, mas aceitar ou recusar agora exige os 4 últimos dígitos do telefone do cliente cadastrado. A validação ocorre exclusivamente no backend.

- o orçamento armazena apenas um HMAC ligado ao token e aos 4 dígitos, não os 4 dígitos em texto puro;
- 5 tentativas incorretas bloqueiam novas tentativas por 15 minutos;
- orçamentos sem telefone verificável continuam visíveis, porém os botões de decisão ficam indisponíveis;
- novos orçamentos capturam a verificação a partir do cliente cadastrado da mesma `account_id`;
- a API administrativa `/api/quotes/{token}` permanece protegida por autenticação e `account_id`;
- o cliente continua respondendo somente por `/q/{token}/respond`.

## Importante

Orçamentos criados antes da v1.6.30 não possuem a verificação gravada automaticamente. Para validar o novo fluxo, cadastre um cliente com telefone e crie um orçamento novo após o deploy.

## Regressão

O parser e as regras de interpretação não foram alterados nesta versão. O arquivo `tests/test_interpret_regression.py` continua contendo os 11 cenários de regressão já usados nas versões anteriores.

## Deploy

Pacote mínimo para Git/Render. A migração adiciona somente novas colunas à tabela `quotes`, sem apagar ou recriar dados existentes. Variáveis de ambiente continuam externas ao ZIP.
