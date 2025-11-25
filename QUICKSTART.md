# Guia de Instalação Rápida

## Pré-requisitos

- Python 3.9+
- ffmpeg (para processamento de áudio)
- Chave API OpenAI
- Token Hugging Face

## Instalação

### 1. Instalar ffmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Baixar de: https://ffmpeg.org/download.html

### 2. Clonar/Baixar o Projeto

```bash
cd /caminho/do/projeto
```

### 3. Criar Ambiente Virtual (Recomendado)

```bash
python -m venv venv

# Ativar (macOS/Linux)
source venv/bin/activate

# Ativar (Windows)
venv\Scripts\activate
```

### 4. Instalar Dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Nota:** A instalação pode demorar alguns minutos devido ao PyTorch e outros pacotes grandes.

### 5. Configurar Variáveis de Ambiente

```bash
cp .env.example .env
```

Editar `.env` e adicionar:
```bash
OPENAI_API_KEY=sk-proj-...
HF_TOKEN=hf_...
```

**Obter tokens:**
- OpenAI: https://platform.openai.com/api-keys
- Hugging Face: https://huggingface.co/settings/tokens
  - Aceitar termos: https://huggingface.co/pyannote/speaker-diarization

### 6. Testar Instalação

```bash
python main.py test
```

Isso irá:
- Baixar 1 vídeo da playlist
- Transcrever e diarizar
- Analisar tese de investimento
- Gerar conteúdo de marketing

## Troubleshooting

### Erro: "ImportError: No module named 'torch'"

```bash
# CPU apenas
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Com GPU (CUDA 11.8)
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Erro: "ffmpeg not found"

Certifique-se que ffmpeg está instalado e no PATH:
```bash
ffmpeg -version
```

### Erro: "pyannote.audio authentication"

1. Criar conta em https://huggingface.co/
2. Aceitar termos em https://huggingface.co/pyannote/speaker-diarization
3. Aceitar termos em https://huggingface.co/pyannote/segmentation
4. Gerar token em https://huggingface.co/settings/tokens
5. Adicionar ao .env: `HF_TOKEN=hf_...`

### Erro: "CUDA out of memory"

Usar backend OpenAI (API) em vez de modelos locais:
```bash
export TRANSCRIPTION_BACKEND=openai
```

## Uso Básico

```bash
# Processar 3 vídeos em modo didático
python main.py outliers --max-videos 3 --tone didactic

# Processar em modo técnico
python main.py outliers --max-videos 5 --tone technical

# Ver todos os comandos
python main.py --help
```

## Estrutura de Saída

Após processar, os resultados estarão em:

```
output/
├── transcripts/       # Transcrições JSON
├── analyses/          # Análises de investimento JSON
├── marketing/         # Conteúdo de marketing JSON
└── pipeline_summary_*.json  # Estatísticas
```

## Próximos Passos

1. Ler `README.md` completo
2. Ver `examples.py` para uso programático
3. Processar playlist completa: `python main.py outliers`

## Suporte

Para issues ou dúvidas, consultar:
- README.md - Documentação completa
- examples.py - Exemplos de código
- main.py - Comandos CLI disponíveis
