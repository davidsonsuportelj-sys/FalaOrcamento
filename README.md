# FalaOrçamento v1.6.20 — Groq AI

Integração Groq no interpretador já existente. Com `GROQ_API_KEY` configurada, `/api/interpret` usa Groq; sem ela, preserva Ollama como fallback. A chave permanece somente no Render.

Modelo padrão: `openai/gpt-oss-20b`.
Mantidos: PostgreSQL, Google Login, SMTP/Brevo, logout, PDF, PWA e links públicos.

Start: `gunicorn backend.app:app`
