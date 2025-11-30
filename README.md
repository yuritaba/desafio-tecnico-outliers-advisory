# Pipeline de Processamento de Podcasts Financeiros

Sistema para transcrever, analisar e gerar conteúdo de marketing a partir do podcasts Second Level no YouTube.

## Estrutura do Projeto

```
desafio-tecnico-outliers-advisory/
├── main.py                              # CLI principal para ingestão de dados
├── app.py                               # Aplicação web Flask (chatbot + visualizações)
├── requirements.txt                     # Dependências Python
├── src/
│   ├── master_pipeline_api.py          # Orquestrador principal do pipeline
│   ├── youtube_transcriber_assemblyai.py  # Transcrição via AssemblyAI
│   ├── investment_agent.py             # Análise de investimentos (RAG + LLMs)
│   ├── marketing_agent.py              # Geração de conteúdo de marketing
│   ├── podcast_start_detector.py       # Detecção de início real do podcast
│   ├── models.py                        # Modelos Pydantic
│   └── utils.py                         # Funções utilitárias
├── output/ 
│   ├── transcripts/                     # Transcrições JSON (não commitado pelo .gitignore)
│   ├── analyses/                        # Análises de investimento (não commitado pelo .gitignore)
│   └── marketing/                       # Conteúdo de marketing gerado (não commitado pelo .gitignore)
├── templates/                           # Templates HTML do Flask
└── static/                              # Arquivos estáticos (CSS, JS)
```

### Descrição dos Arquivos Principais

**main.py**
- Pipeline para processamento em lote da playlist do podcast
- Comandos: `outliers-api`, `analyze`, `marketing`
- Orquestra transcrição, análise e faz geração de marketing

**app.py**
- Interface web com chatbot RAG (Pinecone + OpenAI)
- Visualização de análises e conteúdo de marketing
- API REST para consultas

**src/master_pipeline_api.py**
- Pipeline completo: transcrição via AssemblyAI + análise + marketing
- Gerencia fluxo entre componentes
- Skip automático de vídeos já processados

**src/youtube_transcriber_assemblyai.py**
- Download de áudio do YouTube (yt-dlp)
- Conversão para WAV 16kHz mono
- Transcrição via AssemblyAI com diarização (2 speakers)
- Identificação automática de speakers (Samuel Ponsoni + convidado)

**src/investment_agent.py**
- Análise de teses de investimento usando RAG
- Extração de ativos, setores, contexto macroeconômico
- Armazenamento vetorial no Pinecone
- Citações com timestamps e atribuição de speaker

**src/marketing_agent.py**
- Geração de posts para LinkedIn
- Criação de carrosséis (5 slides)
- Extração de citações impactantes
- Modos: técnico ou didático

## Como Rodar

### 1. Criar ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```
OPENAI_API_KEY=sk-...
ASSEMBLYAI_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=outliers-case
PINECONE_ENVIRONMENT=us-east-1
```

### 4. Rodar ingestão de dados (main.py)

Processar playlist completa:
```bash
python main.py outliers-api --max-videos 5
```

Processar apenas análise (transcrições já existem):
```bash
python main.py analyze --transcript-file output/transcripts/VIDEO_ID.json
```

Gerar apenas marketing:
```bash
python main.py marketing \
  --analysis-file output/analyses/VIDEO_ID_analysis.json \
  --transcript-file output/transcripts/VIDEO_ID.json
```

### 5. Rodar aplicação web (app.py)

```bash
python app.py
```

Acesse: http://localhost:5000

Funcionalidades:
- Chatbot com RAG para consultar análises
- Visualização de análises de investimento
- Visualização de conteúdo de marketing gerado

## Fluxo do Pipeline

```
YouTube Playlist
    ↓
[1] Transcrição (AssemblyAI)
    - Download de áudio
    - Conversão para WAV 16kHz
    - Diarização (2 speakers)
    - Identificação de speakers
    ↓
output/transcripts/*.json
    ↓
[2] Análise de Investimento
    - RAG com Pinecone
    - Extração de teses
    - Identificação de ativos/setores
    - Contexto macroeconômico
    ↓
output/analyses/*_analysis.json
    ↓
[3] Geração de Marketing
    - Posts LinkedIn
    - Carrosséis
    - Citações
    ↓
output/marketing/*_marketing.json
```

## Requisitos

- Python 3.8+
- ffmpeg (para conversão de áudio)
- APIs: OpenAI, AssemblyAI, Pinecone