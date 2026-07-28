# Projeto de Estudo: Web Scraping

Este repositório contém um projeto experimental desenvolvido em Python. O objetivo principal foi estudar e aplicar técnicas de extração de dados (Web Scraping) em páginas web governamentais, integrando o resultado a um sistema de notificações via Discord.

## Escopo do Estudo
O script foi construído para monitorar e extrair dados específicos das seguintes fontes:
* **STN (Secretaria do Tesouro Nacional):** Mapeamento e validação no portal SICONFI.
* **TCE-SP (Tribunal de Contas do Estado de São Paulo):** Busca por atualizações de Planos de Contas e Demonstrativos do portal Audesp, com agrupamento.

## Conceitos e Desafios Abordados
Durante o desenvolvimento, foram praticados os seguintes conceitos técnicos:
* **Navegação no DOM:** Uso da biblioteca `BeautifulSoup` para localizar blocos de texto, lidando com variações de estrutura HTML e elementos ocultos.
* **Expressões Regulares (Regex):** Criação de padrões para identificar anos, datas e controle de versionamento diretamente no texto bruto.
* **Gerenciamento de Estado:** Criação de uma rotina de leitura e gravação em um arquivo local (`historico.json`) para registrar o processamento e evitar dados duplicados.
* **Automação e CI/CD:** Configuração de um fluxo no **GitHub Actions** para rodar o script periodicamente e realizar o *commit* automático do estado atualizado.
* **Boas Práticas de Segurança:** Ocultação de dados sensíveis isolando a URL de integração do Discord por meio de variáveis de ambiente (Secrets).

## Tecnologias
* Python 3.14
* BeautifulSoup4
* Requests
* GitHub Actions
