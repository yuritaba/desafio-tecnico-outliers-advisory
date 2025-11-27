"""
Módulo para transcrever vídeos do YouTube via AssemblyAI.
Inclui diarização para identificar speakers (Samuel e Convidado).
"""
import os
import time
import logging
import subprocess
import warnings
from typing import Dict, Any, List, Optional
from pathlib import Path
import tempfile

# Suprimir avisos de deprecação do yt-dlp
warnings.filterwarnings('ignore', message='.*Python version.*deprecated.*')
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning'

try:
    import yt_dlp
    
    # Configurar logger do yt-dlp para ser silencioso
    yt_dlp.utils.std_headers['User-Agent'] = 'Mozilla/5.0'
    
    import requests
    from dotenv import load_dotenv
except ImportError:
    raise ImportError(
        "Dependências não instaladas. Execute: "
        "pip install yt-dlp requests python-dotenv"
    )


class QuietLogger:
    """Logger customizado para suprimir mensagens de deprecação do yt-dlp."""
    def debug(self, msg):
        pass
    
    def info(self, msg):
        pass
    
    def warning(self, msg):
        if 'deprecated' not in msg.lower() and 'python version' not in msg.lower():
            pass  # Suprimir todos os warnings por enquanto
    
    def error(self, msg):
        if 'deprecated' not in msg.lower():
            logging.getLogger('yt-dlp').error(msg)


class YouTubeTranscriberAssemblyAI:
    """
    Transcreve vídeos do YouTube via AssemblyAI.
    Inclui diarização para identificar speakers (Samuel e Convidado).
    """
    
    ASSEMBLYAI_BASE_URL = "https://api.assemblyai.com/v2"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        temp_dir: Optional[str] = None
    ):
        """
        Inicializa o transcriber com AssemblyAI.
        
        Args:
            api_key: Chave da API AssemblyAI (se None, busca em ASSEMBLYAI_KEY no .env)
            temp_dir: Diretório temporário (se None, usa sistema)
        """
        self.logger = logging.getLogger('podcast_pipeline.youtube_transcriber')
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        # Carregar API key
        if api_key is None:
            load_dotenv()
            api_key = os.getenv("ASSEMBLYAI_KEY")
            if not api_key:
                raise ValueError(
                    "ASSEMBLYAI_KEY não encontrado. "
                    "Configure no arquivo .env ou passe como parâmetro."
                )
        
        self.api_key = api_key
        self.logger.info("✓ AssemblyAI API key configurada")
    
    def transcribe_youtube_url(
        self,
        youtube_url: str,
        language: str = "pt"
    ) -> Dict[str, Any]:
        """
        Transcreve um vídeo do YouTube via AssemblyAI.
        
        Args:
            youtube_url: URL do vídeo do YouTube
            language: Código do idioma (pt, en, es, etc)
            
        Returns:
            Dict com transcrição, metadados e speakers identificados no formato:
            {
                'video_id': str,
                'title': str,
                'duration': float (segundos),
                'text': str (transcrição completa),
                'utterances': [
                    {
                        'speaker': str (ex: 'A', 'B'),
                        'text': str,
                        'start': float (segundos),
                        'end': float (segundos)
                    },
                    ...
                ]
            }
        """
        self.logger.info(f"Transcrevendo: {youtube_url}")
        
        # 1. Extrair metadados do vídeo (sem baixar)
        metadata = self._get_video_metadata(youtube_url)
        duration_sec = metadata['duration']
        self.logger.info(f"Vídeo: {metadata['title']} ({duration_sec}s = {duration_sec/60:.1f}min)")
        
        # 2. Baixar áudio em formato WAV mono 16kHz
        self.logger.info("Baixando áudio...")
        audio_path = self._download_audio(youtube_url)
        
        try:
            # 3. Upload para AssemblyAI
            upload_url = self._upload_file(audio_path)
            self.logger.info(f"✓ Áudio enviado para AssemblyAI")
            
            # 4. Criar transcrição com diarização
            transcript_id = self._request_transcription(upload_url, language)
            self.logger.info(f"✓ Transcrição iniciada: ID={transcript_id}")
            
            # 5. Aguardar conclusão
            result = self._poll_transcription(transcript_id)
            
            # 6. Processar resultado
            processed_result = self._process_result(result, metadata)
            
            self.logger.info(f"✓ Transcrição concluída: {len(processed_result['utterances'])} utterances")
            return processed_result
            
        finally:
            # Limpar arquivo temporário
            if audio_path.exists():
                audio_path.unlink()
                self.logger.debug(f"Arquivo temporário removido: {audio_path}")
    
    def _get_video_metadata(self, youtube_url: str) -> Dict[str, Any]:
        """Obtém metadados do vídeo sem baixá-lo."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'logger': QuietLogger(),
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            
            return {
                'id': info.get('id'),
                'title': info.get('title'),
                'duration': info.get('duration', 0),
                'description': info.get('description'),
                'channel': info.get('channel'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
            }
    
    def _find_command(self, names: List[str]) -> Optional[str]:
        """Encontra o caminho completo de um comando."""
        for name in names:
            try:
                result = subprocess.run(
                    ['which', name],
                    capture_output=True,
                    text=True,
                    check=True
                )
                path = result.stdout.strip()
                if path:
                    return path
            except subprocess.CalledProcessError:
                continue
        return None
    
    def _download_audio(self, youtube_url: str) -> Path:
        """
        Baixa áudio do YouTube e converte para WAV mono 16kHz.
        
        Returns:
            Path para o arquivo WAV temporário
        """
        # Encontrar yt-dlp
        ytdlp = self._find_command([
            'yt-dlp',
            '/opt/homebrew/bin/yt-dlp',
            '/usr/local/bin/yt-dlp'
        ])
        if not ytdlp:
            raise RuntimeError("yt-dlp não encontrado. Instale com: brew install yt-dlp")
        
        # Encontrar ffmpeg
        ffmpeg = self._find_command([
            'ffmpeg',
            '/opt/homebrew/bin/ffmpeg',
            '/usr/local/bin/ffmpeg'
        ])
        if not ffmpeg:
            raise RuntimeError("ffmpeg não encontrado. Instale com: brew install ffmpeg")
        
        ffmpeg_location = Path(ffmpeg).parent
        
        # Criar arquivo temporário
        temp_dir = Path(self.temp_dir)
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / f"youtube_audio_{int(time.time())}"
        
        # Baixar áudio
        cmd = [
            ytdlp,
            '--extract-audio',
            '--audio-format', 'wav',
            '--audio-quality', '0',
            '-o', str(temp_file),
            '--no-playlist',
            '--no-warnings',
            '--no-check-certificate',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--referer', 'https://www.youtube.com/',
            '--extractor-args', 'youtube:player_client=android,web',
            '--ffmpeg-location', str(ffmpeg_location),
            youtube_url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Erro ao baixar áudio: {result.stderr}")
        
        # Encontrar arquivo baixado
        downloaded_files = list(temp_dir.glob(f"{temp_file.name}.*"))
        if not downloaded_files:
            raise RuntimeError("Arquivo de áudio não encontrado após download")
        
        original_audio = downloaded_files[0]
        
        # Converter para mono 16kHz
        converted_audio = temp_dir / f"youtube_audio_{int(time.time())}_16k.wav"
        
        cmd = [
            str(ffmpeg),
            '-i', str(original_audio),
            '-ar', '16000',  # 16kHz
            '-ac', '1',      # mono
            '-y',            # overwrite
            str(converted_audio)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Erro ao converter áudio: {result.stderr}")
        
        # Limpar arquivo original
        if original_audio.exists():
            original_audio.unlink()
        
        return converted_audio
    
    def _upload_file(self, audio_path: Path) -> str:
        """
        Faz upload do arquivo para AssemblyAI.
        
        Returns:
            URL do arquivo no AssemblyAI
        """
        headers = {"authorization": self.api_key}
        
        with audio_path.open("rb") as f:
            response = requests.post(
                f"{self.ASSEMBLYAI_BASE_URL}/upload",
                headers=headers,
                data=f
            )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"Erro no upload para AssemblyAI ({response.status_code}): {response.text}"
            )
        
        return response.json()["upload_url"]
    
    def _request_transcription(
        self,
        upload_url: str,
        language: str = "pt",
        speakers_expected: int = 2
    ) -> str:
        """
        Cria requisição de transcrição com diarização.
        
        Returns:
            ID da transcrição
        """
        headers = {
            "authorization": self.api_key,
            "content-type": "application/json"
        }
        
        data = {
            "audio_url": upload_url,
            "speaker_labels": True,
            "speakers_expected": speakers_expected,
            "language_code": language,
        }
        
        response = requests.post(
            f"{self.ASSEMBLYAI_BASE_URL}/transcript",
            json=data,
            headers=headers
        )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"Erro ao criar transcrição ({response.status_code}): {response.text}"
            )
        
        return response.json()["id"]
    
    def _poll_transcription(
        self,
        transcript_id: str,
        poll_interval: int = 3
    ) -> dict:
        """
        Aguarda conclusão da transcrição.
        
        Returns:
            Resultado completo da transcrição
        """
        headers = {"authorization": self.api_key}
        polling_endpoint = f"{self.ASSEMBLYAI_BASE_URL}/transcript/{transcript_id}"
        
        self.logger.info("⏳ Aguardando conclusão da transcrição...")
        
        while True:
            response = requests.get(polling_endpoint, headers=headers)
            
            if response.status_code != 200:
                raise RuntimeError(
                    f"Erro ao consultar transcrição ({response.status_code}): {response.text}"
                )
            
            result = response.json()
            status = result.get("status")
            
            if status == "completed":
                self.logger.info("✓ Transcrição concluída!")
                return result
            elif status == "error":
                error_msg = result.get("error", "Unknown error")
                raise RuntimeError(f"Transcrição falhou: {error_msg}")
            else:
                self.logger.debug(f"Status: {status}... aguardando {poll_interval}s")
                time.sleep(poll_interval)
    
    def _process_result(self, result: dict, metadata: dict) -> Dict[str, Any]:
        """
        Processa resultado do AssemblyAI para o formato esperado pelo pipeline.
        
        Returns:
            Dict formatado com utterances e metadados
        """
        utterances_raw = result.get("utterances", [])
        
        if not utterances_raw:
            self.logger.warning("⚠ Nenhum utterance retornado")
        
        # Converter utterances para o formato esperado
        utterances = []
        for utt in utterances_raw:
            # AssemblyAI usa ms, converter para segundos
            start_ms = utt.get("start", 0)
            end_ms = utt.get("end", 0)
            
            utterances.append({
                'speaker': utt.get("speaker", "UNKNOWN"),  # Ex: "A", "B", "C"
                'text': utt.get("text", "").strip(),
                'start': start_ms / 1000.0,  # Converter para segundos
                'end': end_ms / 1000.0,
            })
        
        # Texto completo
        full_text = result.get("text", "")
        
        return {
            'video_id': metadata['id'],
            'video_url': metadata.get('webpage_url', f"https://www.youtube.com/watch?v={metadata['id']}"),
            'title': metadata['title'],
            'duration': metadata['duration'],
            'upload_date': metadata.get('upload_date'),
            'channel': metadata.get('channel'),
            'description': metadata.get('description'),
            'text': full_text,
            'utterances': utterances,
            'confidence': result.get("confidence"),  # AssemblyAI fornece confiança
            'audio_duration': result.get("audio_duration", 0) / 1000.0,  # ms -> s
            'language': metadata.get('language', 'pt'),
        }
    
    def _get_playlist_info(self, playlist_url: str) -> Dict[str, Any]:
        """
        Obtém informações da playlist do YouTube.
        
        Args:
            playlist_url: URL da playlist
            
        Returns:
            Dict com informações da playlist (título, uploader, entries)
        """
        self.logger.info(f"📋 Extraindo informações da playlist...")
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'no_warnings': True,
            'logger': QuietLogger(),
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                
                return {
                    'title': info.get('title'),
                    'uploader': info.get('uploader'),
                    'entries': [
                        {
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'duration': entry.get('duration')
                        }
                        for entry in info.get('entries', [])
                        if entry  # Filtrar None
                    ]
                }
        except Exception as e:
            self.logger.error(f"✗ Erro ao extrair playlist: {e}")
            raise
