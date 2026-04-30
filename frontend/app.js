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
    const traceHeader = document.getElementById('traceHeader');
    const collapseBtn = document.getElementById('collapseBtn');

    const cards = {
        'ResearchAgentA': document.getElementById('card-research_a'),
        'ResearchAgentB': document.getElementById('card-research_b'),
        'ResearchAgentC': document.getElementById('card-research_c'),
        'VisualizationAgent': document.getElementById('card-visualization'),
        'SynthesizerAgent': document.getElementById('card-synthesizer')
    };

    const authorMap = {
        'ResearchAgentA': 'Expert Lens',
        'ResearchAgentB': 'Analytical Lens',
        'ResearchAgentC': 'Technical Lens',
        'VisualizationAgent': 'Visualization Specialist',
        'SynthesizerAgent': 'Council Synthesizer',
        'query_router': 'Router',
        'discovery_service': 'Discovery',
        'dynamic_research_hub': 'Research Hub',
        'viz_broadcaster': 'Viz Broadcaster',
        'synth_broadcaster': 'Synth Broadcaster',
        'system_start': 'System',
        'system_research': 'System',
        'system_viz': 'System',
        'system_synth': 'System'
    };

    submitBtn.addEventListener('click', startResearch);
    newQueryBtn.addEventListener('click', resetUI);
    traceHeader.addEventListener('click', toggleTrace);

    function toggleTrace() {
        traceSection.classList.toggle('collapsed');
        collapseBtn.innerText = traceSection.classList.contains('collapsed') ? 'Expand' : 'Collapse';
    }

    function updateCard(id, state, msg) {
        const card = cards[id];
        if (!card) return;
        
        card.className = 'status-card ' + state;
        card.querySelector('.card-status').innerText = msg;
    }

    function logTrace(author, text, isSystem = false) {
        const entry = document.createElement('div');
        entry.className = isSystem ? 'trace-entry system' : 'trace-entry';
        
        const displayName = authorMap[author] || author;
        
        if (isSystem) {
            entry.innerHTML = `<span class="trace-text">${text}</span>`;
        } else {
            entry.innerHTML = `<span class="trace-author">${displayName}:</span><span class="trace-text">${text}</span>`;
        }
        
        traceLog.appendChild(entry);
        traceLog.scrollTop = traceLog.scrollHeight;
    }

    let accumulatedMarkdown = "";

    async function startResearch() {
        const question = queryInput.value.trim();
        if (!question) {
            alert('Please enter a research question.');
            return;
        }

        accumulatedMarkdown = ""; // Reset accumulation
        inputSection.classList.add('hidden');
        statusSection.classList.remove('hidden');
        traceSection.classList.remove('hidden');
        traceSection.classList.remove('collapsed');
        collapseBtn.innerText = 'Collapse';
        traceLog.innerHTML = ''; // Clear previous traces
        markdownResult.innerHTML = ''; // Clear previous results
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
                        } else if (data.type === 'partial_result') {
                            accumulatedMarkdown += data.text;
                            updateLiveResult(accumulatedMarkdown);
                        } else if (data.type === 'result') {
                            showFinalResult(data.text || accumulatedMarkdown);
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
            updateStatus("📊 Stage 3: Visualization: Analyzing data and generating charts...", 80);
            updateCard('ResearchAgentA', 'completed', 'Analysis Done');
            updateCard('ResearchAgentB', 'completed', 'Analysis Done');
            updateCard('ResearchAgentC', 'completed', 'Analysis Done');
            updateCard('VisualizationAgent', 'active', 'Analyzing Data...');
        } else if (text.includes("Stage 4")) {
            updateStatus("🏛️ Stage 4: Synthesizing grounded final report...", 95);
            updateCard('VisualizationAgent', 'completed', 'Charts Generated');
            updateCard('SynthesizerAgent', 'active', 'Synthesizing...');
        }
    }

    function handleActivity(author, text) {
        // Update the main status line with the live agent thought/action
        const cleanText = text.replace(/\[Stage.*?\]/g, '').trim();
        const displayName = authorMap[author] || author;
        statusText.innerHTML = `<span class="live-tag">LIVE</span> [${displayName}] ${cleanText}`;
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

    function updateLiveResult(markdown) {
        if (resultSection.classList.contains('hidden')) {
            resultSection.classList.remove('hidden');
        }
        markdownResult.innerHTML = marked.parse(markdown);
        // Scroll to the bottom of the result as it grows
        markdownResult.scrollTop = markdownResult.scrollHeight;
    }

    function showFinalResult(markdown) {
        updateCard('SynthesizerAgent', 'completed', 'Final Report Published');
        statusSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        markdownResult.innerHTML = marked.parse(markdown);
        
        // Auto-collapse the trace to show the report more clearly
        traceSection.classList.add('collapsed');
        collapseBtn.innerText = 'Expand';
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
