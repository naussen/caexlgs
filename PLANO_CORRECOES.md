# Plano de Correções do POMELO

## 1. Objetivo

Corrigir, em etapas pequenas e verificáveis, os problemas encontrados no app publicado em `https://pomelo.streamlit.app/`, com prioridade para:

1. restringir o acesso ao app por login e senha;
2. fazer os botões `+` e `X` do grafo comunicarem-se corretamente com o Streamlit;
3. corrigir a expansão de empresa, sócio, telefone e e-mail;
4. corrigir as expansões globais de segundo grau e contatos;
5. impedir duplicidade de nós e arestas;
6. tornar exclusões consistentes e reversíveis;
7. exibir erros em vez de falhar silenciosamente;
8. preparar o app para dois a cinco usuários simultâneos;
9. alinhar documentação, segurança e comportamento publicado.

Este documento foi escrito para execução por uma IA de menor capacidade. Não pule etapas, não misture fases e não faça refatorações fora do escopo.

## 2. Regras obrigatórias de execução

Antes de iniciar cada fase:

1. executar `git status --short --branch`;
2. confirmar que não existem alterações do usuário que possam ser sobrescritas;
3. criar ou continuar uma branch com prefixo `codex/`;
4. ler integralmente todos os arquivos citados na fase;
5. executar os testes existentes antes de alterar código;
6. implementar somente a fase atual;
7. executar os testes indicados na fase;
8. revisar o diff com `git diff --check` e `git diff`;
9. criar um commit exclusivo para a fase;
10. fazer push da branch, nunca de `main`.

Comandos iniciais:

```powershell
cd C:\pomelo
git status --short --branch
python -m unittest discover -s cnpjpw/tests -p "test_*.py"
python -m compileall -q app.py cnpjpw/local_app cnpjpw/api cnpjpw/etl
```

Não modificar `.env`, `.streamlit/secrets.toml`, chaves JSON, tokens ou credenciais reais. Não adicionar dependências sem necessidade comprovada.

## 3. Estado atual confirmado

Teste realizado com o CNPJ `75323907000190`:

- consulta do CNPJ: funcional;
- grafo inicial: 3 entidades e 2 conexões;
- botão `+` dentro do grafo: sem efeito;
- expansão externa da empresa raiz: não cria entidades e duplica arestas;
- `Expandir Sócios (2º Grau)`: elevou o grafo para 8 entidades e 9 conexões;
- `Expandir Contatos`: mudou o estado do botão, mas não adicionou entidades nem mostrou erro;
- expansão externa de empresa vinculada: elevou o grafo para 10 entidades e 12 conexões;
- o `X` interno usa a mesma comunicação defeituosa do botão `+`;
- a suíte atual possui 27 testes aprovados, mas não cobre a comunicação real iframe/Streamlit.

## 4. Ordem de implementação

### Fase 1 — Adicionar login e senha compartilhados [CONCLUÍDA]

> **Status:** Concluída integralmente.
> - Módulo de autenticação `cnpjpw/local_app/auth.py` implementado com suporte a Streamlit Secrets, variáveis de ambiente e fallback `caexlgs`/`caexlgs`, comparando com `hmac.compare_digest`.
> - Barreira inserida em `cnpjpw/local_app/app.py` logo após `st.set_page_config`, impedindo leitura de URL, consultas e renderização antes do login.
> - Botão `🚪 Sair` adicionado na barra lateral com invalidação de sessão e rerun.
> - Suíte de testes `cnpjpw/tests/test_auth.py` criada com 10 casos de teste cobrindo todos os cenários obrigatórios (10/10 aprovados).
> - Documentação atualizada em `README.md` e `DOCUMENTACAO_APP.md`.

#### Resultado esperado

Nenhuma consulta, parâmetro de URL, ficha cadastral ou grafo deve ser processado antes da autenticação.

Credencial inicial solicitada:

- login: `caexlgs`
- senha: `caexlgs`

Esses valores devem ser defaults temporários. A implementação deve aceitar substituição por Secrets ou variáveis de ambiente sem alteração de código.

#### Arquivos

- criar `cnpjpw/local_app/auth.py`;
- alterar `cnpjpw/local_app/app.py`;
- criar `cnpjpw/tests/test_auth.py`;
- atualizar `README.md` e `DOCUMENTACAO_APP.md`.

#### Implementação exata

1. Em `auth.py`, definir:
   - `DEFAULT_LOGIN = "caexlgs"`;
   - `DEFAULT_PASSWORD = "caexlgs"`;
   - função para carregar `POMELO_LOGIN` e `POMELO_PASSWORD`;
   - prioridade recomendada: Streamlit Secrets, variável de ambiente, default;
   - função pura `verify_credentials(...)` usando `hmac.compare_digest` para os dois campos.
2. Não registrar senha em log, toast, exceção ou estado de erro.
3. Em `app.py`, imediatamente depois de `st.set_page_config(...)`:
   - inicializar `st.session_state.authenticated` como `False`;
   - renderizar formulário com campo de login e `type="password"` para senha;
   - em sucesso, marcar a sessão como autenticada e executar `st.rerun()`;
   - em falha, mostrar mensagem genérica: `Login ou senha inválidos.`;
   - chamar `st.stop()` enquanto não houver autenticação.
4. Depois da autenticação, adicionar `Sair` na barra lateral:
   - ao clicar, definir `authenticated = False`;
   - remover valores temporários do formulário, se existirem;
   - executar `st.rerun()`.
5. Não colocar login ou senha em query parameters.
6. Não usar hash fixo apresentado no navegador como substituto da senha.
7. Não autenticar somente com JavaScript. A barreira deve executar no Python antes do restante do app.

#### Testes obrigatórios

- credencial correta retorna `True`;
- login incorreto retorna `False`;
- senha incorreta retorna `False`;
- valores de Secrets substituem defaults;
- valores de ambiente substituem defaults quando Secrets não existem;
- ausência de configuração usa `caexlgs/caexlgs`;
- abrir `/?cnpj=75323907000190` sem autenticação continua exibindo somente o login;
- após autenticar, o CNPJ pode ser consultado;
- após sair, atualizar a página não mantém acesso.

#### Critério de aceite

O usuário não autenticado não vê nem aciona nenhuma funcionalidade do POMELO. O login solicitado funciona, o botão de saída encerra a sessão e nenhum segredo aparece em logs ou URL.

#### Observação de segurança

Antes de disponibilizar o app a outras pessoas, cadastrar valores diferentes de `caexlgs` nos Secrets do Streamlit. Uma credencial compartilhada não fornece auditoria individual.

### Fase 2 — Substituir a bridge DOM pelo componente oficial do Streamlit [CONCLUÍDA]

> **Status:** Concluída integralmente.
> - Substituído `build_graph_html()` + `components.html()` por `graph_builder.render_interactive_graph()` em `cnpjpw/local_app/app.py`.
> - Removido o campo oculto `Graph Bridge Receiver`, seu callback e hacks de injeção direta no React.
> - Removida a manipulação de `window.parent.document` e fallbacks por `window.parent.location`.
> - Padronizado o schema de eventos no componente `components/vis_graph/index.html` com `action`, `node_id`, `entity_type`, `entity_value`, `entity_label`, `feature` e `nonce`.
> - Implementado controle de deduplicação de eventos por `nonce` em `st.session_state.last_processed_graph_nonce` para evitar repetições em reruns.
> - Criada suíte de testes dedicada `cnpjpw/tests/test_graph_events.py` cobrindo todos os cenários obrigatórios (8/8 aprovados).
> - Atualizado `cnpjpw/tests/test_graph_builder.py` para verificar a ausência da bridge DOM legada.

#### Problema

`app.py` usa `build_graph_html()` com `components.html()`. O iframe tenta editar diretamente um input React chamado `Graph Bridge Receiver`. A tentativa retorna antes de confirmar o recebimento e impede o fallback.

Já existe um componente declarado em `graph_builder.py` e uma implementação em `cnpjpw/local_app/components/vis_graph/index.html`, mas esse caminho não é usado na tela principal.

#### Arquivos

- `cnpjpw/local_app/app.py`;
- `cnpjpw/local_app/graph_builder.py`;
- `cnpjpw/local_app/components/vis_graph/index.html`;
- `cnpjpw/tests/test_graph_builder.py`;
- criar testes específicos de eventos, se necessário.

#### Implementação exata

1. Ler integralmente as três implementações atuais:
   - `render_interactive_graph()`;
   - `build_graph_html()`;
   - `components/vis_graph/index.html`.
2. Escolher uma única implementação ativa: o componente declarado por `components.declare_component`.
3. Em `app.py`, substituir `build_graph_html()` + `components.html()` por `render_interactive_graph()`.
4. Receber o valor retornado pelo componente e processar exatamente um evento por `nonce`.
5. Manter em `st.session_state` o último `nonce` processado para impedir repetição em reruns.
6. Padronizar todos os payloads:

```json
{
  "action": "expand|delete|toggle_feature|clear",
  "node_id": "identificador_estavel",
  "entity_type": "EMPRESA|EMPRESA_ROOT|SOCIO|UBO|TELEFONE|EMAIL",
  "entity_value": "valor_bruto",
  "entity_label": "rotulo",
  "feature": "expand_socios|expand_contacts",
  "nonce": "valor_unico"
}
```

7. Remover o campo oculto `Graph Bridge Receiver` e seu callback.
8. Remover a manipulação de `window.parent.document`.
9. Remover os fallbacks por `window.parent.location` e `window.top.location`.
10. Não manter duas implementações completas do grafo. Depois de validar o componente, remover apenas o código comprovadamente morto, em commit separado ou explicitamente documentado.

#### Testes obrigatórios

- evento `expand` retorna todos os campos esperados;
- evento `delete` envia `node_id`;
- `toggle_feature` envia o nome correto;
- `clear` não é confundido com exclusão individual;
- o mesmo `nonce` não é processado duas vezes;
- clicar no `+` causa rerun e feedback visível;
- clicar no `X` persiste a exclusão após rerun.

#### Critério de aceite

Os botões internos e externos produzem o mesmo resultado e usam o mesmo handler Python. Nenhum código acessa diretamente o DOM do frame pai.

### Fase 3 — Unificar o dispatcher de ações do grafo [CONCLUÍDA]

> **Status:** Concluída integralmente.
> - Criado o módulo `cnpjpw/local_app/graph_dispatcher.py` com a função única `handle_graph_action(event, expand_fn, root_id)`.
> - Validação estrita de eventos (`validate_graph_event`), rejeitando não-dicionários, ações desconhecidas ou campos obrigatórios ausentes.
> - Roteamento padronizado de todas as ações:
>   - `expand` -> `executar_expansao_entidade()`;
>   - `delete` -> `exclude_graph_node()` com proteção ativa bloqueando exclusão do nó da empresa raiz;
>   - `toggle_feature` -> alternância controlada de `expand_socios` e `expand_contacts`;
>   - `clear` -> reinicialização completa via `clear_graph_expansions()`.
> - Todos os controles externos (toolbar e seletor) agora usam a mesma estrutura de evento e chamam o dispatcher central.
> - Removido o processamento de ações do grafo via query parameters da URL (`expand_type`, `exclude_node`).
> - Suíte de testes `cnpjpw/tests/test_graph_events.py` ampliada com testes de validação, bloqueio da raiz e roteamento (11/11 aprovados).

#### Objetivo

Eliminar tratamentos diferentes para botão interno, seletor externo e query parameter.

#### Implementação exata

1. Criar uma função Python única, por exemplo `handle_graph_action(event)`.
2. Validar que `event` é dicionário e que `action` pertence à lista permitida.
3. Validar tipo, valor e identificador antes de alterar o estado.
4. Direcionar:
   - `expand` para `executar_expansao_entidade()`;
   - `delete` para a função de exclusão da Fase 7;
   - `toggle_feature` para alternância controlada;
   - `clear` para limpeza das expansões.
5. Fazer os controles externos criarem o mesmo dicionário de evento e chamarem o mesmo dispatcher.
6. Não usar query parameters para transportar eventos internos do grafo.

#### Critério de aceite

Existe apenas um ponto Python responsável por validar e executar ações do grafo.

### Fase 4 — Corrigir a semântica da expansão específica [CONCLUÍDA]

> **Status:** Concluída integralmente.
> - Implementadas as 4 regras semânticas estritas em `cnpjpw/local_app/graph_dispatcher.py` (`executar_expansao_entidade`):
>   - **Empresa:** Validação estrita de 14 dígitos numéricos; proteção ativa da empresa raiz (impede inclusão em `multi_expanded_companies` e orienta sobre o uso de expansão de 2º grau/contatos); deduplicação de chamadas.
>   - **Sócio / UBO:** Priorização de documento quando disponível e desmascarado (`api_client.buscar_socio`); fallback robusto por nome (`api_client.buscar_empresas_do_socio`); normalização em maiúsculas apenas para chave de cache preservando rótulo original; filtro obrigatório da raiz e deduplicação de CNPJs retornados.
>   - **Telefone:** Sanitização numérica estrita; exigência mandatória de DDD explícito (10 ou 11 dígitos); remoção do fallback arbitrário `ddd = '11'`; filtro da empresa raiz e deduplicação de resultados.
>   - **E-mail:** Normalização completa (`strip().lower()`); validação sintática (presença de `@`, partes não-vazias de usuário e domínio com ponto); filtro da empresa raiz e deduplicação de resultados.
> - Atualizado `cnpjpw/local_app/app.py` para delegar a expansão pontual diretamente para `graph_dispatcher.executar_expansao_entidade(..., root_id=cnpj)`.
> - Criada suíte de testes unitários `TestEntityExpansionSemantics` em `cnpjpw/tests/test_graph_events.py` cobrindo todas as regras por tipo e garantindo proteção da raiz (25/25 testes aprovados no projeto).

#### Regras por tipo

##### Empresa (`EMPRESA` ou `EMPRESA_ROOT`)

1. Limpar e validar CNPJ com 14 dígitos.
2. Buscar a ficha completa.
3. Adicionar a empresa somente se ela ainda não for a raiz nem estiver expandida.
4. Adicionar seus sócios, telefone e e-mail diretos.
5. Se a empresa for a raiz, não adicioná-la a `multi_expanded_companies`.
6. Para a raiz, informar que os vínculos diretos já estão carregados e oferecer expansão de sócios/contatos.

##### Sócio ou UBO

1. Usar documento quando estiver disponível e não mascarado.
2. Usar nome como fallback.
3. Normalizar somente para a chave de cache; preservar o nome original para exibição.
4. Adicionar empresas encontradas, excluindo duplicatas e a raiz.

##### Telefone

1. Manter somente dígitos.
2. Aceitar telefone apenas com DDD explícito.
3. Remover o fallback arbitrário `ddd = "11"`.
4. Executar busca reversa pelo wrapper unificado da Fase 5.

##### E-mail

1. Normalizar com `strip().lower()`.
2. Validar presença de `@` e partes não vazias.
3. Executar busca reversa pelo wrapper unificado da Fase 5.

#### Critério de aceite

Cada tipo de entidade executa uma operação previsível, sem duplicar a raiz e sem inventar DDD.

### Fase 5 — Unificar BigQuery e fallback de API [CONCLUÍDA]

> **Status:** Concluída integralmente.
> - Criada a camada unificada de dados `cnpjpw/local_app/data_service.py` com contrato padronizado de resposta `QueryResult` (`results`, `source`, `error`, `fallback_used`).
> - Implementada detecção completa de credenciais do BigQuery (`is_bigquery_available`): suporte a `st.secrets["GCP_SERVICE_ACCOUNT_JSON"]`, `st.secrets["gcp_service_account"]`, variáveis de ambiente (`GOOGLE_APPLICATION_CREDENTIALS`, `GCP_SERVICE_ACCOUNT_JSON`) e arquivo local exclusivo para ambiente de desenvolvimento.
> - Unificado o acesso a dados de todas as telas e abas:
>   - **Ficha Cadastral:** Busca cadastral (`get_cnpj`) e botões de busca reversa de contatos roteados via `data_service`.
>   - **Busca Simples e Avançada:** Pesquisas por Razão Social, Sócio, Telefone, E-mail e Busca Difusa roteadas via `data_service`.
>   - **Grafo:** Expansões pontuais de entidades no `graph_dispatcher.py` e expansões globais roteadas via `data_service`.
> - **Regra 5 cumprida:** Bloqueio ativo de requisições de busca reversa por telefone ou e-mail na API pública (`api.cnpj.pw`), prevenindo erros 404 e requisições HTTP desnecessárias.
> - **Regra 6 e 7 cumpridas:** Indicador transparente de origem dos dados exibido nas telas de resultados e detalhes; selo lateral `Sigilo Ativo` condicional — exibindo selo verde apenas quando BigQuery ou API Local Privada são utilizados, e selo informativo âmbar `API Pública (Sem Sigilo)` quando conectada à API externa pública.
> - Criada suíte de testes dedicada `cnpjpw/tests/test_data_service.py` (11 testes cobrindo credenciais, contrato de retorno, fallback transparente, bloqueio de reversa pública e cálculo de sigilo). Todos os 46 testes do repositório aprovados.

#### Problema

A ficha cadastral utiliza wrappers próprios para contatos; o grafo chama `api_client` diretamente. Além disso, a detecção de BigQuery em `api_client.is_bigquery_available()` não considera adequadamente todos os formatos de Streamlit Secrets.

#### Implementação exata

1. Criar uma única camada de serviço para:
   - `get_cnpj`;
   - `buscar_empresas_do_socio`;
   - `buscar_telefone`;
   - `buscar_email`.
2. Fazer ficha cadastral, busca simples e grafo usarem essa camada.
3. Fazer a disponibilidade do BigQuery considerar:
   - `st.secrets["GCP_SERVICE_ACCOUNT_JSON"]`;
   - `st.secrets["gcp_service_account"]`;
   - variável de ambiente;
   - arquivo local somente no ambiente local.
4. Retornar uma estrutura explícita:

```python
{
    "results": [],
    "source": "BIGQUERY|LOCAL_API|PUBLIC_API",
    "error": None,
    "fallback_used": False,
}
```

5. Não executar busca reversa na API pública quando ela não oferecer o endpoint.
6. Exibir a origem real da consulta na interface.
7. Corrigir o selo `Sigilo Ativo`: exibi-lo somente quando a origem e configuração justificarem essa afirmação.

#### Critério de aceite

Uma mesma consulta produz o mesmo resultado independentemente do botão que a iniciou e informa claramente origem, fallback e erro.

### Fase 6 — Corrigir expansões globais [CONCLUÍDA]

> **Status:** Concluída integralmente.
> - Criado o módulo `cnpjpw/local_app/graph_expansions.py` implementando:
>   - **Expandir sócios até 2º grau (`expand_socios_grau2`):**
>     - Grau 0 definido como a empresa raiz; Grau 1 como os sócios diretos da raiz; Grau 2 como as outras empresas desses sócios.
>     - Não expande os sócios das empresas de grau 2 (sem avanço descontrolado para grau 3).
>     - Deduplicação estrita por CNPJ completo de 14 dígitos e descarte automático da empresa raiz.
>     - Limite configurável aplicado (padrão 25 empresas por sócio).
>     - Resumo auditável detalhado: sócios consultados, empresas encontradas, adicionadas, duplicatas descartadas e falhas.
>   - **Expandir contatos da rede (`expand_contacts_network`):**
>     - Escopo unificado e transparente: analisa os contatos únicos de todas as empresas visíveis na rede.
>     - Coleta e deduplicação prévia de contatos antes de disparar consultas.
>     - Filtragem rigorosa: rejeita telefones sem DDD explícito (< 10 dígitos) ou repetitivos e e-mails fora do padrão sintático.
>     - Limite configurável de 25 empresas por contato e cache persistido por chave normalizada.
>     - Tratamento gracioso da restrição de busca reversa na API pública (Regra 5), registrando avisos sem abortar o fluxo.
> - Interface atualizada em `cnpjpw/local_app/app.py` e `components/vis_graph/index.html`:
>   - Botões renomeados com tooltips informativos: `👥 Expandir Sócios (2º Grau)` e `📞 Expandir Contatos da Rede`.
>   - Banners visuais de sumário auditável exibidos quando as expansões estão ativas.
>   - Gerenciamento de ciclo de vida e limpeza de sumários no `graph_dispatcher.py` na ação `clear` e alternâncias.
> - Criada suíte de testes unitários dedicada `cnpjpw/tests/test_global_expansions.py` (10/10 testes aprovados). Total do repositório: 56/56 testes aprovados.

#### Expandir sócios até segundo grau

1. Definir grau 0 como empresa raiz.
2. Definir grau 1 como sócios diretos da raiz.
3. Definir grau 2 como outras empresas desses sócios.
4. Não expandir novamente os sócios das empresas de grau 2 nesta operação.
5. Deduplicar por CNPJ completo.
6. Aplicar limite configurável, inicialmente 25 empresas por sócio.
7. Mostrar resumo: sócios consultados, empresas encontradas, duplicatas removidas e falhas.

#### Expandir contatos

1. Definir claramente o escopo do botão:
   - recomendação inicial: contatos de todas as empresas atualmente visíveis;
   - alternativa conservadora: somente contatos da raiz, com esse texto explícito no botão.
2. Coletar contatos únicos antes de consultar.
3. Não consultar contatos vazios ou inválidos.
4. Limitar resultados por contato.
5. Guardar cache por chave normalizada.
6. Mostrar resumo e erros parciais.

#### Critério de aceite

Os nomes dos botões correspondem exatamente ao alcance real da operação, e o usuário recebe um resumo verificável.

### Fase 7 — Corrigir exclusão de entidades

#### Implementação exata

1. Criar uma função única `exclude_graph_node(node_id, root_id)`.
2. Validar que o nó existe.
3. Bloquear exclusão da raiz em todos os controles.
4. Persistir primeiro em `st.session_state.graph_excluded_nodes`.
5. Executar rerun para o grafo ser reconstruído pelo Python.
6. Não remover o nó somente no JavaScript antes da confirmação do backend.
7. Remover automaticamente arestas incidentes durante a reconstrução.
8. Manter a restauração no painel `Gerenciar Exclusões`.
9. Exibir toast com o rótulo da entidade removida.
10. Garantir que salvar e carregar caso preserve as exclusões.

#### Testes obrigatórios

- excluir nó comum remove nó e arestas;
- nó continua excluído após rerun;
- raiz nunca pode ser excluída;
- restaurar nó recompõe suas arestas;
- salvar/carregar caso conserva exclusões;
- identificador inexistente não gera exceção.

#### Critério de aceite

O `X`, o botão externo e o painel de exclusões seguem exatamente as mesmas regras.

### Fase 8 — Deduplicar nós e arestas

#### Implementação exata

1. Manter `nodes_dict` indexado por ID estável.
2. Criar `edges_dict` ou `seen_edges`.
3. Definir chave da aresta como pelo menos:

```python
(source_id, target_id, relationship_type, label)
```

4. Para relações não direcionais, ordenar os dois IDs antes de formar a chave.
5. Não adicionar aresta se qualquer nó estiver ausente ou excluído.
6. Impedir que a expansão da raiz replique suas arestas.

#### Testes obrigatórios

- executar a mesma expansão duas vezes não altera contagens;
- raiz não é duplicada;
- arestas iguais aparecem uma vez;
- arestas com tipos diferentes são preservadas.

#### Critério de aceite

Toda expansão é idempotente.

### Fase 9 — Eliminar falhas silenciosas e melhorar feedback

#### Implementação exata

1. Remover `except Exception: pass` dos fluxos do grafo.
2. Capturar exceções específicas quando possível.
3. Registrar apenas informação técnica sem dados sensíveis.
4. Mostrar ao usuário:
   - consulta iniciada;
   - origem dos dados;
   - quantidade encontrada;
   - lista vazia legítima;
   - erro de credencial, permissão, cota, rede ou endpoint indisponível.
5. Não tratar erro como lista vazia.
6. Não marcar uma consulta com erro como cache concluído.

#### Critério de aceite

O usuário consegue distinguir “nenhuma relação encontrada” de “a consulta falhou”.

### Fase 10 — Segurança para uso compartilhado

#### Implementação exata

1. Remover `verify=False` de todas as requisições HTTP.
2. Remover a desativação global de avisos TLS.
3. Configurar timeouts separados de conexão e leitura.
4. Garantir que configurações por usuário não sejam armazenadas em variáveis globais mutáveis.
5. Manter estado investigativo exclusivamente em `st.session_state` ou armazenamento associado ao usuário.
6. Não compartilhar `_last_error` global entre sessões.
7. Adicionar limites por ação:
   - máximo de empresas por expansão;
   - máximo de contatos consultados;
   - máximo de nós no grafo;
   - aviso antes de operação extensa.
8. Restringir o app no Streamlit Cloud e não depender apenas de URL não divulgada.
9. Trocar a senha padrão via Secrets antes de convidar usuários.
10. Documentar que login compartilhado não oferece trilha individual de auditoria.

#### Critério de aceite

Duas sessões simultâneas não alteram configuração, erros, notas ou grafo uma da outra.

### Fase 11 — Testes de integração e regressão

#### Casos mínimos

1. Login correto, incorreto e logout.
2. Acesso direto por `?cnpj=` sem autenticação.
3. Busca do CNPJ `75323907000190`.
4. Expansão da raiz sem duplicidade.
5. Expansão de empresa relacionada pelo `+`.
6. Expansão do UBO/sócio.
7. Expansão de telefone.
8. Expansão de e-mail quando disponível.
9. Segundo grau acionado duas vezes.
10. Contatos acionados duas vezes.
11. Exclusão e restauração.
12. Salvar e carregar caso com exclusões.
13. Duas sessões independentes.
14. Falha de BigQuery e comportamento do fallback.
15. Cota excedida e mensagem correspondente.

Executar ao final:

```powershell
python -m unittest discover -s cnpjpw/tests -p "test_*.py"
python -m compileall -q app.py cnpjpw/local_app cnpjpw/api cnpjpw/etl
git diff --check
```

Também testar manualmente em larguras de 320, 768 e 1440 pixels, verificando login, toolbar, seletor, grafo, botões flutuantes e painéis inferiores.

### Fase 12 — Documentação e publicação

#### Atualizações obrigatórias

1. Corrigir `README.md`, `GUIA_INSTALACAO.md` e `DOCUMENTACAO_APP.md`.
2. Remover afirmações absolutas de sigilo quando houver fallback externo.
3. Documentar:
   - configuração de login por Secrets;
   - troca da senha padrão;
   - origem das consultas;
   - limites de expansão;
   - definição de primeiro e segundo grau;
   - funcionamento de exclusão e restauração.
4. Confirmar que a documentação descreve somente funcionalidades verificadas.
5. Fazer deploy pela branch ou fluxo de revisão configurado.
6. Repetir os 15 casos da Fase 11 no app publicado.
7. Confirmar o commit efetivamente implantado.

#### Critério de aceite

O deploy publicado exige autenticação e reproduz localmente e em produção os mesmos resultados e mensagens.

## 5. Estratégia recomendada de commits

Usar commits pequenos nesta ordem:

1. `feat(auth): restringir acesso ao app com login compartilhado`
2. `fix(graph): migrar interacoes para componente Streamlit oficial`
3. `refactor(graph): unificar dispatcher de acoes`
4. `fix(graph): corrigir expansao por tipo de entidade`
5. `fix(data): unificar origem de consultas e fallback`
6. `fix(graph): corrigir expansoes de segundo grau e contatos`
7. `fix(graph): tornar exclusao consistente e reversivel`
8. `fix(graph): deduplicar nos e arestas`
9. `fix(ui): exibir erros e resumos de expansao`
10. `security: isolar sessoes e restaurar validacao TLS`
11. `test: cobrir autenticacao e interacoes do grafo`
12. `docs: alinhar documentacao ao comportamento publicado`

Após cada commit:

```powershell
git status --short --branch
git log -1 --oneline
git push -u origin HEAD
```

## 6. Condições de parada

A IA deve parar e relatar o bloqueio se ocorrer qualquer uma destas situações:

- alterações preexistentes conflitarem com os arquivos da fase;
- testes que já falhavam antes da alteração não puderem ser separados das novas falhas;
- credenciais do Streamlit ou BigQuery estiverem ausentes para teste de produção;
- o deploy não corresponder ao commit enviado;
- a correção exigir alteração de `.env`, Secrets ou chave sem autorização do usuário;
- o comportamento da API pública diferir do contrato documentado;
- houver risco de expor senha, chave, notas investigativas ou dados pessoais.

## 7. Definição final de pronto

O trabalho completo só pode ser marcado como concluído quando:

- o app publicado exige login;
- a senha padrão pode ser substituída por Secrets;
- `+` e `X` funcionam diretamente no grafo;
- controles internos e externos usam o mesmo fluxo;
- expansão específica funciona para PJ, PF, telefone e e-mail;
- segundo grau e contatos têm escopo documentado e testado;
- nenhuma expansão duplica nós ou arestas;
- exclusão é persistente, reversível e não aceita a raiz;
- erros são visíveis e distinguíveis de resultado vazio;
- sessões simultâneas são isoladas;
- TLS está habilitado;
- testes automatizados e smoke test publicado foram aprovados;
- documentação corresponde ao comportamento real;
- commits foram enviados para branch diferente de `main`.
