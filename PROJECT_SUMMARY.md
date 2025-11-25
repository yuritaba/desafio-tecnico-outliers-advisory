# Sumário do Projeto - Pipeline de Podcasts Financeiros

## 📊 Visão Geral

Sistema end-to-end para processar playlists de podcasts financeiros do YouTube, extraindo teses de investimento e gerando conteúdo de marketing automatizado.

## 🎯 Objetivo do Desafio

Criar um agente inteligente que:
1. ✅ Extrai áudio de playlist do YouTube
2. ✅ Transcreve com identificação de speakers (Host + Gestor Convidado)
3. ✅ Analisa teses de investimento usando RAG/LLMs (LangChain)
4. ✅ Gera conteúdo de marketing estruturado (LinkedIn, carrosséis, citações)

**Playlist Target:** https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti

## 📁 Estrutura do Código

### Módulos Principais

| Arquivo | LOC | Função |
|---------|-----|--------|
| `src/youtube_extractor.py` | ~200 | Download de playlists do YouTube |
| `src/transcriber.py` | 254 | Transcrição (Whisper/OpenAI/WhisperX) |
| `src/diarizer.py` | 278 | Diarização de speakers (pyannote) |
| `src/aligner.py` | 293 | Alinhamento temporal (IoU-based) |
| `src/speaker_identifier.py` | 355 | Identificação HOST/GUEST (heurísticas) |
| `src/text_cleaner.py` | 285 | Limpeza e normalização de texto |
| `src/pipeline.py` | 324 | Orquestrador de transcrição |
| `src/investment_agent.py` | ~290 | Análise com RAG + GPT-4 |
| `src/marketing_agent.py` | ~350 | Geração de conteúdo marketing |
| `src/master_pipeline.py` | ~360 | Pipeline completo end-to-end |
| `src/models.py` | 366 | Modelos Pydantic (validação) |
| `src/utils.py` | 288 | Funções auxiliares |
| `main.py` | ~370 | CLI com 6 comandos |

**Total:** ~3,400 linhas de código Python

### Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        MASTER PIPELINE                           │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┬──────────────┐
        ▼                     ▼                     ▼              ▼
   [YouTube]           [Transcrição]          [Análise]      [Marketing]
   Extractor             Pipeline              Agent            Agent
        │                     │                     │              │
        ├─ yt-dlp            ├─ Whisper           ├─ LangChain   ├─ GPT-4
        ├─ MP3 conversion    ├─ pyannote          ├─ FAISS      ├─ Prompts
        └─ Metadata          ├─ IoU alignment     ├─ RAG        └─ Templates
                             ├─ Heuristics        └─ GPT-4
                             └─ Text cleaning
```

## 🚀 Comandos CLI

```bash
# 1. Teste rápido (1 vídeo)
python main.py test

# 2. Processar playlist Outliers
python main.py outliers --max-videos 5 --tone didactic

# 3. Pipeline completo customizado
python main.py process-playlist \
  --playlist-url "https://..." \
  --max-videos 10 \
  --tone technical

# 4. Análise individual
python main.py analyze output/transcripts/ep_001.json

# 5. Marketing individual
python main.py marketing \
  output/analyses/ep_001_analysis.json \
  output/transcripts/ep_001.json

# 6. Reprocessar apenas marketing
python main.py process-playlist \
  --skip-download \
  --skip-transcription \
  --skip-analysis
```

## 🔧 Tecnologias Utilizadas

### Core
- **Python 3.9+**: Linguagem base
- **Pydantic 2.0**: Validação de dados
- **Click**: Framework CLI
- **python-dotenv**: Gerenciamento de env vars

### Áudio & Transcrição
- **yt-dlp**: Download do YouTube
- **ffmpeg**: Processamento de áudio
- **OpenAI Whisper**: Transcrição ASR
- **pyannote.audio 3.0**: Diarização de speakers
- **pydub + librosa**: Manipulação de áudio

### Análise & Marketing (LLMs)
- **LangChain**: Framework RAG/LLM
- **OpenAI API (GPT-4)**: Geração de conteúdo
- **FAISS**: Vector store para RAG
- **tiktoken**: Tokenização

### ML/AI
- **PyTorch 2.0**: Backend ML
- **Transformers**: Modelos HuggingFace

## 📤 Saídas Geradas

### 1. Transcrição (`output/transcripts/*.json`)
```json
{
  "metadata": {
    "episode_id": "ep_001_abc123",
    "title": "Teses 2024 com Gestor XYZ",
    "duration_seconds": 3600
  },
  "utterances": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Olá, bem-vindos ao podcast...",
      "speaker_id": "SPEAKER_00",
      "speaker_name": "João Silva",
      "speaker_role": "HOST"
    }
  ],
  "participants": [
    {"role": "HOST", "name": "João Silva"},
    {"role": "GUEST", "name": "Maria Santos"}
  ]
}
```

### 2. Análise (`output/analyses/*_analysis.json`)
```json
{
  "episode_id": "ep_001_abc123",
  "title": "...",
  "analysis": "1. TESE PRINCIPAL DE INVESTIMENTO\n...",
  "metadata": {
    "model": "gpt-4",
    "method": "rag"
  }
}
```

### 3. Marketing (`output/marketing/*_marketing.json`)
```json
{
  "episode_id": "ep_001_abc123",
  "linkedin_post": "📈 As 3 principais teses...",
  "carousel_slides": [
    {
      "title": "Por que Small Caps?",
      "bullets": ["...", "...", "..."]
    }
  ],
  "quotes": [
    {
      "quote": "O mercado está precificando...",
      "speaker_name": "Maria Santos",
      "speaker_role": "GUEST"
    }
  ],
  "executive_summary": "Este episódio apresenta..."
}
```

## 📊 Capacidades

| Recurso | Status | Detalhes |
|---------|--------|----------|
| Download YouTube | ✅ | Playlists completas, metadados |
| Transcrição | ✅ | Whisper local/API, WhisperX |
| Diarização | ✅ | pyannote.audio, WhisperX |
| Identificação Speakers | ✅ | Heurísticas (4 métricas) |
| Análise RAG | ✅ | LangChain + FAISS + GPT-4 |
| Post LinkedIn | ✅ | 150-300 palavras + hashtags |
| Carrosséis | ✅ | 3-7 slides com bullets |
| Citações | ✅ | Top 5 com atribuição |
| Sumário Executivo | ✅ | Para equipe marketing |
| Modos de Tom | ✅ | Technical vs Didactic |
| Batch Processing | ✅ | Múltiplos episódios |
| CLI Interativo | ✅ | 6 comandos principais |

## 🎯 Diferenciadores

1. **Pipeline Completo**: YouTube → Transcrição → Análise → Marketing (end-to-end)
2. **RAG Inteligente**: Análise contextual para episódios longos (1h+)
3. **Multi-Modal**: Suporta múltiplos backends (Whisper local/API, pyannote/WhisperX)
4. **Validação Rigorosa**: Pydantic models para garantir estrutura dos dados
5. **Escalável**: Batch processing, etapas puladas, reprocessamento seletivo
6. **Modular**: Cada componente pode ser usado independentemente
7. **Tom Customizável**: Technical (profissionais) vs Didactic (público geral)
8. **Citações Atribuídas**: Extração automática com nome do speaker

## 📈 Métricas Esperadas

Para playlist típica de 20 episódios (~1h cada):

| Etapa | Tempo/Ep | Total (20 eps) |
|-------|----------|----------------|
| Download | 2-5 min | 40-100 min |
| Transcrição (API) | 1-2 min | 20-40 min |
| Diarização | 3-5 min | 60-100 min |
| Análise RAG | 1-2 min | 20-40 min |
| Marketing | 30-60s | 10-20 min |
| **TOTAL** | **8-15 min** | **2.5-5h** |

**Custo estimado (OpenAI API):**
- Transcrição: ~$0.06/min → ~$72 (20h)
- GPT-4 análise: ~$0.10/ep → ~$2
- GPT-4 marketing: ~$0.05/ep → ~$1
- **Total: ~$75** para 20 episódios

## 🔐 Segurança

- Chaves API carregadas de `.env` (não versionado)
- `.gitignore` configurado
- Token HF para pyannote.audio
- Validação de entrada com Pydantic

## 🧪 Testado Com

- ✅ macOS (M1/M2)
- ✅ Python 3.9, 3.10, 3.11
- ✅ OpenAI API (gpt-4, gpt-3.5-turbo)
- ✅ PyTorch 2.0+ (CPU e CUDA)

## 📝 Documentação

- `README.md` - Documentação completa (20KB)
- `QUICKSTART.md` - Instalação rápida
- `examples.py` - 10 exemplos de uso
- `PROJECT_SUMMARY.md` (este arquivo) - Visão geral

## 🎓 Como Usar

```python
# Uso mais simples
from src import process_outliers_playlist

results = process_outliers_playlist(max_videos=5)

# Saídas em:
# - output/transcripts/*.json
# - output/analyses/*_analysis.json
# - output/marketing/*_marketing.json
```

## 🏆 Conclusão

Sistema completo e robusto que automatiza toda a pipeline de:
- Extração de conteúdo do YouTube
- Transcrição profissional com diarização
- Análise inteligente de teses de investimento (RAG)
- Geração de conteúdo de marketing pronto para publicação

**Pronto para produção** com CLI, validação, logging, e tratamento de erros.

---

**Desenvolvido para:** Outliers Advisory - Desafio Técnico 2024  
**Autor:** Yuri Tabacof  
**Versão:** 2.0.0  
**Licença:** MIT
