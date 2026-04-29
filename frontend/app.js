document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('queryInput');
    const submitBtn = document.getElementById('submitBtn');
    const statusSection = document.getElementById('statusSection');
    const statusText = document.getElementById('statusText');
    const progressBar = document.getElementById('progressBar');
    const resultSection = document.getElementById('resultSection');
    const markdownResult = document.getElementById('markdownResult');
    const newQueryBtn = document.getElementById('newQueryBtn');
    const inputSection = document.querySelector('.input-section');
    const traceSection = document.getElementById('traceSection');
    const traceLog = document.getElementById('traceLog');

    const cards = {
        'ResearchAgentA': document.getElementById('card-research_a'),
        'ResearchAgentB': document.getElementById('card-research_b'),
        'ResearchAgentC': document.getElementById('card-research_c'),
        'SynthesizerAgent': document.getElementById('card-synthesizer')
    };

    submitBtn.addEventListener('click', startResearch);
    newQueryBtn.addEventListener('click', resetUI);

    function updateCard(id, state, msg) {
        const card = cards[id];
        if (!card) return;
        
        card.className = 'status-card ' + state;
        card.querySelector('.card-status').innerText = msg;
    }

    function logTrace(author, text, isSystem = false) {
        const entry = document.createElement('div');
        entry.className = isSystem ? 'trace-entry system' : 'trace-entry';
        
        if (isSystem) {
            entry.innerHTML = `<span class="trace-text">${text}</span>`;
        } else {
            entry.innerHTML = `<span class="trace-author">${author}:</span><span class="trace-text">${text}</span>`;
        }
        
        traceLog.appendChild(entry);
        traceLog.scrollTop = traceLog.scrollHeight;
    }

    async function startResearch() {
        const question = queryInput.value.trim();
        if (!question) {
            alert('Please enter a research question.');
            return;
        }

        inputSection.classList.add('hidden');
        statusSection.classList.remove('hidden');
        traceSection.classList.remove('hidden');
        traceLog.innerHTML = ''; // Clear previous traces
        submitBtn.disabled = true;
        resetCards();
        updateStatus("🏛️ Summoning the Model Conclave...", 5);
        logTrace("System", "Initializing multi-agent session...", true);

        try {
            const response = await fetch('/api/chat_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: question })
            });

            if (!response.ok) throw new Error('Failed to start research conclave');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.type === 'progress') {
                            handleStageChange(data.text);
                        } else if (data.type === 'activity') {
                            handleActivity(data.author, data.text);
                        } else if (data.type === 'result') {
                            showResult(data.text);
                        }
                    } catch (e) {
                        console.error("Error parsing NDJSON chunk", e);
                    }
                }
            }
        } catch (error) {
            alert('Error: ' + error.message);
            resetUI();
        }
    }

    function handleStageChange(text) {
        logTrace("System", `--- ${text} ---`, true);
        if (text.includes("Stage 1")) {
            updateStatus("🧪 Stage 1: Discovery & Parallel Research Init...", 20);
            updateCard('ResearchAgentA', 'active', 'Initializing...');
        } else if (text.includes("Stage 2")) {
            updateStatus("📈 Stage 2: Parallel Multi-perspective Analysis...", 60);
            updateCard('ResearchAgentB', 'active', 'Initializing...');
            updateCard('ResearchAgentC', 'active', 'Initializing...');
        } else if (text.includes("Stage 3")) {
            updateStatus("🏛️ Stage 3: Synthesizing grounded final report...", 90);
            updateCard('ResearchAgentA', 'completed', 'Analysis Done');
            updateCard('ResearchAgentB', 'completed', 'Analysis Done');
            updateCard('ResearchAgentC', 'completed', 'Analysis Done');
            updateCard('SynthesizerAgent', 'active', 'Synthesizing...');
        }
    }

    function handleActivity(author, text) {
        // Update the main status line with the live agent thought/action
        const cleanText = text.replace(/\[Stage.*?\]/g, '').trim();
        statusText.innerHTML = `<span class="live-tag">LIVE</span> [${author}] ${cleanText}`;
        logTrace(author, cleanText);
        
        // Update the status on the card specifically
        if (cards[author]) {
            cards[author].querySelector('.card-status').innerText = cleanText;
        }
    }

    function updateStatus(text, percent) {
        statusText.innerText = text;
        progressBar.style.width = percent + '%';
    }

    function showResult(markdown) {
        updateCard('SynthesizerAgent', 'completed', 'Final Report Published');
        statusSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        markdownResult.innerHTML = marked.parse(markdown);
    }

    function resetCards() {
        Object.keys(cards).forEach(id => updateCard(id, '', 'Waiting...'));
    }

    function resetUI() {
        queryInput.value = '';
        inputSection.classList.remove('hidden');
        statusSection.classList.add('hidden');
        traceSection.classList.add('hidden');
        resultSection.classList.add('hidden');
        submitBtn.disabled = false;
        progressBar.style.width = '0%';
    }
});
