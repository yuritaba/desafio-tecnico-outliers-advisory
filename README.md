# 🎙️ Pipeline de Processamento de Podcasts Financeiros

Sistema completo para extrair, transcrever, analisar e gerar conteúdo de marketing a partir de podcasts financeiros no YouTube.

## 🎯 Objetivo

Processar a playlist de podcasts da **Outliers Advisory** para:

1. **Extrair áudio** de vídeos do YouTube (ou transcrever diretamente via API)
2. **Transcrever e identificar speakers** (Host e Gestor Convidado)
3. **Analisar teses de investimento** usando RAG e LLMs
4. **Gerar conteúdo de marketing** estruturado para LinkedIn

## ⚡ Novidade: Transcrição via API (Sem Download Local)

**Nova funcionalidade adicionada!** Agora você pode processar vídeos do YouTube **sem baixar MP3 localmente**:

- ✅ **Mais rápido**: Transcrição direta via OpenAI Whisper API
- ✅ **Sem usar disco**: Não salva arquivos de áudio
- ✅ **Mais limpo**: Pipeline simplificado sem gerenciamento de arquivos temporários
- ✅ **Escalável**: Processa múltiplos vídeos em paralelo

### Comandos API disponíveis:

```bash
# Processar playlist via API (recomendado)
python main.py process-playlist-api --max-videos 3

# Atalho para playlist da Outliers via API
python main.py outliers-api --max-videos 5

# Especificar provedor da API
python main.py outliers-api --api-provider openai
```

## 🚀 Quick Start

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas chaves:
# OPENAI_API_KEY=sk-...
# HF_TOKEN=hf_...

# 3. Testar com 1 vídeo (VIA API - SEM DOWNLOAD)
python main.py test

# 4. Processar playlist completa VIA API (recomendado)
python main.py outliers-api --max-videos 5

# 5. Ou usar o modo tradicional (com download)
python main.py outliers --max-videos 5
```

## 📋 Funcionalidades

### 1. Extração do YouTube

**Modo Tradicional (com download):**
- Download automático de playlists
- Conversão para formato de áudio (MP3)
- Extração de metadados (título, descrição, duração)

**Modo API (novo - recomendado):**
- ✨ Transcrição direta via OpenAI Whisper API
- ✨ Sem download de arquivos MP3
- ✨ Processamento mais rápido e eficiente
- ✨ Menor uso de disco e recursos

### 2. Transcrição e Diarização

- **Transcrição**: OpenAI Whisper (local, API ou WhisperX)
- **Diarização**: pyannote.audio 3.0 ou WhisperX
- **Identificação de Speakers**: Heurísticas para detectar HOST e GUEST
- **Limpeza de Texto**: Correção de termos financeiros

### 3. Análise de Investimento (RAG + LLMs)

Extrai de cada episódio:
- **Tese Principal de Investimento**
- **Ativos/Setores Mencionados**
- **Contexto Macroeconômico**
- **Horizonte Temporal e Riscos**
- **Citações-Chave com Atribuição**

### 4. Geração de Marketing

Cria conteúdo estruturado:
- **Post LinkedIn** (150-300 palavras, com hashtags)
- **Carrossel** (5 slides com título + bullets)
- **Citações** (5 frases impactantes com speaker)
- **Sumário Executivo** para equipe de marketing

Modos disponíveis:
- **Technical**: Para profissionais do mercado financeiro
- **Didactic**: Para público geral (padrão)

## 🔧 Comandos CLI Disponíveis

### 🌟 Comandos API (Recomendado - Sem Download)

```bash
# Processar playlist via API (OpenAI Whisper)
python main.py process-playlist-api --max-videos 5 --tone didactic

# Atalho para a playlist da Outliers via API
python main.py outliers-api --max-videos 3

# Com provedor específico
python main.py outliers-api --api-provider openai --max-videos 10

# Pular etapas específicas
python main.py process-playlist-api \
  --skip-transcription \  # Usar JSONs existentes
  --skip-analysis \       # Pular análise
  --skip-marketing        # Pular marketing
```

### 📥 Comandos Tradicionais (Com Download)

```bash
# Processar playlist baixando MP3s localmente
python main.py process-playlist --max-videos 5 --tone technical

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