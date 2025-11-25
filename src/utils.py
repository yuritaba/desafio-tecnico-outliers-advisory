"""
Funções utilitárias para o pipeline de processamento de podcasts.
"""
import os
import logging
import colorlog
from typing import Optional
from pathlib import Path


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configura logging colorido para o console.
    
    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Logger configurado
    """
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    )
    
    logger = colorlog.getLogger('podcast_pipeline')
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper()))
    
    return logger


def seconds_to_timestamp(seconds: float) -> str:
    """
    Converte segundos para formato HH:MM:SS.
    
    Args:
        seconds: Tempo em segundos
    
    Returns:
        String no formato HH:MM:SS
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def timestamp_to_seconds(timestamp: str) -> float:
    """
    Converte timestamp HH:MM:SS para segundos.
    
    Args:
        timestamp: String no formato HH:MM:SS
    
    Returns:
        Tempo em segundos
    """
    parts = timestamp.split(':')
    if len(parts) == 3:
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = map(int, parts)
        return m * 60 + s
    else:
        return float(parts[0])


def ensure_directory(path: str) -> Path:
    """
    Garante que um diretório existe, criando-o se necessário.
    
    Args:
        path: Caminho do diretório
    
    Returns:
        Path object do diretório
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def get_audio_duration(audio_path: str) -> float:
    """
    Obtém a duração de um arquivo de áudio em segundos.
    
    Args:
        audio_path: Caminho para o arquivo de áudio
    
    Returns:
        Duração em segundos
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # pydub retorna em ms
    except Exception as e:
        logging.warning(f"Não foi possível obter duração do áudio: {e}")
        return 0.0


def load_env_var(var_name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """
    Carrega uma variável de ambiente com tratamento de erro.
    
    Args:
        var_name: Nome da variável
        default: Valor padrão se não encontrada
        required: Se True, levanta exceção se não encontrada
    
    Returns:
        Valor da variável ou default
    
    Raises:
        ValueError: Se required=True e variável não encontrada
    """
    value = os.getenv(var_name, default)
    
    if required and not value:
        raise ValueError(
            f"Variável de ambiente {var_name} é obrigatória mas não foi encontrada. "
            f"Configure-a no arquivo .env"
        )
    
    return value


def format_file_size(size_bytes: int) -> str:
    """
    Formata tamanho de arquivo em formato legível.
    
    Args:
        size_bytes: Tamanho em bytes
    
    Returns:
        String formatada (ex: "15.3 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def validate_audio_file(audio_path: str) -> bool:
    """
    Valida se um arquivo de áudio existe e tem formato suportado.
    
    Args:
        audio_path: Caminho para o arquivo
    
    Returns:
        True se válido, False caso contrário
    """
    path = Path(audio_path)
    
    if not path.exists():
        logging.error(f"Arquivo não encontrado: {audio_path}")
        return False
    
    supported_formats = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.mp4'}
    if path.suffix.lower() not in supported_formats:
        logging.error(
            f"Formato não suportado: {path.suffix}. "
            f"Formatos suportados: {', '.join(supported_formats)}"
        )
        return False
    
    return True


def calculate_overlap(start1: float, end1: float, start2: float, end2: float) -> float:
    """
    Calcula a sobreposição entre dois intervalos de tempo.
    
    Args:
        start1, end1: Início e fim do primeiro intervalo
        start2, end2: Início e fim do segundo intervalo
    
    Returns:
        Duração da sobreposição em segundos (0 se não houver)
    """
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap = max(0, overlap_end - overlap_start)
    return overlap


def calculate_iou(start1: float, end1: float, start2: float, end2: float) -> float:
    """
    Calcula o IoU (Intersection over Union) entre dois intervalos.
    Útil para alinhamento de segmentos.
    
    Args:
        start1, end1: Início e fim do primeiro intervalo
        start2, end2: Início e fim do segundo intervalo
    
    Returns:
        IoU score entre 0 e 1
    """
    intersection = calculate_overlap(start1, end1, start2, end2)
    
    if intersection == 0:
        return 0.0
    
    union = (end1 - start1) + (end2 - start2) - intersection
    
    if union == 0:
        return 0.0
    
    return intersection / union


def merge_adjacent_segments(
    segments: list,
    max_gap: float = 0.5,
    same_speaker: bool = True
) -> list:
    """
    Mescla segmentos adjacentes ou muito próximos.
    
    Args:
        segments: Lista de segmentos com 'start', 'end' e opcionalmente 'speaker'
        max_gap: Gap máximo em segundos para considerar adjacente
        same_speaker: Se True, só mescla se for o mesmo speaker
    
    Returns:
        Lista de segmentos mesclados
    """
    if not segments:
        return []
    
    # Ordena por start time
    sorted_segments = sorted(segments, key=lambda x: x['start'])
    merged = [sorted_segments[0].copy()]
    
    for current in sorted_segments[1:]:
        last = merged[-1]
        
        gap = current['start'] - last['end']
        same_spk = (
            not same_speaker or 
            'speaker' not in current or 
            current.get('speaker') == last.get('speaker')
        )
        
        if gap <= max_gap and same_spk:
            # Mescla
            last['end'] = max(last['end'], current['end'])
            if 'text' in current and 'text' in last:
                last['text'] = last['text'].strip() + ' ' + current['text'].strip()
        else:
            merged.append(current.copy())
    
    return merged


class ProgressTracker:
    """
    Classe helper para tracking de progresso com logging.
    """
    
    def __init__(self, total_steps: int, description: str = "Processing"):
        self.total_steps = total_steps
        self.current_step = 0
        self.description = description
        self.logger = logging.getLogger('podcast_pipeline')
    
    def update(self, step_name: str = ""):
        """Atualiza o progresso"""
        self.current_step += 1
        percentage = (self.current_step / self.total_steps) * 100
        
        msg = f"{self.description}: {self.current_step}/{self.total_steps} ({percentage:.1f}%)"
        if step_name:
            msg += f" - {step_name}"
        
        self.logger.info(msg)
    
    def complete(self):
        """Marca como completo"""
        self.logger.info(f"{self.description}: Completo! ✓")
