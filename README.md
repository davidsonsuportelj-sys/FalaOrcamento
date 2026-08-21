# FalaOrçamento v1.6.21 — Groq corrigida

Correções:
- IA deve preservar o nome específico dos serviços/produtos na descrição dos itens;
- instrução explícita para não retornar descrições genéricas como “Serviço” quando houver descrição no texto;
- status técnico “IA local indisponível” removido da experiência principal;
- diagnóstico da IA permanece disponível pelo backend `/api/ai/status`;
- PostgreSQL, Google Login, Brevo/SMTP, PDF, PWA e logout preservados.

Render Start Command:
`gunicorn backend.app:app`
