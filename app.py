"""
Interface Web para Outliers Advisory
Chatbot com RAG do Pinecone + Visualização de Análises e Marketing
"""
import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, Response, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from pinecone import Pinecone

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configurar CORS para permitir todas as origens (desenvolvimento)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": True
    }
})

# Configurações
OUTPUT_DIR = Path("output")
TRANSCRIPTS_DIR = OUTPUT_DIR / "transcripts"
ANALYSES_DIR = OUTPUT_DIR / "analyses"
MARKETING_DIR = OUTPUT_DIR / "marketing"

# Inicializar componentes LangChain
embeddings = OpenAIEmbeddings()
llm = ChatOpenAI(model="gpt-4", temperature=0.7, streaming=True)

# Conectar ao Pinecone
pinecone_client = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME", "outliers-case")

# Store de histórico de conversas (em memória)
conversation_histories = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    """Obtém ou cria histórico de conversa."""
    if session_id not in conversation_histories:
        conversation_histories[session_id] = ChatMessageHistory()
    return conversation_histories[session_id]


# System prompt do chatbot
SYSTEM_PROMPT = """Você é um Agente Inteligente da Outliers Advisory, especializado em análise de investimentos e marketing financeiro.

Seu papel:
- Auxiliar na criação de posts de marketing sobre investimentos
- Fornecer análises de investimento baseadas nos episódios do podcast Second Level
- Usar o contexto recuperado do banco vetorial para respostas precisas e fundamentadas
- Citar os speakers (Samuel Ponsoni e convidados) quando relevante

Diretrizes:
- Seja profissional mas acessível
- Use dados e citações do contexto recuperado
- Se não houver contexto relevante, seja honesto sobre isso
- Formate respostas de forma clara e estruturada
- Inclua insights práticos quando possível
- SEMPRE que usar informações do contexto, referencie explicitamente entre parênteses (ex: "segundo o convidado (Contexto 1)", "como mencionado (Contexto 2 e 3)")
- Numere os contextos na ordem que aparecem: Contexto 1, Contexto 2, Contexto 3, etc.

Contexto recuperado:
{context}

Histórico da conversa:
{chat_history}"""


def search_pinecone(query: str, k: int = 5, score_threshold: float = 0.847, episode_filter: str = None):
    """
    Busca no Pinecone com threshold de relevância.
    Busca em TODOS os namespaces (todos os episódios) ou em episódio específico.
    
    Args:
        query: Query de busca
        k: Número máximo de resultados
        score_threshold: Threshold de similaridade (0-1, maior = mais estrito)
        episode_filter: ID do episódio para filtrar (ex: "IZ1LX8yJ6Fk") ou None para todos
        
    Returns:
        Lista de dicts com {text, metadata, score, video_link}
    """
    try:
        # Conectar ao índice Pinecone diretamente
        index = pinecone_client.Index(pinecone_index_name)
        
        # Primeiro, obter todos os namespaces disponíveis
        stats = index.describe_index_stats()
        all_namespaces = list(stats.namespaces.keys()) if hasattr(stats, 'namespaces') else []
        
        # Filtrar namespaces se necessário
        if episode_filter:
            target_namespace = f"episode_{episode_filter}"
            namespaces = [ns for ns in all_namespaces if ns == target_namespace]
            filter_msg = f"EPISÓDIO ESPECÍFICO: {episode_filter}"
        else:
            namespaces = all_namespaces
            filter_msg = f"TODOS OS {len(all_namespaces)} EPISÓDIOS"
        
        print(f"\n{'='*60}")
        print(f"QUERY: {query}")
        print(f"FILTRO: {filter_msg}")
        print(f"THRESHOLD CONFIGURADO: {score_threshold}")
        print(f"NAMESPACES A CONSULTAR: {len(namespaces)}")
        
        if not namespaces:
            if episode_filter:
                print(f"⚠️ NAMESPACE '{target_namespace}' NÃO ENCONTRADO!")
            else:
                print("⚠️ NENHUM NAMESPACE ENCONTRADO NO PINECONE!")
                print("Execute: python main.py outliers-api --max-videos 1")
            print(f"{'='*60}\n")
            return []
        
        # Gerar embedding da query
        query_embedding = embeddings.embed_query(query)
        
        # Buscar em CADA namespace e combinar resultados
        all_results = []
        
        for namespace in namespaces:
            try:
                results = index.query(
                    vector=query_embedding,
                    top_k=k * 2,  # Pegar mais de cada namespace
                    include_metadata=True,
                    include_values=False,
                    namespace=namespace
                )
                
                for match in results.matches:
                    all_results.append({
                        'score': match.score,
                        'metadata': match.metadata,
                        'namespace': namespace
                    })
                    
            except Exception as e:
                print(f"⚠️ Erro ao buscar no namespace {namespace}: {e}")
                continue
        
        # Ordenar todos os resultados por score
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        if all_results:
            max_result = all_results[0]
            print(f"RESULTADOS BRUTOS: {len(all_results)}")
            print(f"MAIOR SCORE OBTIDO: {max_result['score']:.4f}")
            print(f"NAMESPACE: {max_result['namespace']}")
            text = max_result['metadata'].get('text', '')
            print(f"TEXTO DO MAIOR SCORE: {text[:200]}...")
            print(f"SPEAKER: {max_result['metadata'].get('speaker', 'Unknown')}")
            
            # Printar TOP 3 resultados
            print(f"\n{'─'*60}")
            print("TOP 3 RESULTADOS:")
            print(f"{'─'*60}")
            for idx, result in enumerate(all_results[:3], 1):
                text_preview = result['metadata'].get('text', '')[:150]
                score = result['score']
                speaker = result['metadata'].get('speaker', 'Unknown')
                print(f"\n[{idx}] SCORE: {score:.4f} | SPEAKER: {speaker}")
                print(f"    TEXTO: {text_preview}...")
            print(f"{'─'*60}")
        else:
            print("NENHUM RESULTADO ENCONTRADO NO PINECONE")
        
        print(f"{'='*60}\n")
        
        # Filtrar por threshold e formatar
        filtered_results = []
        for result in all_results[:k * 2]:  # Considerar top resultados
            score = result['score']
            
            if score >= score_threshold:
                metadata = result['metadata']
                episode_id = metadata.get("episode_id", "unknown")
                start_time = int(metadata.get("start_time", 0))
                
                # Criar link do YouTube com timestamp
                video_link = f"https://www.youtube.com/watch?v={episode_id}&t={start_time}s"
                
                filtered_results.append({
                    "text": metadata.get("text", ""),
                    "metadata": metadata,
                    "score": float(score),
                    "video_link": video_link,
                    "episode_id": episode_id,
                    "start_time": start_time,
                    "speaker": metadata.get("speaker", "Unknown"),
                    "episode_title": metadata.get("episode_title", "")
                })
        
        # Limitar a k resultados finais
        filtered_results = filtered_results[:k]
        
        print(f"RESULTADOS FILTRADOS (>= {score_threshold}): {len(filtered_results)}\n")
        
        return filtered_results
    
    except Exception as e:
        print(f"ERRO AO BUSCAR NO PINECONE: {e}")
        import traceback
        traceback.print_exc()
        return []


def format_context_for_llm(search_results):
    """Formata resultados do Pinecone para o LLM."""
    if not search_results:
        return "Nenhum contexto relevante encontrado no banco de dados."
    
    context_parts = []
    for i, result in enumerate(search_results, 1):
        episode_title = result['metadata'].get('episode_title', 'Episódio desconhecido')
        speaker = result['metadata'].get('speaker', 'Unknown')
        text = result['text']
        
        context_parts.append(
            f"[Contexto {i}] {episode_title}\n"
            f"Speaker: {speaker}\n"
            f"Trecho: {text}\n"
        )
    
    return "\n\n".join(context_parts)


@app.route('/')
def index():
    """Página inicial."""
    return render_template('index.html')


@app.route('/api/episodes')
def get_episodes():
    """Lista todos os episódios disponíveis para filtro no chatbot."""
    episodes = []
    
    for transcript_file in TRANSCRIPTS_DIR.glob("*.json"):
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
                metadata = transcript_data.get('episode_metadata', {})
                
                episodes.append({
                    'episode_id': metadata.get('episode_id', ''),
                    'title': metadata.get('title', 'Sem título'),
                    'episode_number': metadata.get('episode_number', 0),
                    'duration': metadata.get('duration_seconds', 0)
                })
        except Exception as e:
            print(f"Erro ao carregar episódio {transcript_file}: {e}")
    
    # Ordenar por número do episódio
    episodes.sort(key=lambda x: x.get('episode_number', 0))
    
    return jsonify(episodes)


@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint do chatbot com streaming."""
    data = request.json
    user_input = data.get('message', '')
    episode_filter = data.get('episode_filter')  # Novo: filtro de episódio
    session_id = session.get('session_id', str(datetime.now().timestamp()))
    session['session_id'] = session_id
    
    # Buscar contexto no Pinecone com filtro opcional
    search_results = search_pinecone(user_input, k=5, score_threshold=0.847, episode_filter=episode_filter)
    context_used = len(search_results) > 0
    
    # Formatar contexto
    context = format_context_for_llm(search_results)
    
    # Criar prompt com histórico
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])
    
    # Chain com histórico
    chain = prompt | llm
    
    with_message_history = RunnableWithMessageHistory(
        chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history"
    )
    
    def generate():
        """Generator para streaming de resposta."""
        try:
            for chunk in with_message_history.stream(
                {
                    "input": user_input,
                    "context": context
                },
                config={"configurable": {"session_id": session_id}}
            ):
                text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if text:  # Só enviar se houver texto
                    yield text
        
        except Exception as e:
            print(f"Erro no streaming: {e}")
            yield f"\n\n❌ Erro ao processar sua pergunta: {str(e)}"
    
    # Preparar headers customizados
    headers = {
        'Content-Type': 'text/plain; charset=utf-8',
        'X-Context-Used': str(context_used).lower(),
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    }
    
    # Adicionar links de vídeo se houver contexto
    if search_results:
        video_links = []
        for i, r in enumerate(search_results, 1):
            video_links.append({
                'url': r['video_link'],
                'title': f'Contexto {i}',
                'speaker': r['speaker'],
                'score': r['score']
            })
        headers['X-Video-Links'] = json.dumps(video_links, ensure_ascii=False)
        
        # Detalhes dos contextos
        contexts_info = [{
            'episode_title': r['metadata'].get('episode_title', ''),
            'speaker': r['metadata'].get('speaker', ''),
            'score': r['score'],
            'link': r['video_link']
        } for r in search_results]
        headers['X-Contexts-Info'] = json.dumps(contexts_info, ensure_ascii=False)
    
    return Response(generate(), headers=headers)


@app.route('/api/analyses')
def get_analyses():
    """Lista todas as análises disponíveis."""
    analyses = []
    
    for analysis_file in ANALYSES_DIR.glob("*_analysis.json"):
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
                
                # Usar data de modificação do arquivo se não houver timestamp
                file_mtime = datetime.fromtimestamp(analysis_file.stat().st_mtime).isoformat()
                
                analyses.append({
                    'id': analysis_data.get('episode_id', analysis_file.stem.replace('_analysis', '')),
                    'episode_id': analysis_data.get('episode_id', ''),
                    'episode_title': analysis_data.get('title', 'Sem título'),
                    'timestamp': file_mtime,
                    'file': analysis_file.name
                })
        except Exception as e:
            print(f"Erro ao carregar {analysis_file}: {e}")
    
    # Ordenar por timestamp (mais recente primeiro)
    analyses.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return jsonify(analyses)


@app.route('/api/analysis/<video_id>')
def get_analysis(video_id):
    """Retorna análise específica."""
    analysis_file = ANALYSES_DIR / f"{video_id}_analysis.json"
    
    if not analysis_file.exists():
        return jsonify({'error': 'Análise não encontrada'}), 404
    
    with open(analysis_file) as f:
        return jsonify(json.load(f))


@app.route('/api/marketing')
def get_marketing_list():
    """Lista todos os materiais de marketing disponíveis."""
    marketing_list = []
    
    for marketing_file in MARKETING_DIR.glob("*_marketing.json"):
        try:
            with open(marketing_file, 'r', encoding='utf-8') as f:
                marketing_data = json.load(f)
                marketing_list.append({
                    'id': marketing_data.get('episode_id', marketing_file.stem.replace('_marketing', '')),
                    'episode_id': marketing_data.get('episode_id', ''),
                    'episode_title': marketing_data.get('title', 'Sem título'),
                    'timestamp': marketing_data.get('generated_at', datetime.now().isoformat()),
                    'file': marketing_file.name
                })
        except Exception as e:
            print(f"Erro ao carregar {marketing_file}: {e}")
    
    # Ordenar por timestamp (mais recente primeiro)
    marketing_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return jsonify(marketing_list)


@app.route('/api/marketing/<video_id>')
def get_marketing(video_id):
    """Retorna material de marketing específico."""
    marketing_file = MARKETING_DIR / f"{video_id}_marketing.json"
    
    if not marketing_file.exists():
        return jsonify({'error': 'Marketing não encontrado'}), 404
    
    with open(marketing_file) as f:
        return jsonify(json.load(f))


@app.route('/api/transcripts')
def get_transcripts():
    """Lista todas as transcrições disponíveis."""
    transcripts = []
    
    for transcript_file in TRANSCRIPTS_DIR.glob("*.json"):
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
                metadata = transcript_data.get('episode_metadata', {})
                utterances = transcript_data.get('utterances', [])
                
                # Extrair speakers únicos
                speakers = []
                seen_speakers = set()
                for participant in metadata.get('participants', []):
                    speaker_name = participant.get('name', '')
                    if speaker_name and speaker_name not in seen_speakers:
                        speakers.append(speaker_name)
                        seen_speakers.add(speaker_name)
                
                transcripts.append({
                    'episode_id': metadata.get('episode_id', ''),
                    'title': metadata.get('title', 'Sem título'),
                    'duration': metadata.get('duration_seconds', 0),
                    'speakers': speakers,
                    'utterance_count': len(utterances),
                    'file': transcript_file.name
                })
        except Exception as e:
            print(f"Erro ao carregar {transcript_file}: {e}")
    
    return jsonify(transcripts)


@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    """Limpa histórico de conversa."""
    session_id = session.get('session_id')
    if session_id and session_id in conversation_histories:
        del conversation_histories[session_id]
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
