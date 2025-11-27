// ==================== GLOBAL STATE ====================
let currentSection = 'chat';
let analyses = [];
let marketing = [];
let transcripts = [];

// ==================== NAVIGATION ====================
document.addEventListener('DOMContentLoaded', () => {
    // Setup navigation
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const section = btn.dataset.section;
            switchSection(section);
        });
    });

    // Setup chat
    setupChat();
    
    // Load initial data
    loadAnalyses();
    loadMarketing();
    loadTranscripts();
});

function switchSection(sectionName) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');

    // Update content
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${sectionName}-section`).classList.add('active');

    currentSection = sectionName;
}

// ==================== CHAT ====================
function setupChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-chat');

    sendBtn.addEventListener('click', sendMessage);
    clearBtn.addEventListener('click', clearChat);
    
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message
    addMessage('user', message);
    input.value = '';
    
    // Add typing indicator
    const botMsgDiv = addMessage('bot', '');
    const bubble = botMsgDiv.querySelector('.message-bubble');
    bubble.innerHTML = '<span class="typing-indicator"></span> <span class="typing-indicator"></span> <span class="typing-indicator"></span>';
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            throw new Error('Erro na resposta do servidor');
        }

        // Get headers
        const contextUsed = response.headers.get('X-Context-Used') === 'true';
        const videoLinksHeader = response.headers.get('X-Video-Links');
        const contextsInfoHeader = response.headers.get('X-Contexts-Info');
        
        // Parse video links
        let videoLinks = [];
        if (videoLinksHeader) {
            try {
                videoLinks = JSON.parse(videoLinksHeader);
            } catch (e) {
                console.error('Error parsing video links:', e);
            }
        }

        // Add context indicator
        if (contextUsed) {
            botMsgDiv.classList.add('with-context');
        }

        // Clear typing indicator
        bubble.innerHTML = '';

        // Add video links if present
        if (videoLinks.length > 0) {
            const linksContainer = document.createElement('div');
            linksContainer.className = 'video-links';
            
            videoLinks.forEach(link => {
                const linkEl = document.createElement('a');
                linkEl.href = link.url;
                linkEl.target = '_blank';
                linkEl.className = 'video-link';
                linkEl.innerHTML = `<span class="icon"></span>${link.title}`;
                linkEl.title = `${link.speaker} - Score: ${link.score.toFixed(2)}`;
                linksContainer.appendChild(linkEl);
            });
            
            bubble.appendChild(linksContainer);
        }

        // Create text container
        const textContainer = document.createElement('div');
        bubble.appendChild(textContainer);

        // Stream response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const text = decoder.decode(value);
            textContainer.textContent += text;
            
            // Scroll to bottom
            scrollToBottom();
        }

    } catch (error) {
        console.error('Chat error:', error);
        bubble.innerHTML = 'Erro ao enviar mensagem. Tente novamente.';
    }
}

function addMessage(type, text) {
    const messagesDiv = document.getElementById('chat-messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = text;
    
    messageDiv.appendChild(bubble);
    messagesDiv.appendChild(messageDiv);
    
    scrollToBottom();
    
    return messageDiv;
}

function scrollToBottom() {
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function clearChat() {
    try {
        await fetch('/api/clear-history', {
            method: 'POST'
        });
        
        const messagesDiv = document.getElementById('chat-messages');
        messagesDiv.innerHTML = `
            <div class="message bot">
                <div class="message-bubble">
                    Olá! Sou o Agente Inteligente da Outliers Advisory. Posso te ajudar com análises, estratégias de marketing e insights sobre os episódios do Second Level Podcast. Como posso ajudar?
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Clear chat error:', error);
    }
}

// ==================== ANALYSES ====================
async function loadAnalyses() {
    try {
        const response = await fetch('/api/analyses');
        analyses = await response.json();
        
        renderAnalyses();
    } catch (error) {
        console.error('Load analyses error:', error);
        document.getElementById('analyses-list').innerHTML = '<p class="loading">Erro ao carregar análises</p>';
    }
}

function renderAnalyses() {
    const container = document.getElementById('analyses-list');
    
    if (analyses.length === 0) {
        container.innerHTML = '<p class="loading">Nenhuma análise disponível</p>';
        return;
    }
    
    container.innerHTML = analyses.map(analysis => `
        <div class="card" onclick="showAnalysisDetail('${analysis.id}')">
            <h3>${analysis.episode_title}</h3>
            <p><strong>Episódio:</strong> ${analysis.episode_id}</p>
            <p><strong>Data:</strong> ${new Date(analysis.timestamp).toLocaleDateString('pt-BR')}</p>
            <span class="badge">Ver análise completa</span>
        </div>
    `).join('');
}

async function showAnalysisDetail(id) {
    try {
        const response = await fetch(`/api/analysis/${id}`);
        const analysis = await response.json();
        
        // Switch to detail view
        document.getElementById('analyses-list').style.display = 'none';
        document.getElementById('analysis-detail').style.display = 'block';
        
        // Populate content
        document.getElementById('analysis-title').textContent = analysis.title || 'Análise';
        document.getElementById('analysis-content').innerHTML = formatAnalysisContent(analysis.analysis);
        
    } catch (error) {
        console.error('Show analysis error:', error);
    }
}

function formatAnalysisContent(content) {
    // Convert markdown-like formatting to HTML
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    content = content.replace(/\n\n/g, '</p><p>');
    content = content.replace(/\n/g, '<br>');
    content = content.replace(/^- /gm, '<li>');
    content = content.replace(/<li>/g, '<ul><li>').replace(/<\/li>(?!<li>)/g, '</li></ul>');
    
    return `<p>${content}</p>`;
}

function backToAnalyses() {
    document.getElementById('analyses-list').style.display = 'grid';
    document.getElementById('analysis-detail').style.display = 'none';
}

// ==================== MARKETING ====================
async function loadMarketing() {
    try {
        const response = await fetch('/api/marketing');
        marketing = await response.json();
        
        renderMarketing();
    } catch (error) {
        console.error('Load marketing error:', error);
        document.getElementById('marketing-list').innerHTML = '<p class="loading">Erro ao carregar materiais</p>';
    }
}

function renderMarketing() {
    const container = document.getElementById('marketing-list');
    
    if (marketing.length === 0) {
        container.innerHTML = '<p class="loading">Nenhum material disponível</p>';
        return;
    }
    
    container.innerHTML = marketing.map(item => `
        <div class="card" onclick="showMarketingDetail('${item.id}')">
            <h3>${item.episode_title}</h3>
            <p><strong>Episódio:</strong> ${item.episode_id}</p>
            <p><strong>Data:</strong> ${new Date(item.timestamp).toLocaleDateString('pt-BR')}</p>
            <span class="badge">Ver material completo</span>
        </div>
    `).join('');
}

async function showMarketingDetail(id) {
    try {
        const response = await fetch(`/api/marketing/${id}`);
        const item = await response.json();
        
        // Switch to detail view
        document.getElementById('marketing-list').style.display = 'none';
        document.getElementById('marketing-detail').style.display = 'block';
        
        // Populate content
        document.getElementById('marketing-title').textContent = item.title || 'Material de Marketing';
        document.getElementById('marketing-content').innerHTML = formatMarketingContent(item);
        
    } catch (error) {
        console.error('Show marketing error:', error);
    }
}

function formatMarketingContent(content) {
    let html = '';
    
    // LinkedIn Post
    if (content.linkedin_post) {
        html += '<h3>LinkedIn Post</h3>';
        html += `<pre>${content.linkedin_post}</pre>`;
    }
    
    // Carousel Slides
    if (content.carousel_slides && content.carousel_slides.length > 0) {
        html += '<h3>Carrossel Instagram</h3>';
        content.carousel_slides.forEach((slide, idx) => {
            html += `
                <div class="carousel-slide">
                    <h4>Slide ${idx + 1}: ${slide.title}</h4>
                    <ul>
                        ${slide.bullets.map(bullet => `<li>${bullet}</li>`).join('')}
                    </ul>
                </div>
            `;
        });
    }
    
    // Quotes
    if (content.quotes && content.quotes.length > 0) {
        html += '<h3>Citações em Destaque</h3>';
        content.quotes.forEach(quote => {
            html += `
                <div class="quote-card">
                    <div class="quote-text">"${quote.quote}"</div>
                    <div class="quote-author">— ${quote.speaker_name} (${quote.speaker_role})</div>
                </div>
            `;
        });
    }
    
    // Executive Summary
    if (content.executive_summary) {
        html += '<h3>Sumário Executivo</h3>';
        html += `<pre>${content.executive_summary}</pre>`;
    }
    
    return html || '<p>Conteúdo não disponível</p>';
}

function backToMarketing() {
    document.getElementById('marketing-list').style.display = 'grid';
    document.getElementById('marketing-detail').style.display = 'none';
}

// ==================== TRANSCRIPTS ====================
async function loadTranscripts() {
    try {
        const response = await fetch('/api/transcripts');
        transcripts = await response.json();
        
        renderTranscripts();
    } catch (error) {
        console.error('Load transcripts error:', error);
        document.getElementById('transcripts-list').innerHTML = '<p class="loading">Erro ao carregar transcrições</p>';
    }
}

function renderTranscripts() {
    const container = document.getElementById('transcripts-list');
    
    if (transcripts.length === 0) {
        container.innerHTML = '<p class="loading">Nenhuma transcrição disponível</p>';
        return;
    }
    
    container.innerHTML = transcripts.map(transcript => `
        <div class="card">
            <h3>${transcript.title}</h3>
            <p><strong>ID:</strong> ${transcript.episode_id}</p>
            <p><strong>Duração:</strong> ${formatDuration(transcript.duration)}</p>
            <p><strong>Speakers:</strong> ${transcript.speakers?.join(', ') || 'N/A'}</p>
            <p><strong>Utterances:</strong> ${transcript.utterance_count || 'N/A'}</p>
            <a href="https://www.youtube.com/watch?v=${transcript.episode_id}" 
               target="_blank" 
               class="badge" 
               style="text-decoration: none; background: var(--navy); color: var(--white);">
                Ver no YouTube
            </a>
        </div>
    `).join('');
}

function formatDuration(seconds) {
    if (!seconds) return 'N/A';
    
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes % 60}min`;
    }
    return `${minutes}min`;
}
