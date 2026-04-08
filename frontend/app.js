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

    const cards = {
        'research_a': document.getElementById('card-research_a'),
        'research_b': document.getElementById('card-research_b'),
        'research_c': document.getElementById('card-research_c'),
        'synthesizer': document.getElementById('card-synthesizer')
    };

    submitBtn.addEventListener('click', startResearch);
    newQueryBtn.addEventListener('click', resetUI);

    function updateCard(id, state, msg) {
        const card = cards[id];
        if (!card) return;
        
        card.className = 'status-card ' + state;
        card.querySelector('.card-status').innerText = msg;
    }

    async function startResearch() {
        const question = queryInput.value.trim();
        if (!question) {
            alert('Please enter a research question.');
            return;
        }

        inputSection.classList.add('hidden');
        statusSection.classList.remove('hidden');
        submitBtn.disabled = true;
        resetCards();
        updateStatus("Initializing conclave...", 5);

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
                            handleProgress(data.text);
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

    function handleProgress(text) {
        if (text.includes("Stage 1")) {
            updateStatus("Agent A (Claude) is researching...", 20);
            updateCard('research_a', 'active', 'Researching live web...');
        } else if (text.includes("Stage 2")) {
            updateStatus("Agent B (GPT) is researching...", 45);
            updateCard('research_a', 'completed', '5 Citations Recorded');
            updateCard('research_b', 'active', 'Analyzing trends...');
        } else if (text.includes("Stage 3")) {
            updateStatus("Agent C (Gemini) is researching...", 70);
            updateCard('research_b', 'completed', '5 Citations Recorded');
            updateCard('research_c', 'active', 'Technical verification...');
        } else if (text.includes("Stage 4")) {
            updateStatus("Synthesizing final report...", 90);
            updateCard('research_c', 'completed', '5 Citations Recorded');
            updateCard('synthesizer', 'active', 'Generating report...');
        }
    }

    function updateStatus(text, percent) {
        statusText.innerText = text;
        progressBar.style.width = percent + '%';
    }

    function showResult(markdown) {
        updateCard('synthesizer', 'completed', 'Report Ready');
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
        resultSection.classList.add('hidden');
        submitBtn.disabled = false;
        progressBar.style.width = '0%';
    }
});
