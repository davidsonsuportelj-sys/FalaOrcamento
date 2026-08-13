# Publicar o FalaOrçamento v0.7 no Render

Esta versão foi preparada para publicação pública com:

- Flask + Gunicorn
- PostgreSQL no Render
- HTTPS fornecido pelo Render
- senha administrativa
- links públicos individuais para cada orçamento
- SQLite como fallback apenas para teste local

## 1. Criar um repositório no GitHub

Crie um repositório vazio, por exemplo `falaorcamento`, e envie **os arquivos desta pasta para a raiz do repositório**.

O arquivo `render.yaml` precisa ficar na raiz.

## 2. Criar a publicação no Render

No painel do Render:

1. Escolha **New > Blueprint**.
2. Conecte sua conta do GitHub.
3. Selecione o repositório `falaorcamento`.
4. O Render encontrará o `render.yaml`.
5. Durante a criação, ele solicitará o valor de `ADMIN_PASSWORD`.
6. Escolha uma senha forte e guarde-a.
7. Confirme a criação dos recursos.

O Blueprint cria:
- um Web Service Python;
- um PostgreSQL;
- a variável `DATABASE_URL`;
- uma `SECRET_KEY` aleatória.

## 3. Abrir o sistema

Ao terminar o deploy, o Render fornecerá um endereço semelhante a:

`https://falaorcamento.onrender.com`

Abra o endereço e digite a senha administrativa escolhida.

## 4. Teste externo

1. Cadastre os dados do prestador.
2. Crie um orçamento.
3. Clique em enviar/compartilhar.
4. Copie o link.
5. Abra o link em outro celular usando 4G/5G.

O cliente não precisa da senha administrativa. Ele acessa apenas o orçamento correspondente ao token do link.

## Importante sobre o plano gratuito

O `render.yaml` está configurado para recursos gratuitos apenas para validação do MVP.
Antes de uso comercial real, revise os planos e políticas atuais da hospedagem.
