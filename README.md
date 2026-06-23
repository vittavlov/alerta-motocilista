# Alerta Motociclista Bot (`@AlertaMotoBot`)

O **Alerta Motociclista** é um bot de monitoramento climático automatizado para o Telegram, desenvolvido com o objetivo de auxiliar na segurança de motociclistas. O sistema monitora condições meteorológicas severas em tempo real e envia alertas preventivos automáticos para os usuários cadastrados de acordo com a cidade de preferência.

## 🚀 Funcionalidades

* **Cadastro Multi-Cidades:** Permite que o motociclista se cadastre em uma ou mais cidades para receber alertas segmentados.
* **Monitoramento em Segundo Plano:** Motor de checagem automatizado que consome dados meteorológicos periodicamente.
* **Comandos Intuitivos:** Fluxo simplificado de conversa, incluindo comandos como `/sair` para cancelamento de inscrição.
* **Persistência Confiável:** Armazenamento seguro de dados na nuvem para garantir a consistência das preferências dos usuários.

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.12
* **Framework de Bot:** `pyTelegramBotAPI`
* **Concorrência:** `Threading` (para rodar a escuta do bot em paralelo com a rotina de checagem do clima)
* **APIs Consumidas:** OpenWeather API e INMET (Instituto Nacional de Meteorologia)
* **Banco de Dados:** PostgreSQL (Hospedado no Supabase)
* **Infraestrutura / Cloud:** Render (Hospedagem da aplicação)

## 🏗️ Arquitetura do Sistema

O projeto foi estruturado seguindo boas práticas de divisão de responsabilidades:

* `main.py`: Ponto de entrada que gerencia a inicialização e as conexões principais.
* `bottelegram.py`: Lógica de comandos e fluxo de interação com a API do Telegram.
* `clima.py` e `alertas.py`: Integração com as APIs externas de meteorologia.
* `notificador.py`: Motor interno responsável pelo envio assíncrono das notificações.

---
*Projeto desenvolvido como parte dos meus estudos práticos em Engenharia de Software e Banco de Dados.*
https://www.linkedin.com/in/vitoria-m-silva
