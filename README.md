# 🎙️ Pipeline de Processamento de Podcasts Financeiros

Sistema completo para extrair, transcrever, analisar e gerar conteúdo de marketing a partir de podcasts financeiros no YouTube.

## 🎯 Objetivo

Processar a playlist de podcasts da **Outliers Advisory** para:

1. **Transcrever via AssemblyAI** com diarização (2 speakers)
2. **Identificar speakers** automaticamente (Samuel Ponsoni + Convidado via OpenAI)
3. **Analisar teses de investimento** usando RAG e LLMs
4. **Gerar conteúdo de marketing** estruturado para LinkedIn

## ⚡ Pipeline Otimizado (AssemblyAI)

**Sistema atual utiliza AssemblyAI**:

- ✅ **Diarização perfeita**: Identifica automaticamente 2 speakers com alta precisão
- ✅ **Processamento em nuvem**: Upload + transcrição assíncrona
- ✅ **Identificação inteligente**: Extrai nome do convidado da descrição via OpenAI
- ✅ **Skip automático**: Não re-processa vídeos já transcritos
- ✅ **Formato WAV 16kHz**: Download e conversão automática do YouTube

### Comandos disponíveis:

```bash
# Processar playlist via Google Cloud (recomendado)
python main.py outliers-api --max-videos 3

# Processar todos os vídeos da playlist
python main.py outliers-api

# Testar com 1 vídeo
python main.py test
```

## 🚀 Quick Start

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas chaves:
# OPENAI_API_KEY=sk-...
# ASSEMBLYAI_KEY=...

# 3. Testar com 1 vídeo
python main.py test

# 4. Processar playlist completa
python main.py outliers-api --max-videos 5
```

## 📋 Funcionalidades

### 1. Transcrição via AssemblyAI

- **AssemblyAI Speaker Diarization** com alta precisão
- **Download automático**: yt-dlp + ffmpeg para conversão
- **Formato WAV 16kHz mono**: Conversão automática
- **Diarização perfeita**: 2 speakers identificados corretamente
- **Identificação inteligente**: 
  - Speaker A = Samuel Ponsoni (fixo)
  - Speaker B = Extraído da descrição via OpenAI GPT-3.5-turbo
- **Processamento assíncrono**: Polling até conclusão

### 2. Análise de Investimento (RAG + LLMs)

Extrai de cada episódio:
- **Tese Principal de Investimento**
- **Ativos/Setores Mencionados**
- **Contexto Macroeconômico**
- **Horizonte Temporal e Riscos**
- **Citações-Chave com Atribuição**

### 3. Geração de Marketing

Cria conteúdo estruturado:
- **Post LinkedIn** (150-300 palavras, com hashtags)
- **Carrossel** (5 slides com título + bullets)
- **Citações** (5 frases impactantes com speaker)
- **Sumário Executivo** para equipe de marketing

Modos disponíveis:
- **Technical**: Para profissionais do mercado financeiro
- **Didactic**: Para público geral (padrão)

## 🔧 Comandos CLI Disponíveis

### 🌟 Comandos Principais

```bash
# Processar playlist completa (Google Cloud)
python main.py outliers-api --max-videos 5

# Testar com 1 vídeo
python main.py test

# Processar com tom técnico
python main.py outliers-api --max-videos 3 --tone technical

# Pular etapas específicas
python main.py outliers-api \
  --skip-analysis \       # Pular análise
  --skip-marketing        # Pular marketing
```

### � Outros Comandos

# Atalho Outliers (modo tradicional)
python main.py outliers --max-videos 3

# Com todas as opções
python main.py process-playlist \
  --playlist-url "https://youtube.com/playlist?list=..." \
  --max-videos 10 \
  --tone didactic \
  --skip-download \       # Usar MP3s já baixados
  --skip-transcription \  # Usar JSONs existentes
  --log-level DEBUG
```

### 🎧 Processar Áudio Local

```bash
# Processar um arquivo de áudio com o pipeline completo
python main.py process podcast.mp3 \
  --output output/transcript.json \
  --title "Episódio 001" \
  --host-name "João Silva" \
  --guest-names "Maria Santos"

# Com opções avançadas
python main.py process audio.mp3 \
  --whisper-backend whisperx \
  --whisper-model large-v3 \
  --diarization-backend pyannote \
  --max-speakers 2 \
  --language pt \
  --no-clean  # Desabilita limpeza de texto
```

### 📊 Análise e Marketing Individuais

```bash
# Analisar uma transcrição existente
python main.py analyze output/transcripts/ep_001.json

# Gerar marketing de uma análise
python main.py marketing \
  output/analyses/ep_001_analysis.json \
  output/transcripts/ep_001.json \
  --tone didactic

# Validar arquivo de transcrição
python main.py validate output/transcript.json
```

### 🧪 Teste

```bash
# Testar pipeline completo com 1 vídeo (via API)
python main.py test
```

## 🏗️ Arquitetura

### Modo Tradicional (com download):
```
YouTube Playlist
    ↓
[youtube_extractor.py] → data/*.mp3
    ↓
[pipeline.py] → output/transcripts/*.json
    ├─ transcriber.py
    ├─ diarizer.py
    ├─ aligner.py
    ├─ speaker_identifier.py
    └─ text_cleaner.py
    ↓
[investment_agent.py] → output/analyses/*_analysis.json
    └─ RAG + LangChain + GPT-4
    ↓
[marketing_agent.py] → output/marketing/*_marketing.json
    └─ Prompts especializados + GPT-4
```

### Modo API (novo - recomendado):
```
YouTube Playlist
    ↓
[youtube_transcriber.py] → OpenAI Whisper API
    ├─ Extrai URL do vídeo
    ├─ Áudio temporário em memória
    └─ API retorna transcrição com timestamps
    ↓
output/transcripts/*.json (estruturado)
    ↓
[investment_agent.py] → output/analyses/*_analysis.json
    └─ RAG + LangChain + GPT-4
    ↓
[marketing_agent.py] → output/marketing/*_marketing.json
    └─ Prompts especializados + GPT-4
```

**💡 Vantagens do Modo API:**
- ⚡ Mais rápido (sem tempo de download)
- 💾 Não usa espaço em disco
- 🔄 Mais escalável
- 🎯 Foco no processamento, não no gerenciamento de arquivos