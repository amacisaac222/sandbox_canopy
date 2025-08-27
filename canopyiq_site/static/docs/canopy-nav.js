// Add CanopyIQ navigation back to main site
document.addEventListener('DOMContentLoaded', function() {
    // Add "Back to Main Site" button to docs header
    const headerInner = document.querySelector('.md-header__inner');
    if (headerInner) {
        const backButton = document.createElement('div');
        backButton.style.cssText = `
            position: absolute;
            right: 60px;
            top: 50%;
            transform: translateY(-50%);
            z-index: 1000;
        `;
        
        backButton.innerHTML = `
            <a href="/" style="
                color: #ff6f61;
                font-weight: bold;
                text-decoration: none;
                font-size: 14px;
                padding: 8px 16px;
                border: 1px solid #ff6f61;
                border-radius: 4px;
                transition: all 0.2s ease;
                background: rgba(255, 255, 255, 0.9);
                backdrop-filter: blur(4px);
                display: inline-block;
            " 
            onmouseover="this.style.backgroundColor='#ff6f61'; this.style.color='white';" 
            onmouseout="this.style.backgroundColor='rgba(255, 255, 255, 0.9)'; this.style.color='#ff6f61';"
            title="Return to CanopyIQ main site">
                ← Main Site
            </a>
        `;
        
        headerInner.appendChild(backButton);
    }
});