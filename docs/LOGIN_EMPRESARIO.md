# Login do empresário — v0.9

A área administrativa agora possui login próprio com:

- E-mail
- Senha
- Mostrar/ocultar senha
- Identidade visual do FalaOrçamento
- Sessão protegida no backend

## Variáveis no Render

Adicione:

`ADMIN_EMAIL`
`ADMIN_PASSWORD`

Exemplo para teste:

`ADMIN_EMAIL=empresario@falaorcamento.com`

Use uma senha forte em `ADMIN_PASSWORD`.

## Observação

A recuperação automática de senha ainda não foi implementada. Nesta versão, o botão "Esqueci minha senha" apenas informa que a redefinição deve ser feita pelo administrador.
