"""
Teste para o detector de início de podcast.
"""
from src.podcast_start_detector import PodcastStartDetector
from src.models import AlignedSegment


def test_keyword_detection():
    """Testa detecção por palavra-chave."""
    print("=" * 60)
    print("TESTE 1: Detecção por palavra-chave")
    print("=" * 60)
    
    detector = PodcastStartDetector()
    
    # Simula segmentos com intro + início
    segments = [
        AlignedSegment(
            start=0.0,
            end=5.0,
            text="Propaganda do patrocinador...",
            speaker="SPEAKER_A"
        ),
        AlignedSegment(
            start=5.0,
            end=10.0,
            text="Vinheta do podcast...",
            speaker="SPEAKER_A"
        ),
        AlignedSegment(
            start=10.0,
            end=15.0,
            text="Bom dia a todos! Hoje vamos falar sobre investimentos.",
            speaker="SPEAKER_A"
        ),
        AlignedSegment(
            start=15.0,
            end=20.0,
            text="É um prazer estar aqui.",
            speaker="SPEAKER_B"
        ),
    ]
    
    # Detecta início
    filtered = detector.detect_podcast_start(segments, blocks_to_check=3)
    
    print(f"\n✅ Segmentos originais: {len(segments)}")
    print(f"✅ Segmentos após detecção: {len(filtered)}")
    print(f"✅ Primeiro segmento: '{filtered[0].text}'")
    print(f"✅ Tempo removido: {detector.get_removed_duration(segments, filtered):.1f}s")
    
    assert len(filtered) == 2, "Deveria ter removido 2 segmentos"
    assert "Bom dia" in filtered[0].text, "Deveria começar no 'Bom dia'"
    print("\n✅ TESTE 1 PASSOU!\n")


def test_no_keyword():
    """Testa quando não há palavra-chave (usa LLM)."""
    print("=" * 60)
    print("TESTE 2: Detecção por LLM (sem palavra-chave)")
    print("=" * 60)
    
    detector = PodcastStartDetector()
    
    # Simula segmentos sem palavras-chave óbvias
    segments = [
        AlignedSegment(
            start=0.0,
            end=5.0,
            text="Anúncio comercial aqui...",
            speaker="SPEAKER_A"
        ),
        AlignedSegment(
            start=5.0,
            end=10.0,
            text="Mais propaganda...",
            speaker="SPEAKER_A"
        ),
        AlignedSegment(
            start=10.0,
            end=15.0,
            text="Olá, estamos aqui com nosso convidado especial.",
            speaker="SPEAKER_A"
        ),
    ]
    
    # Detecta início (vai usar LLM)
    filtered = detector.detect_podcast_start(segments, blocks_to_check=3)
    
    print(f"\n✅ Segmentos originais: {len(segments)}")
    print(f"✅ Segmentos após detecção: {len(filtered)}")
    print(f"✅ Primeiro segmento: '{filtered[0].text}'")
    print(f"✅ Tempo removido: {detector.get_removed_duration(segments, filtered):.1f}s")
    print("\n✅ TESTE 2 CONCLUÍDO!\n")


def test_already_starts():
    """Testa quando podcast já começa no início."""
    print("=" * 60)
    print("TESTE 3: Podcast já começa no início")
    print("=" * 60)
    
    detector = PodcastStartDetector()
    
    segments = [
        AlignedSegment(
            start=0.0,
            end=5.0,
            text="Bom dia pessoal, vamos começar!",
            speaker="SPEAKER_A"
        ),
        AlignedSegment(
            start=5.0,
            end=10.0,
            text="Hoje temos um convidado incrível.",
            speaker="SPEAKER_A"
        ),
    ]
    
    # Detecta início
    filtered = detector.detect_podcast_start(segments, blocks_to_check=3)
    
    print(f"\n✅ Segmentos originais: {len(segments)}")
    print(f"✅ Segmentos após detecção: {len(filtered)}")
    print(f"✅ Manteve todos os segmentos: {len(filtered) == len(segments)}")
    
    assert len(filtered) == len(segments), "Não deveria remover nada"
    print("\n✅ TESTE 3 PASSOU!\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TESTANDO DETECTOR DE INÍCIO DE PODCAST")
    print("=" * 60 + "\n")
    
    try:
        test_keyword_detection()
        test_no_keyword()
        test_already_starts()
        
        print("=" * 60)
        print("✅ TODOS OS TESTES PASSARAM!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
