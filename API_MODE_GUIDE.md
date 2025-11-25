# 🚀 Guia do Modo API - Transcrição Sem Download

## 📝 Resumo

Nova funcionalidade que permite processar vídeos do YouTube **sem baixar arquivos MP3 localmente**. A transcrição é feita diretamente via API do OpenAI Whisper, tornando o processo mais rápido, limpo e escalável.

## ✨ Benefícios

### Antes (Modo Tradicional)
```
YouTube → Download MP3 (5-10min) → Salvar em disco (500MB+) → Transcrever (10-15min)
Total: ~20-25 minutos + 500MB por episódio
```

### Agora (Modo API)
```
YouTube → Extrair URL → API Whisper (3-5min) → JSON estruturado
Total: ~3-5 minutos + 0MB de áudio salvo
```

### Vantagens
- ⚡ **4-5x mais rápido** 
- 💾 **Economia de disco**: Não salva arquivos MP3
- 🎯 **Pipeline simplificado**: Menos etapas = menos pontos de falha
- 🔄 **Escalável**: Processa múltiplos vídeos em paralelo
- 🧹 **Mais limpo**: Sem necessidade de gerenciar data/ e limpar arquivos temporários

## 🎯 Quando Usar Cada Modo

### Use o Modo API quando:
- ✅ Você tem acesso à OpenAI API (OPENAI_API_KEY configurado)
- ✅ Quer processar muitos vídeos rapidamente
- ✅ Tem banda larga estável
- ✅ Não precisa dos arquivos de áudio originais
- ✅ Quer reduzir uso de disco

### Use o Modo Tradicional quando:
- ✅ Precisa dos arquivos MP3 para outros fins
- ✅ Quer processar offline (sem internet)
- ✅ Precisa de diarização local (pyannote)
- ✅ Tem GPU potente para processar localmente
- ✅ Quer economizar custos da API

## 📋 Como Usar

### 1. Configuração Inicial

```bash
# Certifique-se de que o .env está configurado
cat .env
```

Deve conter:
```bash
OPENAI_API_KEY=sk-proj-...  # OBRIGATÓRIO para modo API
HF_TOKEN=hf_...              # Opcional (só se usar diarização)
```

### 2. Comandos Básicos

#### Processar Playlist da Outliers (Recomendado)

```bash
# Processar primeiros 5 vídeos
python main.py outliers-api --max-videos 5

# Processar todos os vídeos (cuidado com custos!)
python main.py outliers-api

# Com tom técnico
python main.py outliers-api --max-videos 10 --tone technical
```

#### Processar Playlist Customizada

```bash
python main.py process-playlist-api \
  --playlist-url "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID" \
  --max-videos 5 \
  --tone didactic \
  --api-provider openai
```

#### Pular Etapas (Usar Outputs Existentes)

```bash
# Usar transcrições já salvas, apenas fazer análise e marketing
python main.py process-playlist-api \
  --skip-transcription \
  --max-videos 5

# Apenas transcrever, sem análise/marketing
python main.py process-playlist-api \
  --skip-analysis \
  --skip-marketing \
  --max-videos 5
```

### 3. Teste Rápido

```bash
# Testar com 1 vídeo
python main.py test
```

## 💡 Detalhes Técnicos

### Fluxo do Modo API

1. **Extração de Metadados** (yt-dlp)
   - Obtém título, descrição, duração do vídeo
   - Lista vídeos da playlist
   
2. **Áudio Temporário** (em memória)
   - Extrai stream de áudio sem salvar no disco
   - Mantém apenas o necessário para enviar à API
   
3. **Transcrição via API** (OpenAI Whisper)
   - Modelo: `whisper-1`
   - Format: `verbose_json` (com timestamps)
   - Response: JSON estruturado com segmentos
   
4. **Estruturação** (Pydantic)
   - Converte resposta da API para `TranscriptOutput`
   - Valida schema
   - Salva em `output/transcripts/`

5. **Análise e Marketing** (igual ao modo tradicional)
   - RAG + GPT-4 para análise de investimento
   - LangChain para geração de conteúdo

### Limitações do Modo API

#### ⚠️ O que NÃO está incluído:

- **Diarização local**: Não identifica speakers (retorna `UNKNOWN`)
- **Identificação HOST/GUEST**: Não distingue quem é quem
- **Múltiplos speakers**: Trata todo áudio como um único speaker
- **Alinhamento fino**: Timestamps são da API, não word-level

#### 💡 Solução:

Para podcasts que **realmente precisam** de identificação de speakers:
1. Use o modo tradicional para diarização
2. Ou considere usar a API + pós-processamento de diarização

Para conteúdo onde **não importa quem fala** (ex: tutoriais, palestras solo):
- Modo API é **perfeito**!

## 💰 Custos Estimados

### OpenAI Whisper API Pricing (Jan 2024)
- **$0.006 por minuto** de áudio
- Episódio de 60min = ~$0.36
- Playlist de 50 episódios = ~$18

### Comparação com Modo Local
- **Custo**: $0 (usa GPU local)
- **Tempo**: 4-5x mais lento
- **Hardware**: Requer GPU potente (NVIDIA)

**Recomendação**: Para produção, use modo API. Para testes/desenvolvimento, use modo local.

## 📊 Estrutura de Saída

### O que é gerado:

```
output/
├── transcripts/
│   ├── <video_id>.json          # Transcrição estruturada
│   └── ...
├── analyses/
│   ├── <video_id>_analysis.json  # Análise de investimento
│   └── ...
├── marketing/
│   ├── <video_id>_marketing.json # Conteúdo de marketing
│   └── ...
└── pipeline_summary_<timestamp>.json  # Estatísticas
```

### O que NÃO é gerado:

```
data/                              # ❌ Sem pasta de áudios
├── *.mp3                          # ❌ Sem arquivos MP3
└── *.wav                          # ❌ Sem arquivos WAV
```

## 🔧 Configuração do `master_pipeline_api.py`

### Opções de Inicialização

```python
from src.master_pipeline_api import MasterPipelineAPI

# Configuração padrão (OpenAI)
pipeline = MasterPipelineAPI(
    output_dir="output",
    api_provider="openai"  # ou "google" (futuro)
)

# Processar
results = pipeline.process_playlist(
    playlist_url="https://youtube.com/playlist?list=...",
    max_videos=5,
    marketing_tone="didactic",
    skip_transcription=False,
    skip_analysis=False,
    skip_marketing=False
)
```

### Função Helper

```python
from src.master_pipeline_api import process_outliers_playlist_api

# Uma linha para processar tudo
results = process_outliers_playlist_api(
    max_videos=5,
    marketing_tone="technical"
)
```

## 🎓 Exemplos Práticos

### Exemplo 1: Processar 3 episódios rapidamente

```bash
python main.py outliers-api --max-videos 3
```

**Output esperado:**
```
🚀 Processando Playlist da Outliers (VIA API)
[1/3] TRANSCRIÇÃO VIA API
✓ [1] Gestor discute Small Caps 2024
✓ [2] Análise do Mercado Imobiliário
✓ [3] Perspectivas para Renda Fixa

[2/3] ANÁLISE DE INVESTIMENTO
✓ Análise completa: 3/3 sucessos

[3/3] GERAÇÃO DE MARKETING
✓ Marketing completo: 3/3 sucessos

✓ PIPELINE CONCLUÍDO (VIA API)
Transcrições: 3
Análises: 3
Marketing: 3
```

### Exemplo 2: Apenas transcrever (sem análise/marketing)

```bash
python main.py process-playlist-api \
  --max-videos 10 \
  --skip-analysis \
  --skip-marketing
```

**Uso:** Quando você quer apenas as transcrições para revisar antes de processar análises.

### Exemplo 3: Reprocessar análises (transcrições já existem)

```bash
python main.py process-playlist-api \
  --skip-transcription \
  --max-videos 10
```

**Uso:** Quando mudou prompts de análise/marketing e quer reprocessar sem re-transcrever.

## 🐛 Troubleshooting

### Erro: "OPENAI_API_KEY not found"

```bash
# Verifique o .env
cat .env | grep OPENAI_API_KEY

# Se não existir, adicione
echo "OPENAI_API_KEY=sk-proj-..." >> .env
```

### Erro: "Rate limit exceeded"

A API do OpenAI tem limites de requisições. Soluções:

```bash
# 1. Processar menos vídeos por vez
python main.py outliers-api --max-videos 3

# 2. Aguardar 1 minuto e tentar novamente

# 3. Verificar limites da sua conta OpenAI
```

### Erro: "YouTube extraction failed"

```bash
# Certifique-se de que yt-dlp está atualizado
pip install --upgrade yt-dlp

# Teste a URL manualmente
yt-dlp --print-json "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Transcrição vazia ou incompleta

Causas possíveis:
1. Vídeo muito longo (>25MB de áudio)
2. Conexão instável durante upload
3. Vídeo sem áudio ou com áudio corrompido

Solução:
```bash
# Use o modo tradicional para este vídeo específico
python main.py process data/audio.mp3
```

## 🎯 Melhores Práticas

### ✅ Faça:

1. **Teste com poucos vídeos primeiro**
   ```bash
   python main.py outliers-api --max-videos 3
   ```

2. **Monitore custos**
   - 50 episódios de 1h = ~$18
   - Verifique usage em https://platform.openai.com/usage

3. **Use skip-* quando reprocessar**
   ```bash
   # Não re-transcreva se já tem JSONs
   python main.py process-playlist-api --skip-transcription
   ```

4. **Revise transcrições antes de análise**
   ```bash
   # Primeiro: apenas transcrever
   python main.py process-playlist-api --skip-analysis --skip-marketing
   
   # Depois: revisar JSONs em output/transcripts/
   
   # Por fim: processar análises
   python main.py process-playlist-api --skip-transcription
   ```

### ❌ Evite:

1. **Processar playlist inteira sem teste**
   ```bash
   # NÃO faça isso na primeira vez!
   python main.py outliers-api  # processa TUDO
   ```

2. **Re-transcrever desnecessariamente**
   - Custos desnecessários
   - Perda de tempo
   - Use `--skip-transcription` quando já tem JSONs

3. **Ignorar erros da API**
   - Se um vídeo falhar, investigue antes de continuar

## 🚀 Próximos Passos

1. **Teste a funcionalidade**:
   ```bash
   python main.py test
   ```

2. **Processe alguns episódios**:
   ```bash
   python main.py outliers-api --max-videos 5
   ```

3. **Revise os resultados**:
   ```bash
   # Veja as transcrições
   ls output/transcripts/
   
   # Veja as análises
   ls output/analyses/
   
   # Veja o marketing
   ls output/marketing/
   ```

4. **Escale para produção**:
   ```bash
   # Processe a playlist completa
   python main.py outliers-api --max-videos 50
   ```

## 📚 Referências

- **OpenAI Whisper API**: https://platform.openai.com/docs/guides/speech-to-text
- **yt-dlp**: https://github.com/yt-dlp/yt-dlp
- **LangChain**: https://python.langchain.com/

---

**💡 Dica Final**: Para a maioria dos casos, o modo API é **superior**. Use-o como padrão e recorra ao modo tradicional apenas quando precisar de diarização detalhada ou processar offline.
