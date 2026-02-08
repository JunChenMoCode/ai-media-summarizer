// Helper to create button
function createAnalyzeButton(url) {
  const btn = document.createElement('button');
  btn.className = 'ai-analysis-btn';
  btn.innerText = 'AI Analysis';
  
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (btn.classList.contains('loading') || btn.classList.contains('success')) return;
    
    btn.innerText = 'Queuing...';
    btn.classList.add('loading');
    
    try {
      const res = await fetch('http://localhost:18000/tasks/enqueue', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: url })
      });
      
      if (res.ok) {
        const data = await res.json();
        btn.innerText = 'Queued';
        btn.classList.remove('loading');
        btn.classList.add('success');
        console.log('Task queued:', data);
      } else {
        throw new Error('Failed');
      }
    } catch (err) {
      console.error(err);
      btn.innerText = 'Error';
      btn.classList.remove('loading');
      setTimeout(() => {
        btn.innerText = 'AI Analysis';
      }, 2000);
    }
  });
  
  return btn;
}

// Function to process video cards
function processCards() {
  // Selectors for different Bilibili layouts
  const selectors = [
    '.bili-video-card', // New home page
    '.video-card',      // Old/Search
    '.feed-card',       // Feed
    '.rank-item',       // Ranking
    '.bili-video-card__wrap' // Specific wrapper
  ];
  
  selectors.forEach(selector => {
    const cards = document.querySelectorAll(selector);
    cards.forEach(card => {
      if (card.dataset.aiProcessed) return;
      
      // Try to find the link
      const link = card.querySelector('a[href*="/video/BV"]');
      if (!link) return;
      
      let href = link.href;
      // Cleanup url
      if (href.startsWith('//')) href = 'https:' + href;
      
      // Find where to inject (usually the cover container)
      const cover = card.querySelector('.bili-video-card__image--wrap') || 
                   card.querySelector('.pic-box') || 
                   card.querySelector('.cover') ||
                   card;
                   
      if (cover) {
        // Ensure relative positioning
        if (getComputedStyle(cover).position === 'static') {
          cover.style.position = 'relative';
        }
        
        const btn = createAnalyzeButton(href);
        cover.appendChild(btn);
        card.dataset.aiProcessed = 'true';
      }
    });
  });
}

// Run initially
processCards();

// Run on mutations (infinite scroll)
const observer = new MutationObserver((mutations) => {
  let shouldRun = false;
  for (const m of mutations) {
    if (m.addedNodes.length) {
      shouldRun = true;
      break;
    }
  }
  if (shouldRun) processCards();
});

observer.observe(document.body, { childList: true, subtree: true });
