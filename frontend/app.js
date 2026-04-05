document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('queryInput');
    const submitBtn = document.getElementById('submitBtn');
    const statusSection = document.getElementById('statusSection');
    const statusText = document.getElementById('statusText');
    const progressBar = document.getElementById('progressBar');
    const activityLog = document.getElementById('activityLog');
    const resultSection = document.getElementById('resultSection');
    const markdownResult = document.getElementById('markdownResult');
    const newQueryBtn = document.getElementById('newQueryBtn');
    const inputSection = document.querySelector('.input-section');

    submitBtn.addEventListener('click', startResearch);
    newQueryBtn.addEventListener('click', resetUI);

    async function startResearch() {
        const question = queryInput.value.trim();
        if (!question) {
            alert('Please enter a research question.');
            return;
        }

        // UI State: Loading
        inputSection.classList.add('hidden');
        statusSection.classList.remove('hidden');
        submitBtn.disabled = true;
        activityLog.innerHTML = ''; // Clear old logs
        updateStatus("Initializing council...", 5);

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

    function handleProgress(text) {
        if (text.includes("Stage 1")) updateStatus("Agent A (Claude) is researching...", 20);
        else if (text.includes("Stage 2")) updateStatus("Agent B (GPT) is researching...", 45);
        else if (text.includes("Stage 3")) updateStatus("Agent C (Gemini) is researching...", 70);
        else if (text.includes("Stage 4")) updateStatus("Synthesizing final report...", 90);
        else statusText.innerText = text;
        
        // Add stage to log too
        handleActivity("System", text);
    }

    function handleActivity(author, text) {
        const entry = document.createElement('div');
        entry.className = `log-entry ${author}`;
        
        const authorSpan = document.createElement('span');
        authorSpan.className = 'log-author';
        authorSpan.innerText = `[${author}]`;
        
        const textSpan = document.createElement('span');
        textSpan.innerText = text;
        
        entry.appendChild(authorSpan);
        entry.appendChild(textSpan);
        activityLog.appendChild(entry);
        
        // Auto-scroll to bottom
        activityLog.scrollTop = activityLog.scrollHeight;
    }

    function updateStatus(text, percent) {
        statusText.innerText = text;
        progressBar.style.width = percent + '%';
    }

    function showResult(markdown) {
        statusSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        markdownResult.innerHTML = marked.parse(markdown);
    }

    function resetUI() {
        queryInput.value = '';
        inputSection.classList.remove('hidden');
        statusSection.classList.add('hidden');
        resultSection.classList.add('hidden');
        submitBtn.disabled = false;
        progressBar.style.width = '0%';
        activityLog.innerHTML = '';
    }
});
