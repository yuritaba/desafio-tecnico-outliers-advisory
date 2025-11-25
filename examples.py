"""
Exemplos de uso do pipeline de podcasts financeiros.
"""

# ==============================================================================
# EXEMPLO 1: Pipeline Completo - Outliers Advisory
# ==============================================================================

from src import process_outliers_playlist

# Processar os 3 primeiros vídeos da playlist
results = process_outliers_playlist(
    max_videos=3,
    marketing_tone="didactic"
)

print(f"Processados: {len(results['transcriptions'])} episódios")
print(f"Análises: {len(results['analyses'])}")
print(f"Conteúdo de marketing: {len(results['marketing'])}")


# ==============================================================================
# EXEMPLO 2: Pipeline Customizado
# ==============================================================================

from src import MasterPipeline

pipeline = MasterPipeline(
    data_dir="meus_audios",
    output_dir="meus_resultados"
)

results = pipeline.process_playlist(
    playlist_url="https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    max_videos=5,
    marketing_tone="technical",  # Tom técnico para profissionais
    skip_download=False,
    skip_transcription=False,
    skip_analysis=False,
    skip_marketing=False
)


# ==============================================================================
# EXEMPLO 3: Apenas Download do YouTube
# ==============================================================================

from src import YouTubePlaylistExtractor

extractor = YouTubePlaylistExtractor(output_dir="data")

# Obter info da playlist
info = extractor.get_playlist_info(
    "https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti"
)
print(f"Playlist: {info['title']}")
print(f"Total de vídeos: {info['video_count']}")

# Baixar apenas os 2 primeiros
downloads = extractor.download_playlist(
    "https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    max_videos=2
)

for download in downloads:
    if download['success']:
        print(f"✓ {download['title']}")
        print(f"  Arquivo: {download['audio_path']}")


# ==============================================================================
# EXEMPLO 4: Apenas Transcrição
# ==============================================================================

from src import PodcastPipeline

pipeline = PodcastPipeline()

transcript = pipeline.process(
    audio_path="data/ep_001_abc123.mp3",
    episode_id="ep_001",
    output_path="output/transcripts/ep_001.json"
)

print(f"Transcrição: {len(transcript.utterances)} falas")
for participant in transcript.participants:
    print(f"  - {participant.name} ({participant.role})")


# ==============================================================================
# EXEMPLO 5: Apenas Análise de Investimento
# ==============================================================================

from src import InvestmentAnalysisAgent
from src.models import TranscriptOutput
import json

# Carregar transcrição existente
with open("output/transcripts/ep_001.json") as f:
    data = json.load(f)
    transcript = TranscriptOutput(**data)

# Analisar
agent = InvestmentAnalysisAgent(model_name="gpt-4")
analysis = agent.analyze_transcript(transcript, use_rag=True)

print(f"Tese de investimento: {analysis['title']}")
print(analysis['analysis'])


# ==============================================================================
# EXEMPLO 6: Apenas Marketing
# ==============================================================================

from src import MarketingAgent

agent = MarketingAgent(model_name="gpt-4", temperature=0.7)

# Gerar post LinkedIn
linkedin_post = agent.generate_linkedin_post(
    analysis=analysis,
    tone="didactic"
)

print("POST LINKEDIN:")
print(linkedin_post)

# Gerar carrossel
carousel = agent.generate_carousel(
    analysis=analysis,
    num_slides=5,
    tone="technical"
)

for i, slide in enumerate(carousel, 1):
    print(f"\nSLIDE {i}: {slide['title']}")
    for bullet in slide['bullets']:
        print(f"  • {bullet}")

# Extrair citações
transcript_text = "\n".join([
    f"{u.speaker_name}: {u.text}"
    for u in transcript.utterances
])

quotes = agent.extract_quotes(
    transcript_text,
    analysis['participants'],
    num_quotes=5
)

for quote in quotes:
    print(f'\n"{quote["quote"]}"')
    print(f"  - {quote['speaker_name']} ({quote['speaker_role']})")


# ==============================================================================
# EXEMPLO 7: Pacote Completo de Marketing
# ==============================================================================

package = agent.generate_full_marketing_package(
    analysis=analysis,
    transcript_text=transcript_text,
    tone="didactic"
)

print(f"Episódio: {package['episode_id']}")
print(f"Post LinkedIn: {len(package['linkedin_post'])} caracteres")
print(f"Carrossel: {len(package['carousel_slides'])} slides")
print(f"Citações: {len(package['quotes'])} frases")
print(f"\nSumário Executivo:")
print(package['executive_summary'])


# ==============================================================================
# EXEMPLO 8: Batch de Análises
# ==============================================================================

# Analisar múltiplas transcrições
transcripts = []
for path in ["ep_001.json", "ep_002.json", "ep_003.json"]:
    with open(f"output/transcripts/{path}") as f:
        data = json.load(f)
        transcripts.append(TranscriptOutput(**data))

agent = InvestmentAnalysisAgent()
analyses = agent.analyze_batch(transcripts, use_rag=True)

# Criar sumário executivo consolidado
executive_summary = agent.create_executive_summary(analyses)
print(executive_summary)


# ==============================================================================
# EXEMPLO 9: Pipeline com Etapas Seletivas
# ==============================================================================

# Reprocessar apenas marketing (pular download, transcrição e análise)
pipeline = MasterPipeline()

results = pipeline.process_playlist(
    playlist_url="https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    max_videos=10,
    marketing_tone="technical",
    skip_download=True,        # Pular - usar áudios existentes
    skip_transcription=True,   # Pular - usar JSONs existentes
    skip_analysis=True,        # Pular - usar análises existentes
    skip_marketing=False       # Executar apenas marketing
)


# ==============================================================================
# EXEMPLO 10: Uso com Configurações Customizadas
# ==============================================================================

from src import Transcriber, Diarizer, Aligner, SpeakerIdentifier, TextCleaner

# Criar componentes customizados
transcriber = Transcriber(backend="openai")  # Usar API OpenAI
diarizer = Diarizer(backend="pyannote")
aligner = Aligner()
identifier = SpeakerIdentifier()
cleaner = TextCleaner()

# Processar manualmente
audio_path = "data/podcast.mp3"

# 1. Transcrever
segments = transcriber.transcribe(audio_path)

# 2. Diarizar
diarization = diarizer.diarize(audio_path)

# 3. Alinhar
aligned_segments = aligner.align(segments, diarization)

# 4. Identificar speakers
identified_segments = identifier.identify(aligned_segments)

# 5. Limpar texto
for segment in identified_segments:
    segment.text = cleaner.clean(segment.text)

print(f"Processamento manual: {len(identified_segments)} segmentos")
