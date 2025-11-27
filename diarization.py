#!/usr/bin/env python3
"""
youtube_diarization_assemblyai.py

Pipeline completo:

1. Baixa áudio de um vídeo/shorts do YouTube com yt-dlp
2. Converte para WAV mono 16kHz com ffmpeg (youtube_shorts.wav)
3. Envia para AssemblyAI usando ASSEMBLYAI_KEY do .env
4. Cria transcrição com speaker_labels=True (diarização)
5. Imprime utterances com speaker + texto

Requisitos:
    pip install requests python-dotenv
    brew install yt-dlp ffmpeg   (ou equivalente em outro SO)
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Configuração básica de log
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Configs gerais
# -------------------------------------------------------------------
BASE_URL = "https://api.assemblyai.com/v2"
YOUTUBE_URL = "https://www.youtube.com/shorts/YoCStiDz1i0"
OUTPUT_FILE = "youtube_shorts.wav"


# ===================================================================
# Parte 1 — Download + conversão (yt-dlp + ffmpeg)
# ===================================================================
def find_command(names):
    """Encontra o caminho completo de um comando, testando várias opções."""
    for name in names:
        try:
            result = subprocess.run(
                ["which", name],
                capture_output=True,
                text=True,
                check=True,
            )
            path = result.stdout.strip()
            if path:
                return path
        except subprocess.CalledProcessError:
            continue
    return None


def download_youtube_audio(youtube_url: str, output_file: str) -> Path:
    """
    Baixa o áudio de um vídeo do YouTube e converte para WAV mono 16kHz.
    Retorna o caminho final do arquivo WAV.
    """
    logger.info("=" * 80)
    logger.info("📥 DOWNLOAD DE ÁUDIO DO YOUTUBE")
    logger.info("=" * 80)
    logger.info(f"URL: {youtube_url}")
    logger.info(f"Arquivo de saída: {output_file}\n")

    # 1. Encontrar yt-dlp
    ytdlp = find_command(
        ["yt-dlp", "/opt/homebrew/bin/yt-dlp", "/usr/local/bin/yt-dlp"]
    )
    if not ytdlp:
        logger.error("❌ yt-dlp não encontrado! Instale com: brew install yt-dlp")
        sys.exit(1)

    logger.info(f"✓ yt-dlp encontrado: {ytdlp}")

    # 2. Encontrar ffmpeg
    ffmpeg = find_command(
        ["ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    )
    if not ffmpeg:
        logger.error("❌ ffmpeg não encontrado! Instale com: brew install ffmpeg")
        sys.exit(1)

    ffmpeg_location = Path(ffmpeg).parent
    logger.info(f"✓ ffmpeg encontrado: {ffmpeg}")

    # 3. Baixar áudio do YouTube
    logger.info("\n📥 Baixando áudio do YouTube...")
    temp_file = "temp_youtube_audio"

    cmd = [
        ytdlp,
        "--extract-audio",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "-o",
        temp_file,
        "--no-playlist",
        "--no-warnings",
        "--no-check-certificate",
        "--user-agent",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "--referer",
        "https://www.youtube.com/",
        "--extractor-args",
        "youtube:player_client=android,web",
        "--ffmpeg-location",
        str(ffmpeg_location),
        youtube_url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("❌ Erro ao baixar áudio:")
        logger.error(result.stderr)
        sys.exit(1)

    # 4. Encontrar arquivo baixado
    downloaded_files = list(Path(".").glob(f"{temp_file}.*"))
    if not downloaded_files:
        logger.error("❌ Arquivo de áudio não encontrado após download!")
        sys.exit(1)

    original_audio = downloaded_files[0]
    logger.info(f"✓ Áudio baixado: {original_audio}")

    # 5. Converter para mono 16kHz
    logger.info("\n🔄 Convertendo para mono 16kHz...")

    cmd = [
        str(ffmpeg),
        "-i",
        str(original_audio),
        "-ar",
        "16000",  # 16kHz sample rate
        "-ac",
        "1",  # mono
        "-y",  # overwrite
        output_file,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("❌ Erro ao converter áudio:")
        logger.error(result.stderr)
        sys.exit(1)

    out_path = Path(output_file)
    logger.info(f"✓ Áudio convertido: {out_path}")

    # 6. Obter informações do arquivo
    ffprobe = find_command(
        ["ffprobe", "/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"]
    )
    if ffprobe:
        # Duração
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                duration = float(result.stdout.strip())
                logger.info(f"✓ Duração: {duration:.1f}s ({duration/60:.1f} minutos)")
            except ValueError:
                logger.warning("⚠ Não foi possível interpretar a duração via ffprobe.")

        # Tamanho
        file_size = out_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Tamanho: {file_size:.2f} MB")

    # 7. Limpar arquivo temporário
    if original_audio.exists() and original_audio.name != output_file:
        original_audio.unlink()
        logger.info(f"✓ Arquivo temporário removido: {original_audio}")

    logger.info("\n✅ DOWNLOAD + CONVERSÃO CONCLUÍDOS!")
    logger.info("=" * 80 + "\n")
    return out_path


# ===================================================================
# Parte 2 — Diarização AssemblyAI
# ===================================================================
def load_api_key() -> str:
    """Carrega ASSEMBLYAI_KEY do .env ou do ambiente."""
    load_dotenv()
    api_key = os.getenv("ASSEMBLYAI_KEY")
    if not api_key:
        logger.error("❌ ASSEMBLYAI_KEY não encontrado no .env nem no ambiente.")
        sys.exit(1)
    logger.info("✓ ASSEMBLYAI_KEY carregado do ambiente.")
    return api_key


def upload_file(audio_path: Path, api_key: str) -> str:
    """Faz upload do arquivo de áudio para AssemblyAI e retorna o upload_url."""
    logger.info(f"📤 Enviando arquivo para AssemblyAI: {audio_path}")

    headers = {"authorization": api_key}
    with audio_path.open("rb") as f:
        response = requests.post(f"{BASE_URL}/upload", headers=headers, data=f)

    if response.status_code != 200:
        logger.error(
            f"❌ Erro no upload ({response.status_code}): {response.text}"
        )
        sys.exit(1)

    upload_url = response.json()["upload_url"]
    logger.info(f"✓ Upload concluído. upload_url={upload_url}")
    return upload_url


def request_transcription(
    upload_url: str, api_key: str, speakers_expected: int = 2
) -> str:
    """Cria uma transcrição com diarização e retorna o transcript_id."""
    logger.info("📝 Criando requisição de transcrição com diarização...")

    headers = {"authorization": api_key, "content-type": "application/json"}

    data = {
        "audio_url": upload_url,
        "speaker_labels": True,
        "speakers_expected": speakers_expected,  # você sabe que são 2 (host + gestor)
        "language_code": "pt",
    }

    response = requests.post(f"{BASE_URL}/transcript", json=data, headers=headers)
    if response.status_code != 200:
        logger.error(
            f"❌ Erro ao criar transcrição ({response.status_code}): {response.text}"
        )
        sys.exit(1)

    transcript_id = response.json()["id"]
    logger.info(f"✓ Transcrição criada. ID={transcript_id}")
    return transcript_id


def poll_transcription(
    transcript_id: str, api_key: str, poll_interval: int = 3
) -> dict:
    """
    Fica consultando até a transcrição ser concluída ou dar erro.
    Retorna o JSON final.
    """
    headers = {"authorization": api_key}
    polling_endpoint = f"{BASE_URL}/transcript/{transcript_id}"

    logger.info("⏳ Aguardando conclusão da transcrição...")
    while True:
        response = requests.get(polling_endpoint, headers=headers)
        if response.status_code != 200:
            logger.error(
                f"❌ Erro ao consultar transcrição ({response.status_code}): {response.text}"
            )
            sys.exit(1)

        result = response.json()
        status = result.get("status")

        if status == "completed":
            logger.info("✓ Transcrição concluída!")
            return result
        elif status == "error":
            logger.error(f"❌ Transcrição falhou: {result.get('error')}")
            sys.exit(1)
        else:
            logger.info(f"Status atual: {status}... aguardando {poll_interval}s")
            time.sleep(poll_interval)


def print_utterances(result: dict):
    """Imprime utterances (speaker + texto) e preview do transcript completo."""
    utterances = result.get("utterances", [])
    if not utterances:
        logger.warning(
            "⚠ Nenhum utterance retornado. Verifique se speaker_labels está habilitado."
        )
        logger.info(f"Resposta completa:\n{result}")
        return

    logger.info("\n===== UTTERANCES (SPEAKER + TEXTO) =====")
    for i, utt in enumerate(utterances, 1):
        speaker = utt.get("speaker")
        text = utt.get("text", "").strip()
        start = utt.get("start")
        end = utt.get("end")

        # AssemblyAI geralmente usa ms para start/end
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            start_s = start / 1000.0
            end_s = end / 1000.0
            logger.info(
                f"[{i:02d}] {start_s:6.2f}s - {end_s:6.2f}s | "
                f"Speaker {speaker}: {text}"
            )
        else:
            logger.info(f"[{i:02d}] Speaker {speaker}: {text}")

    full_text = " ".join(utt.get("text", "").strip() for utt in utterances)
    logger.info("\n===== TRANSCRIPT COMPLETO (preview) =====")
    logger.info(full_text[:500] + ("..." if len(full_text) > 500 else ""))
    logger.info("\n✓ Diarização AssemblyAI concluída com sucesso.")


# ===================================================================
# main — orquestra tudo
# ===================================================================
def main():
    # 1) Baixar + converter áudio do YouTube
    audio_path = download_youtube_audio(YOUTUBE_URL, OUTPUT_FILE)

    # 2) AssemblyAI — diarização
    api_key = load_api_key()
    upload_url = upload_file(audio_path, api_key)
    transcript_id = request_transcription(upload_url, api_key, speakers_expected=2)
    result = poll_transcription(transcript_id, api_key)

    # 3) Exibir resultado
    print_utterances(result)


if __name__ == "__main__":
    main()