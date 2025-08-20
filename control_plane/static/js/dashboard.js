// Agent Sandbox - Interactive Dashboard
class AgentSandboxDashboard {
  constructor() {
    this.apiBase = '';
    this.refreshInterval = 5000; // 5 seconds
    this.init();
  }

  async init() {
    await this.loadDashboardData();
    this.startAutoRefresh();
    this.bindEvents();
  }

  async loadDashboardData() {
    try {
      // Load audit data
      const auditData = await this.fetchJSON('/v1/audit/export?frm=0&to=9999999999');
      this.updateAuditStats(auditData);

      // Load system status
      const healthData = await this.fetchJSON('/health');
      this.updateSystemStatus(healthData);

    } catch (error) {
      console.error('Error loading dashboard data:', error);
      this.showError('Failed to load dashboard data');
    }
  }

  async fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  updateAuditStats(auditData) {
    const stats = this.calculateStats(auditData);
    
    // Update stats cards
    this.updateElement('#total-decisions', stats.total);
    this.updateElement('#pending-approvals', stats.pending);
    this.updateElement('#approved-count', stats.approved);
    this.updateElement('#denied-count', stats.denied);

    // Update status indicators
    this.updateStatusIndicator('#system-status', stats.pending > 0 ? 'warning' : 'success');
  }

  calculateStats(auditData) {
    return {
      total: auditData.length,
      pending: auditData.filter(item => item.status === 'pending').length,
      approved: auditData.filter(item => item.status === 'approved').length,
      denied: auditData.filter(item => item.status === 'denied').length
    };
  }

  updateSystemStatus(healthData) {
    const statusElement = document.getElementById('system-health');
    if (statusElement) {
      statusElement.textContent = healthData.ok ? 'Healthy' : 'Degraded';
      statusElement.className = `status-indicator ${healthData.ok ? 'status-success' : 'status-danger'}`;
    }
  }

  updateElement(selector, value) {
    const element = document.querySelector(selector);
    if (element) {
      element.textContent = value;
    }
  }

  updateStatusIndicator(selector, status) {
    const element = document.querySelector(selector);
    if (element) {
      element.className = `status-indicator status-${status}`;
    }
  }

  startAutoRefresh() {
    setInterval(() => {
      this.loadDashboardData();
    }, this.refreshInterval);
  }

  bindEvents() {
    // Approval buttons
    document.addEventListener('click', async (e) => {
      if (e.target.matches('.approve-btn')) {
        await this.handleApproval(e.target.dataset.approvalId, 'approve');
      } else if (e.target.matches('.deny-btn')) {
        await this.handleApproval(e.target.dataset.approvalId, 'deny');
      }
    });

    // Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadDashboardData());
    }
  }

  async handleApproval(approvalId, decision) {
    try {
      const formData = new FormData();
      formData.append('decision', decision);

      const response = await fetch(`/v1/approvals/${approvalId}/decision`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        this.showSuccess(`Request ${decision}d successfully`);
        await this.loadDashboardData();
        // Refresh the approvals list if we're on that page
        if (window.location.pathname === '/approvals') {
          window.location.reload();
        }
      } else {
        throw new Error(`Failed to ${decision} request`);
      }
    } catch (error) {
      console.error('Error handling approval:', error);
      this.showError(`Failed to ${decision} request`);
    }
  }

  showSuccess(message) {
    this.showNotification(message, 'success');
  }

  showError(message) {
    this.showNotification(message, 'error');
  }

  showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 1rem 1.5rem;
      border-radius: 8px;
      color: white;
      font-weight: 500;
      z-index: 1000;
      opacity: 0;
      transform: translateX(100%);
      transition: all 0.3s ease;
      background: ${type === 'success' ? '#10b981' : '#ef4444'};
    `;

    document.body.appendChild(notification);

    // Animate in
    setTimeout(() => {
      notification.style.opacity = '1';
      notification.style.transform = 'translateX(0)';
    }, 10);

    // Animate out and remove
    setTimeout(() => {
      notification.style.opacity = '0';
      notification.style.transform = 'translateX(100%)';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  // Real-time metrics simulation
  simulateRealTimeMetrics() {
    // This would connect to WebSocket or Server-Sent Events in production
    const metricsElements = {
      requestsPerSecond: document.getElementById('requests-per-second'),
      responseTime: document.getElementById('response-time'),
      errorRate: document.getElementById('error-rate')
    };

    setInterval(() => {
      if (metricsElements.requestsPerSecond) {
        const rps = Math.floor(Math.random() * 50) + 10;
        metricsElements.requestsPerSecond.textContent = rps;
      }

      if (metricsElements.responseTime) {
        const rt = Math.floor(Math.random() * 100) + 50;
        metricsElements.responseTime.textContent = `${rt}ms`;
      }

      if (metricsElements.errorRate) {
        const er = (Math.random() * 2).toFixed(2);
        metricsElements.errorRate.textContent = `${er}%`;
      }
    }, 2000);
  }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.dashboard = new AgentSandboxDashboard();
});