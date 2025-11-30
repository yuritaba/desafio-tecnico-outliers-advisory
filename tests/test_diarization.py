#!/usr/bin/env python3
"""
diarization.py

Testa diarização do Google Cloud Speech-to-Text (API v1p1beta1)
usando o arquivo youtube_shorts.wav na mesma pasta.

Configurações (iguais às da interface):
- API version: v1p1beta1
- Transcription model: Long (latest_long)
- Language code: en-US
- Encoding: LINEAR16
- Sample rate: 24000 Hz
- Speaker diarization: Enabled, min=2, max=3
"""

import os
import sys
import logging
from pathlib import Path

from google.cloud import speech_v1p1beta1 as speech

# -------------------------------------------------------------------
# Configuração básica de log
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _duration_to_seconds(d) -> float:
    """Converte google.protobuf.Duration em segundos (float)."""
    if d is None:
        return 0.0
    seconds = getattr(d, "seconds", 0)
    nanos = getattr(d, "nanos", 0)
    return float(seconds) + float(nanos) / 1e9


def ensure_gcp_credentials():
    """
    Garante que a variável GOOGLE_APPLICATION_CREDENTIALS esteja setada.

    Usa o arquivo:
        keys/desafio-outliers-9b2e0744f24b.json
    """
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        logger.info(
            f"✓ GOOGLE_APPLICATION_CREDENTIALS já definida: "
            f"{os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}"
        )
        return

    creds_path = Path("keys/desafio-outliers-9b2e0744f24b.json")
    if creds_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path.resolve())
        logger.info(f"✓ Usando credenciais locais: {creds_path.resolve()}")
    else:
        logger.error("❌ Arquivo de credenciais não encontrado.")
        logger.error("   Esperado: keys/desafio-outliers-9b2e0744f24b.json")
        sys.exit(1)


def main():
    # ----------------------------------------------------------------
    # 1) Resolver caminhos
    # ----------------------------------------------------------------
    script_dir = Path(__file__).resolve().parent
    audio_path = script_dir / "youtube_shorts.wav"

    if not audio_path.exists():
        logger.error(f"❌ Arquivo de áudio não encontrado: {audio_path}")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("🧪 TESTE DE DIARIZAÇÃO - GOOGLE STT v1p1beta1")
    logger.info("=" * 80)
    logger.info(f"Áudio: {audio_path}")

    # ----------------------------------------------------------------
    # 2) Credenciais GCP
    # ----------------------------------------------------------------
    ensure_gcp_credentials()

    # ----------------------------------------------------------------
    # 3) Ler áudio
    # ----------------------------------------------------------------
    logger.info("Lendo áudio (LINEAR16, 24000 Hz, mono)...")
    with open(audio_path, "rb") as f:
        content = f.read()

    audio = speech.RecognitionAudio(content=content)

    # ----------------------------------------------------------------
    # 4) Configuração da diarização (igual à UI)
    # ----------------------------------------------------------------
    diarization_config = speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        min_speaker_count=2,
        max_speaker_count=2,
    )

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000, 
        language_code="pt-BR", # portugues
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
        diarization_config=diarization_config,
        # equivalente ao "Transcription model: Long"
        model="latest_long",
    )

    # ----------------------------------------------------------------
    # 5) Chamar API v1p1beta1 (recognize síncrono)
    # ----------------------------------------------------------------
    client = speech.SpeechClient()
    logger.info("Enviando requisição para Google Speech-to-Text v1p1beta1...")
    response = client.recognize(config=config, audio=audio)
    logger.info(f"✓ Resposta recebida: {len(response.results)} results\n")

    if not response.results:
        logger.error("❌ Nenhum result retornado.")
        sys.exit(1)

    # ----------------------------------------------------------------
    # 6) Pegar último result (onde ficam as words com speaker_tag)
    # ----------------------------------------------------------------
    last_result = response.results[-1]
    alternative = last_result.alternatives[0]
    words = alternative.words

    logger.info("===== PALAVRAS + SPEAKER_TAG (primeiras 50) =====")
    logger.info(f"Total de palavras: {len(words)}")

    for w in words[:50]:
        start = _duration_to_seconds(w.start_time)
        end = _duration_to_seconds(w.end_time)
        logger.info(
            f"[{start:5.1f}s - {end:5.1f}s] "
            f"speaker={w.speaker_tag} word='{w.word}'"
        )

    if len(words) > 50:
        logger.info(f"... (+{len(words) - 50} palavras)\n")

    # ----------------------------------------------------------------
    # 7) Agrupar palavras em segmentos por speaker (similar à UI)
    # ----------------------------------------------------------------
    logger.info("===== SEGMENTOS AGRUPADOS POR SPEAKER =====")

    segments = []
    if words:
        current_speaker = words[0].speaker_tag
        current_start = _duration_to_seconds(words[0].start_time)
        current_words = []

        for w in words:
            spk = w.speaker_tag
            if spk != current_speaker and current_words:
                # fecha segmento anterior
                seg_text = " ".join(current_words)
                segments.append(
                    {
                        "speaker": current_speaker,
                        "start": current_start,
                        "end": _duration_to_seconds(w.start_time),
                        "text": seg_text,
                    }
                )
                # inicia novo
                current_speaker = spk
                current_start = _duration_to_seconds(w.start_time)
                current_words = [w.word]
            else:
                current_words.append(w.word)

        # fecha último
        if current_words:
            seg_text = " ".join(current_words)
            last_end = _duration_to_seconds(words[-1].end_time)
            segments.append(
                {
                    "speaker": current_speaker,
                    "start": current_start,
                    "end": last_end,
                    "text": seg_text,
                }
            )

    # imprimir segmentos (estilo tabela simplificada)
    for i, seg in enumerate(segments, 1):
        logger.info(
            f"[{i:02d}] {seg['start']:5.1f}s - {seg['end']:5.1f}s | "
            f"speaker {seg['speaker']}: {seg['text']}"
        )

    # ----------------------------------------------------------------
    # 8) Transcript completo (por curiosidade)
    # ----------------------------------------------------------------
    full_text = " ".join([w.word for w in words])
    logger.info("\n===== TRANSCRIPT COMPLETO (preview) =====")
    logger.info(full_text[:500] + ("..." if len(full_text) > 500 else ""))
    logger.info("\n✓ Diarização concluída com sucesso.")


if __name__ == "__main__":
    main()