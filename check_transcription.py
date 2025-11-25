#!/usr/bin/env python3
"""
Script para verificar rapidamente as transcrições geradas.
Uso: python3 check_transcription.py
"""

import json
from pathlib import Path

def check_transcriptions():
    """Verifica transcrições e mostra resumo."""
    
    transcripts_dir = Path("output/transcripts")
    analyses_dir = Path("output/analyses")
    marketing_dir = Path("output/marketing")
    
    print("=" * 80)
    print("VERIFICAÇÃO DE TRANSCRIÇÕES")
    print("=" * 80)
    
    # Verificar transcrições
    print("\n📝 TRANSCRIÇÕES:")
    if transcripts_dir.exists():
        transcripts = list(transcripts_dir.glob("*.json"))
        if transcripts:
            for t in transcripts:
                print(f"  ✓ {t.name}")
                # Ler e mostrar info básica
                with open(t, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata = data.get('metadata', {})
                    print(f"    Título: {metadata.get('title', 'N/A')}")
                    print(f"    Duração: {metadata.get('duration_seconds', 0) / 60:.1f} min")
                    print(f"    Utterances: {len(data.get('utterances', []))}")
                    print(f"    Caminho: {t}")
                    print()
        else:
            print("  ⚠ Nenhuma transcrição encontrada")
    else:
        print("  ⚠ Diretório não existe")
    
    # Verificar análises
    print("\n🔍 ANÁLISES:")
    if analyses_dir.exists():
        analyses = list(analyses_dir.glob("*.json"))
        if analyses:
            for a in analyses:
                print(f"  ✓ {a.name}")
        else:
            print("  ⚠ Nenhuma análise encontrada")
    else:
        print("  ⚠ Diretório não existe")
    
    # Verificar marketing
    print("\n📢 MARKETING:")
    if marketing_dir.exists():
        marketing = list(marketing_dir.glob("*.json"))
        if marketing:
            for m in marketing:
                print(f"  ✓ {m.name}")
        else:
            print("  ⚠ Nenhum material de marketing encontrado")
    else:
        print("  ⚠ Diretório não existe")
    
    # Verificar sumários do pipeline
    print("\n📊 SUMÁRIOS DO PIPELINE:")
    output_dir = Path("output")
    if output_dir.exists():
        summaries = sorted(output_dir.glob("pipeline_summary_*.json"), reverse=True)
        if summaries:
            # Mostrar apenas os 3 mais recentes
            for s in summaries[:3]:
                print(f"  📄 {s.name}")
                with open(s, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"    Transcrições: {len(data.get('transcriptions', []))}")
                    print(f"    Análises: {len(data.get('analyses', []))}")
                    print(f"    Marketing: {len(data.get('marketing', []))}")
                    print(f"    Erros: {len(data.get('errors', []))}")
                    
                    # Mostrar erros se houver
                    errors = data.get('errors', [])
                    if errors:
                        print("    ⚠ Erros:")
                        for err in errors[:3]:  # Mostrar max 3 erros
                            print(f"      - {err.get('stage')}: {err.get('error', '')[:100]}...")
                    print()
        else:
            print("  ⚠ Nenhum sumário encontrado")
    
    print("=" * 80)
    print("\n💡 Para ver o conteúdo completo de uma transcrição:")
    print("   cat output/transcripts/<video_id>.json | jq")
    print("\n💡 Para ver erros detalhados:")
    print("   cat output/pipeline_summary_*.json | jq '.errors'")
    print("=" * 80)

if __name__ == "__main__":
    check_transcriptions()
