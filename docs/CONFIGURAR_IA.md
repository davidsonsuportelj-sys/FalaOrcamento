# Ativar a IA no FalaOrçamento v0.8

A chave fica somente no backend do Render. Nunca coloque a chave no `app.js` ou `index.html`.

## Render
1. Abra o Web Service do FalaOrçamento.
2. Vá em Environment.
3. Adicione `OPENAI_API_KEY` com sua chave da API.
4. Confirme `OPENAI_MODEL` como `gpt-5-mini`.
5. Salve e faça novo deploy.

O sistema tenta a IA primeiro. Se a API estiver indisponível ou sem chave, usa automaticamente o interpretador local.

## Teste
Fale/digite:
`Fui na casa de João troquei a porta dele 50 reais`

Esperado:
- Cliente: João
- Troca de porta
- Qtd. 1
- Unitário R$ 50
- Total R$ 50

Outro teste:
`Ontem fui no Gabriel, troquei duas telhas que ficaram 15 reais cada, gastei 80 de material e cobrei mais 150 da mão de obra.`

A IA deve estruturar os itens sem exigir uma frase padrão.
