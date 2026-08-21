# FalaOrçamento v1.6.24 — correção determinística das descrições

A v1.6.22 não reconhecia construções nominais como:
- `instalação de 3 tomadas a 80 reais cada`
- `troca de disjuntor por 150 reais`

A v1.6.24 corrige isso no backend, depois da resposta da IA:
- preserva quantidade e valor;
- substitui somente descrições genéricas;
- reconhece `instalação de`, `troca de`, `limpeza de`, `pintura de`, `reparo de`,
  reposicionamento e formas verbais equivalentes;
- não depende de a Groq obedecer ao prompt.

Teste automatizado incluído confirmou:
`Cliente João, instalação de 3 tomadas a 80 reais cada e troca de disjuntor por 150 reais`
=> `Instalação de tomadas` + `Troca de disjuntor`.

O status técnico foi retirado do cabeçalho comercial.
