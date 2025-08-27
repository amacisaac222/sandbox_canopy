// Add "Back to Main Site" button to docs
document.addEventListener('DOMContentLoaded', function() {
    // Find the header navigation
    const headerNav = document.querySelector('.md-header__inner');
    if (headerNav) {
        // Create a "Back to Main Site" button
        const backButton = document.createElement('div');
        backButton.innerHTML = `
            <a href="/" class="md-header__button" title="Back to Main Site" style="
                position: absolute;
                right: 60px;
                top: 50%;
                transform: translateY(-50%);
                color: #ff6f61;
                font-weight: bold;
                text-decoration: none;
                font-size: 14px;
                padding: 8px 16px;
                border: 1px solid #ff6f61;
                border-radius: 4px;
                transition: all 0.2s ease;
            " onmouseover="this.style.backgroundColor='#ff6f61'; this.style.color='white';" 
               onmouseout="this.style.backgroundColor='transparent'; this.style.color='#ff6f61';">
                ← Main Site
            </a>
        `;
        headerNav.appendChild(backButton);
    }
});