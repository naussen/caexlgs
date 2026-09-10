# 🏢 CAEXLGS - Guia Prático de Instalação e Uso

> **Plataforma de Consulta de CNPJ, Grafos de Relacionamentos Societários, Mapeamento de Contatos, Avaliação de Risco e Emissão de Dossiês Investigativos.**

Este guia foi elaborado **passo a passo para qualquer pessoa (mesmo sem conhecimento técnico de programação)** conseguir instalar e rodar o aplicativo no Windows em poucos minutos.

---

## 📋 Pré-requisitos Básicos

Você precisará de apenas **duas coisas** instaladas no seu computador:
1. **Python** (versão 3.10 ou superior)
2. **Git** (opcional, para baixar ou atualizar o código facilmente)

---

## 🚀 Passo 1: Como Instalar o Python no Windows

1. Acesse o site oficial do Python: 👉 **[https://www.python.org/downloads/](https://www.python.org/downloads/)**
2. Clique no botão amarelo **"Download Python 3.x.x"**.
3. Abra o arquivo instalador que foi baixado (ex.: `python-3.13.x-amd64.exe`).
4. ⚠️ **MUITO IMPORTANTE (NÃO PULE ESTE DETALHE):**
   - Na primeira tela do instalador, **MARQUE A CAIXINHA**:
     - `[X] Add python.exe to PATH` (Adicionar python.exe ao PATH)
   - Se essa caixinha não for marcada, o Windows não reconhecerá os comandos do Python!
5. Clique em **"Install Now"** e aguarde a barra concluir.
6. Ao final, se aparecer uma opção *"Disable path length limit"*, clique nela e depois em **"Close"**.

---

## 📥 Passo 2: Baixar o Projeto

Existem duas formas fáceis de ter os arquivos no seu computador:

### Opção A (Mais fácil — Sem Git):
1. Acesse o repositório no GitHub: 👉 **[https://github.com/naussen/caexlgs](https://github.com/naussen/caexlgs)**
2. Clique no botão verde **`<> Code`** e depois em **`Download ZIP`**.
3. Extraia a pasta baixada para onde preferir (ex.: `Documentos\caexlgs`).

### Opção B (Usando Git via Terminal):
Abra o **Prompt de Comando (CMD)** ou o **PowerShell** e digite:
```bash
git clone https://github.com/naussen/caexlgs.git
cd caexlgs
```

---

## 📦 Passo 3: Instalar as Bibliotecas Necessárias

Abra o **Prompt de Comando (CMD)** ou **PowerShell**, navegue até a pasta do projeto e execute o comando abaixo:

```bash
pip install -r cnpjpw/local_app/requirements.txt
```

O instalador baixará automaticamente todas as bibliotecas necessárias:
* `streamlit` (interface web interativa)
* `google-cloud-bigquery` e `db-dtypes` (conexão com a nuvem)
* `pyvis` e `networkx` (motor de grafos de relacionamentos)
* `reportlab` (geração de relatórios em PDF)
* `openpyxl` (geração de planilhas em Excel)

---

## ☁️ Passo 4: Como Configurar o Acesso ao Google BigQuery (Gratuito)

O Google Cloud oferece **1 TB de consultas gratuitas todo mês** no BigQuery. Para ter sua chave privada e ativar o **Modo Sigilo Total**:

1. Acesse o **[Google Cloud Console](https://console.cloud.google.com/)** e faça login com uma conta Google.
2. No topo da tela, clique no seletor de projetos e em **"Novo Projeto"**.
3. Dê um nome (ex: `consulta-cnpj`) e anote o **ID do Projeto** (ex: `consulta-cnpj-123456`).
4. No menu lateral esquerdo (☰), vá em **IAM e administração** > **Contas de serviço**.
5. Clique em **"+ Criar conta de serviço"**:
   - Nome: `app-cnpj`
   - Clique em **Criar e Continuar**.
   - No campo de Papel/Função, selecione: **BigQuery** ➔ **Usuário de trabalho do BigQuery** (*BigQuery Job User*).
   - Clique em **Concluir**.
6. Na lista de contas de serviço, clique na conta que você acabou de criar (`app-cnpj@...`).
7. Vá na aba **Chaves** > **Adicionar Chave** > **Criar nova chave** > Escolha **JSON** e clique em **Criar**.
8. O arquivo `.json` será baixado para o seu computador. Salve-o em uma pasta segura (ex.: `C:\Users\SeuUsuario\Documents\caexlgs\gcp-key.json`).

---

## 🖥️ Passo 5: Como Iniciar o Aplicativo

### Método com 1 Clique (Mais Fácil):
Dê um clique duplo no arquivo executável:
👉 **`iniciar_app.bat`**

### Método via Linha de Comando:
Abra o Prompt de Comando na pasta do projeto e digite:
```bash
streamlit run cnpjpw/local_app/app.py
```

O aplicativo abrirá automaticamente uma página no seu navegador padrão (`http://localhost:8501`).

---

## ⚙️ Configuração Inicial no Aplicativo (Feita apenas 1 vez)

1. Na barra lateral esquerda do aplicativo, em **⚙️ Conexões & Dados**:
   - No seletor **Motor de Dados & Privacidade**, deixe selecionado **`Google BigQuery (Sigilo Total & Privado)`**.
   - Digite o seu **ID do Projeto Google Cloud** (ex: `consulta-cnpj-123456`).
   - Informe o caminho do seu arquivo de chave JSON (ex: `C:/Users/SeuUsuario/Documents/caexlgs/gcp-key.json`).
   - Clique no botão **`🔌 Testar Conexão BigQuery`**.
   - Uma mensagem verde aparecerá: `✅ Conexão estabelecida com sucesso!`.
2. Pronto! O aplicativo está configurado com segurança máxima e sigilo total.

---

## 🧭 Principais Recursos e Como Usar

### 1. 🔍 Pesquisa de Empresas
- Digite qualquer CNPJ ou Razão Social na tela inicial para consultar a ficha completa com telefones, e-mails, quadro societário e endereço.

### 2. 🕸️ Grafo Interativo de Relacionamentos
- Na tela de detalhes da empresa, clique na aba **`🕸️ Grafo de Relacionamentos`**:
  - Visualize a rede com física gravitacional, nós arrastáveis e zoom.
  - Clique em **`⛶ Tela Cheia (Maximizar)`** para ocupar 100% do seu monitor.
  - Ative **`🧹 Filtrar Contadores`** para remover automaticamente prestadores contábeis e ruídos de rede.
  - Ative **`👥 Expandir Sócios (2º Grau)`** para desenhar no mapa todas as outras empresas em que os sócios participam.
  - Ative **`📍 Endereços Compartilhados`** para ver empresas que operam no mesmo prédio ou galpão.
  - Ative **`👑 Rastrear UBO`** para identificar quem são os controladores de pessoas físicas no topo da pirâmide societária.

### 3. 📑 Emissão de Relatórios & Dossiês
- Na sub-aba **`📑 Dossiê & Relatórios`**:
  - Digite seu parecer ou anotações no campo de texto.
  - Clique em **`Baixar Dossiê Completo (PDF)`** para gerar um documento formal com tabela de risco e quadro de sócios.
  - Clique em **`Baixar Planilha Consolidada (Excel)`** para abrir os dados no Microsoft Excel.

### 4. 💾 Salvar e Carregar Projetos de Investigação
- Na sub-aba **`💾 Salvar/Carregar Projeto`**:
  - Salve todo o trabalho da investigação em um arquivo `.json` para continuar outro dia ou enviar a um colega de equipe.

---

## ❓ Dúvidas Frequentes

* **P: Preciso pagar alguma coisa para o Google?**
  - **R:** Não. O Google oferece 1 TB (1.000 GB) de processamento gratuito todo mês no BigQuery, o que é suficiente para centenas de milhares de consultas no aplicativo.
* **P: Minhas pesquisas ficam salvas em algum servidor público?**
  - **R:** Não! No modo padrão de Sigilo Total, as consultas trafegam diretamente entre seu computador e o Google Cloud. Nenhuma informação é enviada a servidores de terceiros.
* **P: Como atualizar o aplicativo no futuro?**
  - **R:** Se você usou o Git, basta abrir o terminal na pasta e digitar `git pull`. Se baixou o ZIP, basta baixar a versão mais recente do repositório.
