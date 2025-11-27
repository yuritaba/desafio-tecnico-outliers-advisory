#!/usr/bin/env python3
"""
Script principal CLI para processamento de podcasts financeiros da Outliers Advisory.

Pipeline completo:
YouTube → Transcrição → Análise de Investimento → Marketing
"""

import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
from colorlog import ColoredFormatter
from dotenv import load_dotenv

# Suprimir avisos de deprecação do yt-dlp
warnings.filterwarnings('ignore', message='.*Python version.*deprecated.*')

# Carregar variáveis de ambiente (.env)
load_dotenv()

# ==== IMPORTS DO PROJETO ====
# Ajuste os caminhos conforme sua estrutura real
from src.master_pipeline import MasterPipeline, process_outliers_playlist
from src.master_pipeline_api import MasterPipelineAPI, process_outliers_playlist_api
from src.pipeline import PodcastPipeline
from src.utils import validate_audio_file
from src.investment_agent import InvestmentAnalysisAgent
from src.marketing_agent import MarketingAgent
from src.models import TranscriptOutput


# =====================================================================
# LOGGING
# =====================================================================

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configura logging com cores e retorna o logger principal."""
    formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger("podcast_pipeline")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    return logger


# =====================================================================
# CLI ROOT
# =====================================================================

@click.group()
@click.version_option(version="2.0.0")
def cli() -> None:
    """
    Pipeline de Processamento de Podcasts Financeiros.

    YouTube → Transcrição → Diarização → Análise de Investimento → Marketing.
    """
    pass


# =====================================================================
# COMANDO: process-playlist
# =====================================================================

@cli.command("process-playlist")
@click.option(
    '--playlist-url',
    default="https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    help='URL da playlist do YouTube',
)
@click.option(
    '--max-videos',
    type=int,
    default=None,
    help='Número máximo de vídeos a processar (None = todos).',
)
@click.option(
    '--tone',
    type=click.Choice(['technical', 'didactic']),
    default='didactic',
    help='Tom do conteúdo de marketing (technical ou didactic).',
)
@click.option(
    '--skip-download',
    is_flag=True,
    help='Pular download (usar áudios já existentes no disco).',
)
@click.option(
    '--skip-transcription',
    is_flag=True,
    help='Pular transcrição (usar JSONs existentes).',
)
@click.option(
    '--skip-analysis',
    is_flag=True,
    help='Pular análise de investimento.',
)
@click.option(
    '--skip-marketing',
    is_flag=True,
    help='Pular geração de conteúdos de marketing.',
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Nível de log (padrão: INFO).',
)
def process_playlist(
    playlist_url: str,
    max_videos: Optional[int],
    tone: str,
    skip_download: bool,
    skip_transcription: bool,
    skip_analysis: bool,
    skip_marketing: bool,
    log_level: str,
) -> None:
    """
    Processa uma playlist completa do YouTube.

    Exemplo:
        python main.py process-playlist --max-videos 3 --tone didactic
    """
    logger = setup_logging(log_level)
    try:
        pipeline = MasterPipeline()
        results: Dict[str, Any] = pipeline.process_playlist(
            playlist_url=playlist_url,
            max_videos=max_videos,
            marketing_tone=tone,
            skip_download=skip_download,
            skip_transcription=skip_transcription,
            skip_analysis=skip_analysis,
            skip_marketing=skip_marketing,
        )

        click.echo("\n" + "=" * 80)
        click.echo(click.style("✓ PIPELINE CONCLUÍDO", fg="green", bold=True))
        click.echo("=" * 80)
        click.echo(f"Transcrições: {len(results.get('transcriptions', []))}")
        click.echo(f"Análises:     {len(results.get('analyses', []))}")
        click.echo(f"Marketing:    {len(results.get('marketing', []))}")

        errors = results.get('errors', [])
        if errors:
            click.echo(click.style(f"\n⚠ Erros: {len(errors)}", fg="yellow"))
            for error in errors[:5]:
                click.echo(f"  - {error.get('stage', 'N/A')}: {error.get('episode_id', 'N/A')}")

        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("\n\nProcessamento interrompido pelo usuário.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro no pipeline: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# COMANDO: outliers (atalho da playlist)
# =====================================================================

@cli.command("outliers")
@click.option(
    '--max-videos',
    type=int,
    default=None,
    help='Número máximo de vídeos (None = todos).',
)
@click.option(
    '--tone',
    type=click.Choice(['technical', 'didactic']),
    default='didactic',
    help='Tom do conteúdo de marketing.',
)
def outliers(max_videos: Optional[int], tone: str) -> None:
    """
    Atalho para processar a playlist padrão da Outliers Advisory.

    Exemplo:
        python main.py outliers --max-videos 5 --tone technical
    """
    logger = setup_logging()
    try:
        click.echo(click.style("\n🚀 Processando Playlist da Outliers Advisory", fg="cyan", bold=True))
        results = process_outliers_playlist(
            max_videos=max_videos,
            marketing_tone=tone,
        )

        click.echo("\n" + click.style("✓ Completo!", fg="green", bold=True))
        click.echo(f"Transcrições: {len(results.get('transcriptions', []))}")
        click.echo(f"Análises:     {len(results.get('analyses', []))}")
        click.echo(f"Marketing:    {len(results.get('marketing', []))}")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("\n\nInterrompido pelo usuário.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# COMANDO: process-playlist-api (NOVO - transcrição via API sem download)
# =====================================================================

@cli.command("process-playlist-api")
@click.option(
    '--playlist-url',
    default="https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti",
    help='URL da playlist do YouTube',
)
@click.option(
    '--max-videos',
    type=int,
    default=None,
    help='Número máximo de vídeos a processar (None = todos).',
)
@click.option(
    '--tone',
    type=click.Choice(['technical', 'didactic']),
    default='didactic',
    help='Tom do conteúdo de marketing (technical ou didactic).',
)
@click.option(
    '--skip-transcription',
    is_flag=True,
    help='Pular transcrição (usar JSONs existentes).',
)
@click.option(
    '--skip-analysis',
    is_flag=True,
    help='Pular análise de investimento.',
)
@click.option(
    '--skip-marketing',
    is_flag=True,
    help='Pular geração de conteúdos de marketing.',
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Nível de log (padrão: INFO).',
)
def process_playlist_api(
    playlist_url: str,
    max_videos: Optional[int],
    tone: str,
    skip_transcription: bool,
    skip_analysis: bool,
    skip_marketing: bool,
    log_level: str,
) -> None:
    """
    Processa uma playlist via Google Cloud Speech-to-Text (SEM download local).

    Usa Google Cloud para transcrever diretamente a partir das URLs do YouTube,
    sem salvar arquivos localmente. Inclui diarização para Samuel e Convidado.

    Exemplo:
        python main.py process-playlist-api --max-videos 3
    """
    logger = setup_logging(log_level)
    try:
        click.echo(click.style("\n🚀 Processando Playlist via Google Cloud (SEM download)", fg="cyan", bold=True))
        
        pipeline = MasterPipelineAPI()
        results: Dict[str, Any] = pipeline.process_playlist(
            playlist_url=playlist_url,
            max_videos=max_videos,
            marketing_tone=tone,
            language="pt-BR",
            skip_transcription=skip_transcription,
            skip_analysis=skip_analysis,
            skip_marketing=skip_marketing,
        )

        click.echo("\n" + "=" * 80)
        click.echo(click.style("✓ PIPELINE CONCLUÍDO (Google Cloud)", fg="green", bold=True))
        click.echo("=" * 80)
        click.echo(f"Transcrições: {len(results.get('transcriptions', []))}")
        click.echo(f"Análises:     {len(results.get('analyses', []))}")
        click.echo(f"Marketing:    {len(results.get('marketing', []))}")

        errors = results.get('errors', [])
        if errors:
            click.echo(click.style(f"\n⚠ Erros: {len(errors)}", fg="yellow"))
            for error in errors[:5]:
                click.echo(f"  - {error.get('stage', 'N/A')}: {error.get('video_id', 'N/A')}")

        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("\n\nProcessamento interrompido pelo usuário.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro no pipeline API: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# COMANDO: outliers-api (atalho da playlist via API)
# =====================================================================

@cli.command("outliers-api")
@click.option(
    '--max-videos',
    type=int,
    default=None,
    help='Número máximo de vídeos (None = todos).',
)
@click.option(
    '--tone',
    type=click.Choice(['technical', 'didactic']),
    default='didactic',
    help='Tom do conteúdo de marketing.',
)
def outliers_api(max_videos: Optional[int], tone: str) -> None:
    """
    Atalho para processar a playlist da Outliers via Google Cloud Speech-to-Text.
    SEM download local - usa diarização para identificar Samuel e Convidado.

    Exemplo:
        python main.py outliers-api --max-videos 5
    """
    logger = setup_logging()
    try:
        click.echo(click.style("\n🚀 Processando Playlist da Outliers (Google Cloud)", fg="cyan", bold=True))
        results = process_outliers_playlist_api(
            max_videos=max_videos,
            marketing_tone=tone
        )

        click.echo("\n" + click.style("✓ Completo (Google Cloud)!", fg="green", bold=True))
        click.echo(f"Transcrições: {len(results.get('transcriptions', []))}")
        click.echo(f"Análises:     {len(results.get('analyses', []))}")
        click.echo(f"Marketing:    {len(results.get('marketing', []))}")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("\n\nInterrompido pelo usuário.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# COMANDO: process (um áudio local com pipeline completo STT+diarização)
# =====================================================================

@cli.command("process")
@click.argument('audio_path', type=click.Path(exists=True))
@click.option(
    '-o', '--output',
    type=click.Path(),
    help='Caminho do arquivo JSON de saída (padrão: output/<nome_audio>.json).',
)
@click.option('--episode-id', help='ID do episódio.')
@click.option('--title', help='Título do episódio.')
@click.option('--date', help='Data de publicação (ISO 8601).')
@click.option('--link', help='Link original do episódio (YouTube, etc.).')
@click.option('--host-name', help='Nome do host/apresentador.')
@click.option('--guest-names', help='Nomes dos convidados (separados por vírgula).')
@click.option(
    '--whisper-backend',
    type=click.Choice(['local', 'openai', 'whisperx']),
    default='local',
    help='Backend para transcrição (padrão: local).',
)
@click.option(
    '--whisper-model',
    default='large-v3',
    help='Modelo Whisper a usar (padrão: large-v3).',
)
@click.option(
    '--diarization-backend',
    type=click.Choice(['pyannote', 'whisperx']),
    default='pyannote',
    help='Backend para diarização (padrão: pyannote).',
)
@click.option(
    '--max-speakers',
    type=int,
    default=2,
    help='Número máximo de speakers esperados (padrão: 2).',
)
@click.option(
    '--language',
    default='pt',
    help='Código do idioma (padrão: pt).',
)
@click.option(
    '--no-clean',
    is_flag=True,
    help='Desabilita limpeza de texto (remoção de fillers etc.).',
)
@click.option(
    '--aggressive-clean',
    is_flag=True,
    help='Ativa limpeza agressiva de texto.',
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Nível de log (padrão: INFO).',
)
def process_command(
    audio_path: str,
    output: Optional[str],
    episode_id: Optional[str],
    title: Optional[str],
    date: Optional[str],
    link: Optional[str],
    host_name: Optional[str],
    guest_names: Optional[str],
    whisper_backend: str,
    whisper_model: str,
    diarization_backend: str,
    max_speakers: int,
    language: str,
    no_clean: bool,
    aggressive_clean: bool,
    log_level: str,
) -> None:
    """
    Processa um único episódio de podcast a partir de um arquivo de áudio.

    Exemplo:
        python main.py process podcast.mp3 -o output.json --host-name "João" --guest-names "Maria"
    """
    logger = setup_logging(log_level)

    # Validar arquivo de áudio
    if not validate_audio_file(audio_path):
        logger.error(f"Arquivo inválido: {audio_path}")
        sys.exit(1)

    # Determinar caminho de saída padrão
    if not output:
        audio_name = Path(audio_path).stem
        output = f"output/{audio_name}_transcript.json"

    # Montar metadados do episódio
    episode_metadata: Dict[str, Any] = {}
    if episode_id:
        episode_metadata['episode_id'] = episode_id
    if title:
        episode_metadata['title'] = title
    if date:
        episode_metadata['date'] = date
    if link:
        episode_metadata['original_link'] = link
    episode_metadata['language'] = language

    guest_list: Optional[List[str]] = None
    if guest_names:
        guest_list = [name.strip() for name in guest_names.split(',') if name.strip()]

    pipeline_config = {
        'transcriber_config': {
            'backend': whisper_backend,
            'model': whisper_model,
            'language': language,
        },
        'diarizer_config': {
            'backend': diarization_backend,
            'max_speakers': max_speakers,
        },
        'cleaner_config': {
            'remove_fillers': not no_clean,
            'aggressive_cleaning': aggressive_clean,
        },
        'log_level': log_level,
    }

    try:
        logger.info(f"Iniciando processamento de: {audio_path}")
        pipeline = PodcastPipeline(**pipeline_config)
        result = pipeline.process(
            audio_path=audio_path,
            episode_metadata=episode_metadata,
            host_name=host_name,
            guest_names=guest_list,
        )

        # Salvar resultado
        pipeline.save_output(result, output)

        # Resumo
        logger.info("=" * 60)
        logger.info("PROCESSAMENTO COMPLETO!")
        logger.info("=" * 60)
        logger.info(f"Arquivo de saída: {output}")
        logger.info(f"Total de falas: {len(result.utterances)}")
        logger.info(f"Duração: {result.get_total_duration():.1f}s")

        speaker_stats = result.get_speaker_stats()
        for role, stats in speaker_stats.items():
            logger.info(
                f"  {role}: {stats['utterance_count']} falas, "
                f"{stats['total_time']:.1f}s "
                f"({stats['total_time']/result.get_total_duration()*100:.1f}%)"
            )

        if result.processing_notes:
            warnings = [n for n in result.processing_notes if n.level == "WARNING"]
            errors = [n for n in result.processing_notes if n.level == "ERROR"]
            if warnings:
                logger.info(f"Avisos: {len(warnings)}")
            if errors:
                logger.info(f"Erros: {len(errors)}")

    except Exception as e:
        logger.error(f"Erro no processamento: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# COMANDO: analyze (análise de investimento a partir da transcrição)
# =====================================================================

@cli.command("analyze")
@click.argument('transcript_json', type=click.Path(exists=True))
def analyze(transcript_json: str) -> None:
    """
    Analisa uma transcrição existente para extrair teses de investimento.

    Exemplo:
        python main.py analyze output/transcripts/ep_001.json
    """
    logger = setup_logging()
    try:
        with open(transcript_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        transcript = TranscriptOutput(**data)
        agent = InvestmentAnalysisAgent()
        analysis = agent.analyze_transcript(transcript)

        click.echo("\n" + "=" * 80)
        click.echo(click.style(f"ANÁLISE: {transcript.metadata.title}", fg="cyan", bold=True))
        click.echo("=" * 80)
        click.echo(analysis['analysis'])

        output_path = (
            Path(transcript_json).parent.parent / "analyses" /
            f"{Path(transcript_json).stem}_analysis.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        click.echo(f"\n✓ Análise salva em: {output_path}")
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# COMANDO: marketing (gera pacote de marketing)
# =====================================================================

@cli.command("marketing")
@click.argument('analysis_json', type=click.Path(exists=True))
@click.argument('transcript_json', type=click.Path(exists=True))
@click.option(
    '--tone',
    type=click.Choice(['technical', 'didactic']),
    default='didactic',
    help='Tom do conteúdo (technical/didactic).',
)
def marketing_command(analysis_json: str, transcript_json: str, tone: str) -> None:
    """
    Gera conteúdo de marketing a partir de uma análise + transcrição.

    Exemplo:
        python main.py marketing output/analyses/ep_001_analysis.json \
                                   output/transcripts/ep_001.json \
                                   --tone didactic
    """
    logger = setup_logging()
    try:
        with open(analysis_json, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
        with open(transcript_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        transcript = TranscriptOutput(**data)

        transcript_text = "\n".join(
            f"{u.speaker or u.speaker_raw_id or 'Unknown'}: {u.text}"
            for u in transcript.utterances
        )

        agent = MarketingAgent()
        package = agent.generate_full_marketing_package(
            analysis,
            transcript_text,
            tone=tone,
        )

        output_path = (
            Path(analysis_json).parent.parent / "marketing" /
            f"{Path(transcript_json).stem}_marketing.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(package, f, indent=2, ensure_ascii=False)

        click.echo("\n" + "=" * 80)
        click.echo(click.style("POST LINKEDIN (PREVIEW)", fg="cyan", bold=True))
        click.echo("=" * 80)
        click.echo(package.get('linkedin_post', ''))
        click.echo(f"\n✓ Pacote de marketing salvo em: {output_path}")
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# COMANDO: batch (processa vários episódios a partir de um JSON de metadados)
# =====================================================================

@cli.command("batch")
@click.argument('metadata_file', type=click.Path(exists=True))
@click.option(
    '-o', '--output-dir',
    type=click.Path(),
    default='output',
    help='Diretório de saída (padrão: output/).',
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Nível de log (padrão: INFO).',
)
def batch(metadata_file: str, output_dir: str, log_level: str) -> None:
    """
    Processa múltiplos episódios em lote.

    METADATA_FILE: Arquivo JSON com lista de episódios e seus metadados.

    Formato esperado:
    {
      "episodes": [
        {
          "audio_path": "ep1.mp3",
          "episode_id": "001",
          "title": "Episódio 1",
          "host_name": "João",
          "guest_names": ["Maria"]
        },
        ...
      ]
    }
    """
    logger = setup_logging(log_level)
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de metadados: {e}")
        sys.exit(1)

    episodes: List[Dict[str, Any]] = data.get('episodes', [])
    if not episodes:
        logger.error("Nenhum episódio encontrado no arquivo de metadados.")
        sys.exit(1)

    logger.info(f"Processando {len(episodes)} episódios em lote...")
    success_count = 0
    error_count = 0

    for i, episode in enumerate(episodes, 1):
        audio_path = episode.get('audio_path')
        if not audio_path:
            logger.warning(f"Episódio {i}: 'audio_path' não fornecido, pulando.")
            continue

        logger.info(f"\n[{i}/{len(episodes)}] Processando: {audio_path}")
        try:
            audio_name = Path(audio_path).stem
            out_path = Path(output_dir) / f"{audio_name}_transcript.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)

            pipeline = PodcastPipeline(log_level=log_level)
            result = pipeline.process_from_metadata(
                audio_path=audio_path,
                metadata_dict=episode,
            )
            pipeline.save_output(result, str(out_path))
            success_count += 1
        except Exception as e:
            logger.error(f"Erro ao processar {audio_path}: {e}")
            error_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("LOTE COMPLETO")
    logger.info("=" * 60)
    logger.info(f"Sucesso: {success_count}")
    logger.info(f"Erros:   {error_count}")


# =====================================================================
# COMANDO: validate (valida um JSON de transcrição)
# =====================================================================

@cli.command("validate")
@click.argument('transcript_file', type=click.Path(exists=True))
def validate(transcript_file: str) -> None:
    """
    Valida um arquivo de transcrição gerado.

    TRANSCRIPT_FILE: Arquivo JSON da transcrição.
    """
    logger = setup_logging('INFO')
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        transcript = TranscriptOutput(**data)

        logger.info("✓ Arquivo válido!")
        logger.info(f"  Versão:   {transcript.version}")
        logger.info(f"  Episódio: {transcript.episode_metadata.title or 'N/A'}")
        logger.info(f"  Falas:    {len(transcript.utterances)}")
        logger.info(f"  Duração:  {transcript.get_total_duration():.1f}s")
        logger.info(f"  Participantes: {len(transcript.episode_metadata.participants)}")

        if transcript.processing_notes:
            warnings = sum(1 for n in transcript.processing_notes if n.level == "WARNING")
            errors = sum(1 for n in transcript.processing_notes if n.level == "ERROR")
            logger.info(f"  Avisos: {warnings}")
            logger.info(f"  Erros:  {errors}")
    except Exception as e:
        logger.error(f"✗ Arquivo inválido: {e}")
        sys.exit(1)


# =====================================================================
# COMANDO: test (testa pipeline da playlist com 1 vídeo)
# =====================================================================

@cli.command("test")
def test_command() -> None:
    """
    Testa o pipeline com 1 vídeo da playlist padrão da Outliers.

    Baixa (se necessário), transcreve, analisa e gera marketing para 1 vídeo.
    """
    logger = setup_logging()
    click.echo(click.style("\n🧪 MODO DE TESTE", fg="yellow", bold=True))
    click.echo("Processando 1 vídeo da playlist...\n")
    try:
        results = process_outliers_playlist(
            max_videos=1,
            marketing_tone='didactic',
        )

        click.echo(click.style("\n✓ Teste concluído!", fg="green", bold=True))
        click.echo("Verifique os diretórios output/* para os resultados")
        click.echo(f"Transcrições: {len(results.get('transcriptions', []))}")
        click.echo(f"Análises:     {len(results.get('analyses', []))}")
        click.echo(f"Marketing:    {len(results.get('marketing', []))}")
    except Exception as e:
        logger.error(f"Erro no teste: {e}", exc_info=True)
        sys.exit(1)


# =====================================================================
# ENTRYPOINT
# =====================================================================

if __name__ == '__main__':
    cli()