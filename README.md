# FalaOrçamento v1.6.27 — associação robusta de itens

Baseada na v1.6.24 validada no Render. Esta versão preserva autenticação, PostgreSQL, multiempresa, Google OAuth, Brevo, PDF, WhatsApp e PWA.

## Correção principal

O pós-processamento agora usa âncoras fortes da própria fala para associar descrição, quantidade e preço. Ele corrige descrições trocadas ou genéricas quando a sequência numérica confirma o alinhamento e consegue reconstruir item perdido somente quando os preços retornados pela IA formam uma subsequência inequívoca dos preços explicitamente falados.

Também foram adicionados tratamentos para:
- valores com centavos (ex.: 85 reais e 50 centavos);
- preço global de um conjunto (ex.: 5 luminárias, serviço todo por R$ 600 => 1 item de R$ 600);
- material com preço próprio;
- ações como carga de gás, ajuste, montagem, alinhamento e rejunte;
- preservação de autocorreções faladas (ex.: “não, corrigindo…”).

## Regressão

`python tests/test_interpret_regression.py` valida 11 cenários reais: João, Marcos, Roberto, Carlos, Ana, Renato, Fernanda, Gustavo, Patrícia, Lucas e Juliana.

## Deploy

Pacote mínimo para Git/Render. Variáveis de ambiente continuam externas ao ZIP.
