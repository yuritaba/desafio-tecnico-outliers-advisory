#!/usr/bin/env python3
"""
Script principal CLI para processamento de podcasts financeiros da Outliers Advisory.

Pipeline completo:
YouTube → Transcrição (AssemblyAI) → Análise de Investimento → Marketing

Comandos principais:
- outliers-api: Processa playlist da Outliers com AssemblyAI
- analyze: Análise de teses de investimento em transcrições existentes
- marketing: Gera conteúdo de marketing de transcrições existentes
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
from src.master_pipeline_api import MasterPipelineAPI, process_outliers_playlist_api
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
    Pipeline de Processamento de Podcasts Financeiros - Outliers Advisory.

    YouTube → Transcrição (AssemblyAI) → Análise de Investimento → Marketing.
    """
    pass


# =====================================================================
# COMANDO: outliers-api (PRINCIPAL)
# =====================================================================

@cli.command("outliers-api")
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
    help='Tom do conteúdo de marketing.',
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
    help='Pular geração de marketing.',
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Nível de log.',
)
def outliers_api(
    max_videos: Optional[int],
    tone: str,
    skip_transcription: bool,
    skip_analysis: bool,
    skip_marketing: bool,
    log_level: str,
) -> None:
    """
    Processa playlist da Outliers com AssemblyAI (COMANDO PRINCIPAL).

    Exemplo:
        python main.py outliers-api --max-videos 3
        python main.py outliers-api --skip-transcription
    """
    logger = setup_logging(log_level)
    try:
        # URL hardcoded da playlist da Outliers
        OUTLIERS_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL_y7P-w62_ZER2V4kIF5RX4HK4JKPR_Ti"
        
        pipeline = MasterPipelineAPI()
        results: Dict[str, Any] = pipeline.process_playlist(
            playlist_url=OUTLIERS_PLAYLIST_URL,
            max_videos=max_videos,
            marketing_tone=tone,
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

    except KeyboardInterrupt:
        click.echo(click.style("\n✗ Interrompido pelo usuário.", fg="yellow"))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"✗ Erro fatal: {e}", fg="red"), err=True)
        logger.exception("Erro no pipeline")
        sys.exit(1)


# =====================================================================
# COMANDO: analyze (Apenas análise de investimento)
# =====================================================================

@cli.command("analyze")
@click.option(
    '--transcript-file',
    type=click.Path(exists=True),
    required=True,
    help='Caminho do arquivo JSON da transcrição.',
)
@click.option(
    '--output-file',
    type=click.Path(),
    required=True,
    help='Caminho para salvar a análise (JSON).',
)
@click.option(
    '--use-rag',
    is_flag=True,
    default=True,
    help='Usar RAG (análise contextual).',
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Nível de log.',
)
def analyze(
    transcript_file: str,
    output_file: str,
    use_rag: bool,
    log_level: str,
) -> None:
    """
    Analisa transcrição existente e gera insights de investimento.

    Exemplo:
        python main.py analyze \\
            --transcript-file output/transcripts/IZ1LX8yJ6Fk.json \\
            --output-file output/analyses/IZ1LX8yJ6Fk.json
    """
    logger = setup_logging(log_level)
    try:
        # Carregar transcrição
        with open(transcript_file, 'r') as f:
            data = json.load(f)
        transcript = TranscriptOutput(**data)

        # Analisar
        agent = InvestmentAnalysisAgent()
        analysis = agent.analyze_transcript(transcript, use_rag=use_rag)

        # Salvar
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        click.echo(click.style(f"✓ Análise salva em: {output_file}", fg="green"))

    except Exception as e:
        click.echo(click.style(f"✗ Erro: {e}", fg="red"), err=True)
        logger.exception("Erro na análise")
        sys.exit(1)


# =====================================================================
# COMANDO: marketing (Apenas geração de marketing)
# =====================================================================

@cli.command("marketing")
@click.option(
    '--transcript-file',
    type=click.Path(exists=True),
    required=True,
    help='Caminho do arquivo JSON da transcrição.',
)
@click.option(
    '--analysis-file',
    type=click.Path(exists=True),
    required=True,
    help='Caminho do arquivo JSON da análise.',
)
@click.option(
    '--output-file',
    type=click.Path(),
    required=True,
    help='Caminho para salvar conteúdos de marketing (JSON).',
)
@click.option(
    '--tone',
    type=click.Choice(['technical', 'didactic']),
    default='didactic',
    help='Tom do conteúdo.',
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help='Nível de log.',
)
def marketing(
    transcript_file: str,
    analysis_file: str,
    output_file: str,
    tone: str,
    log_level: str,
) -> None:
    """
    Gera conteúdos de marketing de transcrição e análise existentes.

    Exemplo:
        python main.py marketing \\
            --transcript-file output/transcripts/IZ1LX8yJ6Fk.json \\
            --analysis-file output/analyses/IZ1LX8yJ6Fk.json \\
            --output-file output/marketing/IZ1LX8yJ6Fk.json
    """
    logger = setup_logging(log_level)
    try:
        # Carregar transcrição
        with open(transcript_file, 'r') as f:
            transcript_data = json.load(f)
        transcript = TranscriptOutput(**transcript_data)

        # Carregar análise
        with open(analysis_file, 'r') as f:
            analysis_data = json.load(f)

        # Gerar marketing
        agent = MarketingAgent()
        marketing_content = agent.generate_marketing(
            transcript=transcript,
            analysis=analysis_data,
            tone=tone
        )

        # Salvar
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(marketing_content, f, indent=2, ensure_ascii=False)

        click.echo(click.style(f"✓ Marketing salvo em: {output_file}", fg="green"))

    except Exception as e:
        click.echo(click.style(f"✗ Erro: {e}", fg="red"), err=True)
        logger.exception("Erro no marketing")
        sys.exit(1)


# =====================================================================
# MAIN
# =====================================================================

if __name__ == "__main__":
    cli()
