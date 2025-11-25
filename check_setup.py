#!/usr/bin/env python3
"""
Script para verificar se o ambiente está configurado corretamente.
"""
import os
import sys
from pathlib import Path

def check_env_vars():
    """Verifica variáveis de ambiente necessárias."""
    print("🔍 Verificando variáveis de ambiente...")
    
    issues = []
    
    # Verificar OPENAI_API_KEY
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        issues.append("❌ OPENAI_API_KEY não encontrada no .env")
    elif openai_key.startswith('sk-'):
        print(f"✅ OPENAI_API_KEY: {openai_key[:20]}...")
    else:
        issues.append(f"⚠️  OPENAI_API_KEY parece inválida: {openai_key[:20]}...")
    
    # Verificar HF_TOKEN
    hf_token = os.getenv('HF_TOKEN')
    if not hf_token:
        issues.append("❌ HF_TOKEN não encontrada no .env")
    elif hf_token.startswith('hf_'):
        print(f"✅ HF_TOKEN: {hf_token[:15]}...")
    else:
        issues.append(f"⚠️  HF_TOKEN parece inválida: {hf_token[:15]}...")
    
    return issues

def check_dependencies():
    """Verifica se as dependências principais estão instaladas."""
    print("\n🔍 Verificando dependências...")
    
    issues = []
    required = [
        ('openai', 'OpenAI API'),
        ('langchain', 'LangChain'),
        ('langchain_openai', 'LangChain OpenAI'),
        ('langchain_community', 'LangChain Community'),
        ('whisper', 'OpenAI Whisper'),
        ('pyannote.audio', 'Pyannote Audio'),
        ('yt_dlp', 'yt-dlp'),
        ('click', 'Click'),
    ]
    
    for module, name in required:
        try:
            __import__(module)
            print(f"✅ {name}")
        except ImportError:
            issues.append(f"❌ {name} não instalado (pip install {module})")
    
    return issues

def check_directories():
    """Verifica se os diretórios necessários existem."""
    print("\n🔍 Verificando estrutura de diretórios...")
    
    dirs = ['data', 'output', 'output/transcripts', 'output/analyses', 'output/marketing']
    
    for dir_path in dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"✅ {dir_path}/")
        else:
            print(f"⚠️  {dir_path}/ não existe (será criado automaticamente)")
    
    return []

def check_pyannote_access():
    """Verifica se tem acesso aos modelos pyannote."""
    print("\n🔍 Verificando acesso ao Pyannote...")
    
    hf_token = os.getenv('HF_TOKEN')
    if not hf_token:
        return ["❌ HF_TOKEN não configurado"]
    
    try:
        from pyannote.audio import Pipeline
        
        # Tentar carregar pipeline
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            print("✅ Acesso ao pyannote/speaker-diarization-3.1")
            return []
        except Exception as e:
            error_msg = str(e)
            if 'gated' in error_msg.lower() or 'private' in error_msg.lower():
                return [
                    "⚠️  Modelo pyannote é GATED - você precisa aceitar os termos:",
                    "   1. Acesse: https://huggingface.co/pyannote/speaker-diarization-3.1",
                    "   2. Clique em 'Agree and access repository'",
                    "   3. Acesse: https://huggingface.co/pyannote/segmentation-3.0",
                    "   4. Clique em 'Agree and access repository'",
                ]
            else:
                return [f"❌ Erro ao acessar pyannote: {error_msg}"]
    except ImportError:
        return ["❌ pyannote.audio não instalado"]

def main():
    """Função principal."""
    print("=" * 80)
    print("🚀 VERIFICAÇÃO DO AMBIENTE - Pipeline de Podcasts")
    print("=" * 80)
    
    # Carregar .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Arquivo .env carregado\n")
    except Exception as e:
        print(f"⚠️  Erro ao carregar .env: {e}\n")
    
    all_issues = []
    
    # Executar verificações
    all_issues.extend(check_env_vars())
    all_issues.extend(check_dependencies())
    all_issues.extend(check_directories())
    all_issues.extend(check_pyannote_access())
    
    # Resumo
    print("\n" + "=" * 80)
    if all_issues:
        print("⚠️  PROBLEMAS ENCONTRADOS:")
        print("=" * 80)
        for issue in all_issues:
            print(issue)
        print("\n💡 RECOMENDAÇÕES:")
        print("   → Instalar dependências: pip install -r requirements.txt")
        print("   → Configurar .env com OPENAI_API_KEY e HF_TOKEN")
        print("   → Aceitar termos do Pyannote no Hugging Face")
        return 1
    else:
        print("✅ AMBIENTE CONFIGURADO CORRETAMENTE!")
        print("=" * 80)
        print("\n🎉 Você pode rodar:")
        print("   → python main.py test")
        print("   → python main.py outliers --max-videos 3")
        return 0

if __name__ == '__main__':
    sys.exit(main())
