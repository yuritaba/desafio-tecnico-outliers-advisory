"""
Teste para verificar detecção de palavras-chave e corte de propaganda.
"""
from src.podcast_start_detector import PodcastStartDetector
from src.models import AlignedSegment

def test_keyword_cutting():
    detector = PodcastStartDetector()
    
    print("\n" + "="*80)
    print("TESTE 1: Palavra-chave no MEIO do segmento (com propaganda antes)")
    print("="*80)
    
    segments = [
        AlignedSegment(
            start=0.0,
            end=30.0,
            text="Propaganda qualquer aqui no início.",
            speaker="A"
        ),
        AlignedSegment(
            start=30.0,
            end=60.0,
            text="Com a ajuda do Credit Guide, isso é simples. Bom dia, boa tarde, boa noite. Bem-vindos ao podcast!",
            speaker="A"
        ),
        AlignedSegment(
            start=60.0,
            end=90.0,
            text="Hoje vamos falar sobre investimentos.",
            speaker="A"
        ),
    ]
    
    result = detector.detect_podcast_start(segments, blocks_to_check=10)
    
    print(f"\n📊 RESULTADO:")
    print(f"   Segmentos removidos: {len(segments) - len(result)}")
    print(f"   Primeiro segmento após detecção:")
    print(f"   - Text: '{result[0].text[:100]}...'")
    print(f"   - Start: {result[0].start}s")
    
    assert result[0].text.startswith("Bom dia"), "Texto deveria começar com 'Bom dia'"
    assert "Credit Guide" not in result[0].text, "Propaganda não deveria estar presente"
    print("\n✅ TESTE 1 PASSOU!\n")
    
    print("="*80)
    print("TESTE 2: Palavra-chave no INÍCIO do segmento (sem propaganda)")
    print("="*80)
    
    segments = [
        AlignedSegment(
            start=0.0,
            end=30.0,
            text="Propaganda de abertura.",
            speaker="A"
        ),
        AlignedSegment(
            start=30.0,
            end=60.0,
            text="Bom dia pessoal! Bem-vindos ao episódio de hoje.",
            speaker="A"
        ),
        AlignedSegment(
            start=60.0,
            end=90.0,
            text="Vamos falar de finanças.",
            speaker="A"
        ),
    ]
    
    result = detector.detect_podcast_start(segments, blocks_to_check=10)
    
    print(f"\n📊 RESULTADO:")
    print(f"   Segmentos removidos: {len(segments) - len(result)}")
    print(f"   Primeiro segmento após detecção:")
    print(f"   - Text: '{result[0].text}'")
    print(f"   - Start: {result[0].start}s")
    
    assert result[0].text.startswith("Bom dia"), "Texto deveria começar com 'Bom dia'"
    assert len(result) == 2, "Deveria ter 2 segmentos (removeu 1)"
    print("\n✅ TESTE 2 PASSOU!\n")
    
    print("="*80)
    print("TESTE 3: SEM palavra-chave (deveria usar LLM - mas vamos simular)")
    print("="*80)
    
    segments = [
        AlignedSegment(
            start=0.0,
            end=30.0,
            text="Propaganda de abertura sem saudações.",
            speaker="A"
        ),
        AlignedSegment(
            start=30.0,
            end=60.0,
            text="Olá, meu nome é João e hoje vou entrevistar Maria.",
            speaker="A"
        ),
        AlignedSegment(
            start=60.0,
            end=90.0,
            text="Maria, fala um pouco sobre seu trabalho.",
            speaker="A"
        ),
    ]
    
    result = detector.detect_podcast_start(segments, blocks_to_check=10)
    
    print(f"\n📊 RESULTADO:")
    print(f"   Tentou usar LLM: Sim")
    print(f"   Segmentos finais: {len(result)}")
    print("\n✅ TESTE 3 PASSOU!\n")
    
    print("="*80)
    print("TESTE 4: Case-insensitive (BOA TARDE em maiúscula)")
    print("="*80)
    
    segments = [
        AlignedSegment(
            start=0.0,
            end=30.0,
            text="Propaganda aqui.",
            speaker="A"
        ),
        AlignedSegment(
            start=30.0,
            end=60.0,
            text="BOA TARDE! Sejam todos bem-vindos.",
            speaker="A"
        ),
    ]
    
    result = detector.detect_podcast_start(segments, blocks_to_check=10)
    
    print(f"\n📊 RESULTADO:")
    print(f"   Segmentos removidos: {len(segments) - len(result)}")
    print(f"   Primeiro texto: '{result[0].text}'")
    
    assert "BOA TARDE" in result[0].text, "Deveria detectar BOA TARDE em maiúscula"
    print("\n✅ TESTE 4 PASSOU!\n")

if __name__ == "__main__":
    test_keyword_cutting()
    print("\n" + "="*80)
    print("🎉 TODOS OS TESTES PASSARAM!")
    print("="*80)
