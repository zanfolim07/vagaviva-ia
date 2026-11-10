# Vaga Viva — serviço de risco de falta

Entrega da disciplina **Artificial Intelligence & Chatbot**, Global Solution
2026/2 (CitizenTech), turma **1TDSPV**. A IA estima a probabilidade de falta para
priorizar confirmações pela recepção e agrupa instantâneos comportamentais para
sugerir contato. O risco e o perfil **nunca negam nem cancelam uma consulta**.

## Integrantes

- Fabio Cezare Almeida — RM 572642
- Guilherme Zanfolim Nunes Farias — RM 570983
- Jaime Ringel — RM 562044
- Lucas Monteiro Dias da Costa — RM 571388
- Mateus Magalhães Romão de Moraes — RM 573371

## Dados e privacidade

Fonte: Joni Hoppen, [Medical Appointment No Shows](https://www.kaggle.com/datasets/joniarroba/noshowappointments),
Kaggle, versão 5, modificada em 20/08/2017; licença **CC BY-NC-SA 4.0**.
A base tem 110.527 registros e 14 colunas. O notebook de análise baixa o arquivo
oficial diretamente para a memória, remove idade negativa, datas inválidas e
antecedência negativa, e grava em `dados/noshow_consultas.csv` apenas variáveis
derivadas, alvo e data da consulta. `PatientId` é usado só em memória para montar
históricos estritamente anteriores; IDs, sexo e doenças não são exportados nem
usados como entradas dos modelos.

## Estrutura

```text
vagaviva-ia/
├── dados/noshow_consultas.csv
├── notebooks/
│   ├── 01_analise_exploratoria.ipynb
│   ├── 02_modelo_classificacao_falta.ipynb
│   └── 03_modelo_agrupamento_perfis.ipynb
├── modelos/
│   ├── modelo_falta.joblib
│   ├── modelo_perfil.joblib
│   ├── scaler_perfil.joblib
│   └── config_modelos.json
├── api/
│   ├── app.py
│   └── requirements.txt
├── requirements-notebooks.txt
├── tests/test_api.py
├── integrantes.txt
└── README.md
```

## Executar os notebooks

Requer Python 3. Instale as dependências dos notebooks e abra a pasta `notebooks`
no Jupyter:

```powershell
python -m pip install -r requirements-notebooks.txt
python -m jupyter lab
```

Execute os notebooks na ordem:

1. `01_analise_exploratoria.ipynb` baixa a fonte oficial, valida e prepara a base
   sem identificadores, mostra os gráficos e salva `dados/noshow_consultas.csv`.
2. `02_modelo_classificacao_falta.ipynb` compara Regressão Logística e Random
   Forest com pesos de classe, usa separação temporal, calibra probabilidades com
   validação temporal e exporta o classificador e as faixas de risco.
3. `03_modelo_agrupamento_perfis.ipynb` avalia K-Means pelo cotovelo e silhueta,
   exporta o agrupador/scaler e acrescenta os perfis à configuração.

Os notebooks já foram executados e incluem as saídas desta execução. Se forem
executados novamente, o primeiro notebook precisa de acesso à internet para baixar
a versão 5 no endpoint oficial do Kaggle.

## Resultados calculados nos notebooks

Na base limpa, foram mantidas 110.521 consultas; a taxa observada de faltas foi
20,19%. A avaliação respeita o tempo e mantém o teste final isolado: os dados
anteriores a 20/05/2016 servem para ajuste, 20/05/2016 a 31/05/2016 para seleção
do algoritmo e consultas a partir de 01/06/2016 para o teste final.

| Modelo comparado no período de seleção, limiar 0,50 | Acurácia | Precisão (falta) | Recall (falta) | F1 (falta) | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Regressão Logística | 0,5606 | 0,3001 | 0,8921 | 0,4492 | 0,7327 |
| Random Forest | 0,6646 | 0,3238 | 0,6161 | 0,4245 | 0,7165 |

A Regressão Logística foi selecionada pelo ROC-AUC no período de seleção, sem
consultar o resultado do teste final, e calibrada usando validação temporal nos
dados de desenvolvimento. No teste final e limiar operacional 0,20, suas métricas
foram acurácia 0,5414, precisão 0,2710, recall 0,8787, F1 0,4143 e ROC-AUC 0,7218.
O recall alto ajuda a não deixar de contatar pacientes que possam faltar; em
contrapartida, haverá contatos de pessoas que compareceriam. As faixas BAIXO
(<0,20), MÉDIO (0,20–0,35) e ALTO (>0,35) apresentaram taxas reais de falta no
teste de 5,57%, 24,93% e 34,67%,
respectivamente.

No agrupamento, a maior silhueta na amostra determinística de até 3.000 linhas foi
0,5608 para **k=3** (k=2: 0,5515; k=4: 0,4157). Os nomes e estratégias vêm das
médias de cada grupo no notebook e são orientação operacional, não rótulos clínicos.

## Instalar e iniciar a API

Na raiz do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r api\requirements.txt
$env:PORT = "5000"
python api\app.py
```

Os três modelos são carregados uma vez na inicialização. A API lê os artefatos de
`modelos/` usando caminho relativo ao próprio `app.py`; CORS está habilitado.
Em produção, o comando de inicialização é `gunicorn app:app` no diretório `api`.

### `GET /`

```json
{"status":"ok","modelos":["falta","perfil"]}
```

### `POST /prever-falta`

Contrato consumido pela API Java:

```json
{
  "idade": 45,
  "dias_antecedencia": 40,
  "mesmo_dia": false,
  "dia_semana": 1,
  "recebeu_lembrete": false,
  "n_consultas_anteriores": 3,
  "faltas_anteriores": 2,
  "taxa_faltas_anterior": 0.67,
  "primeira_consulta": false
}
```

Resposta: `probabilidade_falta` entre 0 e 1, `nivel` exatamente `BAIXO`, `MEDIO`
ou `ALTO` (lido de `config_modelos.json`) e até três motivos curtos. Campos
ausentes, tipos incorretos ou valores fora dos limites retornam HTTP 400 com
`{"erro":"...","campos":[...]}`. Os motivos são descrições simples das entradas,
não explicações causais.

### `POST /perfil-paciente`

```json
{
  "idade": 45,
  "dias_antecedencia_media": 12.5,
  "taxa_faltas_anterior": 0.25,
  "taxa_lembretes_anterior": 0.5,
  "n_consultas_anteriores": 4
}
```

Resposta:

```json
{
  "grupo": 0,
  "perfil": "Histórico de faltas",
  "estrategia_contato": "Ligação da recepção 48h antes"
}
```

Os nomes e estratégias efetivos são os que estiverem no `config_modelos.json`.

### Teste local das rotas

Com a API em execução, envie:

```powershell
curl.exe http://localhost:5000/
curl.exe -X POST http://localhost:5000/prever-falta -H "Content-Type: application/json" -d "{\"idade\":45,\"dias_antecedencia\":40,\"mesmo_dia\":false,\"dia_semana\":1,\"recebeu_lembrete\":false,\"n_consultas_anteriores\":3,\"faltas_anteriores\":2,\"taxa_faltas_anterior\":0.67,\"primeira_consulta\":false}"
curl.exe -X POST http://localhost:5000/perfil-paciente -H "Content-Type: application/json" -d "{\"idade\":45,\"dias_antecedencia_media\":12.5,\"taxa_faltas_anterior\":0.25,\"taxa_lembretes_anterior\":0.5,\"n_consultas_anteriores\":4}"
```

Para executar os testes automatizados da API na raiz do projeto:

```powershell
python -m unittest discover -s tests -v
```

As três faixas foram exercitadas contra os modelos exportados:

| Cenário | Entrada resumida | Resposta observada |
|---|---|---|
| BAIXO | Primeira consulta, 18 anos, mesmo dia, recebeu lembrete | `{"probabilidade_falta":0.048705,"nivel":"BAIXO","motivos":["Primeira consulta"]}` |
| MÉDIO | 18 anos, mesmo dia, recebeu lembrete, 5 faltas em 10 consultas anteriores | `{"probabilidade_falta":0.274311,"nivel":"MEDIO","motivos":["Faltou em 5 das 10 consultas anteriores"]}` |
| ALTO | 18 anos, 1 dia de antecedência, recebeu lembrete, 1 falta em 3 consultas anteriores | `{"probabilidade_falta":0.359699,"nivel":"ALTO","motivos":["Faltou em 1 das 3 consultas anteriores"]}` |

`GET /` retornou HTTP 200 com os dois modelos; `/perfil-paciente` retornou HTTP
200 com grupo, nome e estratégia; uma requisição de previsão inválida retornou
HTTP 400 com `erro` e `campos`. CORS também foi verificado. Em 20 chamadas locais
de previsão, o p95 medido foi 12,68 ms e o máximo 45,26 ms.

## Integração com a API Java

O contrato foi conferido em `IaClient`, `IaRequest`, `IaResponse` e
`RiscoService`: os nove campos de `/prever-falta` correspondem ao JSON em
`snake_case`, os níveis aceitos são `BAIXO`, `MEDIO` e `ALTO`, e o cliente Java
usa timeout de 2 segundos. Não foi necessário alterar os arquivos Java.

Para a integração local, inicie a Flask e configure `IA_URL=http://localhost:5000`
na API Java. Depois crie uma consulta e confira `risco.nivel`. A criação de
consulta pela API Java não foi executada neste workspace; requer iniciar o serviço
Java e seu banco. Se a Flask estiver indisponível, a regra Java salva
`NAO_CALCULADO`. O risco não cancela nem impede consultas (RN07).

## Publicação no Render

Crie um Web Service Python apontando para a raiz desta pasta:

- **Root Directory:** raiz do repositório
- **Build Command:** `pip install -r api/requirements.txt`
- **Start Command:** `gunicorn --chdir api --workers 1 --timeout 120 app:app`

Após publicar, valide `GET /` e `POST /prever-falta` na URL pública e configure
`IA_URL=<URL pública>` na API Java. O plano gratuito do Render pode suspender o
serviço; antes da apresentação, faça uma requisição de aquecimento a `GET /` e
aguarde o serviço responder.

**URL pública:** https://vagaviva-ia.onrender.com

## Apresentação presencial — roteiro curto

1. **CitizenTech:** faltas desperdiçam horários e prolongam a fila; a Vaga Viva usa
   risco para priorizar confirmação e permitir oferta de vagas liberadas.
2. **Dados:** apresentar a origem, licença, limpeza e histórico anterior sem IDs;
   comentar taxa global e gráficos do notebook 01.
3. **Modelos:** explicar classificação para estimar probabilidade e K-Means para
   agrupar padrões de contato.
4. **Métricas:** interpretar precisão, recall, F1 e ROC-AUC; destacar o custo de
   perder uma falta e também o custo de contatos desnecessários.
5. **Demonstração:** abrir `GET /`, enviar exemplo para `/prever-falta`, mostrar
   `/perfil-paciente` e, com a API Java e banco disponíveis, criar consulta e
   conferir o risco na Agenda.
6. **Perguntas prováveis:** por que a divisão é temporal? Para simular previsões
   futuras. Como evitou vazamento? O histórico usa somente datas anteriores e IDs
   são removidos antes de exportar. Por que recall? Para não deixar de priorizar
   quem pode faltar. O risco cancela consultas? Não; só muda a ordem do contato.
   Por que K-Means? Para agrupar padrões sem rótulos prévios e sugerir estratégias.
