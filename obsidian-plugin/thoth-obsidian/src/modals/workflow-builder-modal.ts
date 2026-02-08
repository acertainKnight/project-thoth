/**
 * Workflow Builder Modal
 *
 * Multi-step wizard for adding custom article sources using LLM-powered auto-detection.
 * Steps: URL Input → Analysis → Review Samples → (Optional Refinement) → Confirm & Save
 */

import { App, Modal, Notice } from 'obsidian';

interface SampleArticle {
  title: string;
  authors: string[] | string;
  url?: string;
  publication_date?: string;
}

interface SearchFilter {
  element_type: string;
  description?: string;
  css_selector?: string;
}

interface AnalysisResult {
  page_title: string;
  page_type: string;
  confidence: number;
  total_articles_found: number;
  article_container_selector: string;
  selectors: Record<string, any>;
  sample_articles: SampleArticle[];
  pagination_selector?: string;
  search_filters: SearchFilter[];
  notes: string;
}

type WorkflowStep = 'input' | 'analyzing' | 'review' | 'refining' | 'saving' | 'success';

export class WorkflowBuilderModal extends Modal {
  private plugin: any;
  private currentStep: WorkflowStep = 'input';
  private url: string = '';
  private analysisResult: AnalysisResult | null = null;
  private stepContainer: HTMLElement;

  constructor(app: App, plugin: any) {
    super(app);
    this.plugin = plugin;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass('thoth-workflow-builder-modal');

    // Modal header
    const header = contentEl.createEl('h2', { text: '🔧 Add Custom Article Source' });
    header.style.cssText = 'margin-bottom: 20px; border-bottom: 2px solid var(--background-modifier-border); padding-bottom: 10px;';

    // Progress indicator
    this.renderProgressIndicator(contentEl);

    // Step container (dynamic content)
    this.stepContainer = contentEl.createDiv({ cls: 'thoth-workflow-step-container' });
    this.stepContainer.style.cssText = 'min-height: 300px; margin-top: 20px;';

    // Render current step
    this.renderCurrentStep();
  }

  private renderProgressIndicator(containerEl: HTMLElement) {
    const progressBar = containerEl.createDiv({ cls: 'thoth-workflow-progress' });
    progressBar.style.cssText = 'display: flex; justify-content: space-between; margin: 20px 0; padding: 0 20px;';

    const steps = [
      { id: 'input', label: '1. URL' },
      { id: 'review', label: '2. Review' },
      { id: 'saving', label: '3. Save' }
    ];

    steps.forEach((step, index) => {
      const stepEl = progressBar.createDiv({ cls: 'progress-step' });
      const isActive = this.getStepIndex(this.currentStep) >= index;
      const isCurrent = this.getStepIndex(this.currentStep) === index;

      stepEl.style.cssText = `
        flex: 1;
        text-align: center;
        padding: 8px;
        border-radius: 4px;
        ${isActive ? 'background: var(--interactive-accent); color: var(--text-on-accent);' : 'background: var(--background-secondary);'}
        ${isCurrent ? 'font-weight: bold; box-shadow: 0 0 8px var(--interactive-accent);' : ''}
      `;

      stepEl.textContent = step.label;
    });
  }

  private getStepIndex(step: WorkflowStep): number {
    const steps: WorkflowStep[] = ['input', 'analyzing', 'review', 'refining', 'saving', 'success'];
    return Math.min(2, Math.floor(steps.indexOf(step) / 2)); // Map to 0, 1, or 2
  }

  private renderCurrentStep() {
    this.stepContainer.empty();

    switch (this.currentStep) {
      case 'input':
        this.renderInputStep();
        break;
      case 'analyzing':
        this.renderAnalyzingStep();
        break;
      case 'review':
        this.renderReviewStep();
        break;
      case 'refining':
        this.renderRefiningStep();
        break;
      case 'saving':
        this.renderSavingStep();
        break;
      case 'success':
        this.renderSuccessStep();
        break;
    }
  }

  private renderInputStep() {
    const container = this.stepContainer;

    container.createEl('p', {
      text: 'Enter the URL of a page with article listings (journal TOC, conference proceedings, search results, etc.)'
    });

    const inputGroup = container.createDiv({ cls: 'input-group' });
    inputGroup.style.cssText = 'margin: 20px 0;';

    const label = inputGroup.createEl('label', { text: 'URL:' });
    label.style.cssText = 'display: block; margin-bottom: 8px; font-weight: 500;';

    const input = inputGroup.createEl('input', {
      type: 'text',
      placeholder: 'https://example.com/papers',
      value: this.url
    });
    input.style.cssText = 'width: 100%; padding: 10px; border: 1px solid var(--background-modifier-border); border-radius: 4px; font-size: 14px;';
    input.focus();

    input.addEventListener('input', () => {
      this.url = input.value.trim();
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && this.url) {
        this.analyzeUrl();
      }
    });

    // Examples
    const examplesEl = container.createDiv({ cls: 'examples' });
    examplesEl.style.cssText = 'margin: 20px 0; padding: 15px; background: var(--background-secondary); border-radius: 4px; font-size: 12px;';
    examplesEl.createEl('strong', { text: 'Examples:' });
    const examplesList = examplesEl.createEl('ul');
    examplesList.style.cssText = 'margin: 5px 0 0 20px;';
    [
      'https://www.nber.org/papers',
      'https://arxiv.org/list/cs.AI/recent',
      'https://jmlr.org/papers/v25/'
    ].forEach(example => {
      const li = examplesList.createEl('li');
      const link = li.createEl('a', { text: example, href: '#' });
      link.onclick = (e) => {
        e.preventDefault();
        this.url = example;
        input.value = example;
        input.focus();
      };
    });

    // Buttons
    const buttonContainer = container.createDiv();
    buttonContainer.style.cssText = 'display: flex; justify-content: flex-end; gap: 10px; margin-top: 30px;';

    const cancelBtn = buttonContainer.createEl('button', { text: 'Cancel' });
    cancelBtn.style.cssText = 'padding: 10px 20px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    cancelBtn.onclick = () => this.close();

    const analyzeBtn = buttonContainer.createEl('button', { text: '🔍 Analyze URL' });
    analyzeBtn.style.cssText = 'padding: 10px 20px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px; font-weight: 500;';
    analyzeBtn.disabled = !this.url;
    analyzeBtn.onclick = () => this.analyzeUrl();

    input.addEventListener('input', () => {
      analyzeBtn.disabled = !this.url;
    });
  }

  private renderAnalyzingStep() {
    const container = this.stepContainer;

    const loadingEl = container.createDiv({ cls: 'loading-indicator' });
    loadingEl.style.cssText = 'text-align: center; padding: 60px 20px;';

    const spinner = loadingEl.createEl('div', { cls: 'spinner' });
    spinner.style.cssText = 'margin: 0 auto 20px; width: 50px; height: 50px; border: 4px solid var(--background-modifier-border); border-top-color: var(--interactive-accent); border-radius: 50%; animation: spin 1s linear infinite;';

    loadingEl.createEl('p', { text: 'Analyzing page structure...' });
    loadingEl.createEl('p', {
      text: 'This may take 10-30 seconds',
      cls: 'text-muted'
    }).style.fontSize = '12px';

    // Add CSS animation
    const style = document.createElement('style');
    style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
    container.appendChild(style);
  }

  private async analyzeUrl() {
    if (!this.url) return;

    this.currentStep = 'analyzing';
    this.onOpen(); // Re-render

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/api/workflows/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: this.url })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Analysis failed');
      }

      this.analysisResult = await response.json();
      this.currentStep = 'review';
      this.onOpen();
    } catch (error) {
      new Notice(`❌ Analysis failed: ${error.message}`);
      this.currentStep = 'input';
      this.onOpen();
    }
  }

  private renderReviewStep() {
    if (!this.analysisResult) return;

    const container = this.stepContainer;
    const result = this.analysisResult;

    // Confidence badge
    const confidenceBadge = container.createDiv({ cls: 'confidence-badge' });
    const confLevel = result.confidence >= 0.8 ? 'high' : result.confidence >= 0.6 ? 'medium' : 'low';
    const confColor = confLevel === 'high' ? '#4caf50' : confLevel === 'medium' ? '#ff9800' : '#f44336';
    const confIcon = confLevel === 'high' ? '🟢' : confLevel === 'medium' ? '🟡' : '🔴';

    confidenceBadge.innerHTML = `
      <div style="display: inline-block; padding: 8px 16px; background: ${confColor}22; border: 2px solid ${confColor}; border-radius: 6px; margin-bottom: 15px;">
        <strong>${confIcon} ${confLevel.toUpperCase()} CONFIDENCE</strong> (${(result.confidence * 100).toFixed(0)}%)
      </div>
    `;

    // Summary stats
    const stats = container.createDiv({ cls: 'stats' });
    stats.style.cssText = 'display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px;';

    [
      { label: 'Page Type', value: result.page_type },
      { label: 'Articles Found', value: result.total_articles_found.toString() },
      { label: 'Fields', value: Object.keys(result.selectors).length.toString() },
      { label: 'Pagination', value: result.pagination_selector ? 'Yes' : 'No' }
    ].forEach(stat => {
      const statEl = stats.createDiv();
      statEl.style.cssText = 'padding: 10px; background: var(--background-secondary); border-radius: 4px;';
      statEl.createEl('div', { text: stat.label, cls: 'text-muted' }).style.fontSize = '11px';
      statEl.createEl('div', { text: stat.value }).style.cssText = 'font-weight: 600; margin-top: 4px;';
    });

    // Detected fields
    const fieldsEl = container.createDiv();
    fieldsEl.style.cssText = 'margin: 15px 0;';
    fieldsEl.createEl('strong', { text: 'Fields Detected: ' });
    fieldsEl.createEl('span', { text: Object.keys(result.selectors).join(', ') });

    // Search filters
    if (result.search_filters.length > 0) {
      const filtersEl = container.createDiv();
      filtersEl.style.cssText = 'margin: 15px 0; padding: 10px; background: var(--background-secondary); border-radius: 4px;';
      filtersEl.createEl('strong', { text: `🔍 Search/Filter Elements: ${result.search_filters.length}` });
      const filterList = filtersEl.createEl('ul');
      filterList.style.cssText = 'margin: 5px 0 0 20px; font-size: 12px;';
      result.search_filters.forEach(f => {
        filterList.createEl('li', { text: `${f.element_type}: ${f.description || 'detected'}` });
      });
    }

    // Sample articles table
    container.createEl('h4', { text: 'Sample Articles:' }).style.cssText = 'margin-top: 20px;';
    const table = container.createEl('table');
    table.style.cssText = 'width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 15px;';

    const thead = table.createEl('thead');
    const headerRow = thead.createEl('tr');
    ['Title', 'Authors', 'URL'].forEach(header => {
      const th = headerRow.createEl('th', { text: header });
      th.style.cssText = 'text-align: left; padding: 8px; border-bottom: 2px solid var(--background-modifier-border); background: var(--background-secondary);';
    });

    const tbody = table.createEl('tbody');
    result.sample_articles.slice(0, 5).forEach((article, idx) => {
      const row = tbody.createEl('tr');
      row.style.cssText = idx % 2 === 0 ? 'background: var(--background-primary);' : 'background: var(--background-secondary-alt);';

      // Title
      const titleCell = row.createEl('td');
      titleCell.style.cssText = 'padding: 8px; border-bottom: 1px solid var(--background-modifier-border);';
      titleCell.textContent = article.title ? (article.title.length > 60 ? article.title.substring(0, 60) + '...' : article.title) : '(no title)';

      // Authors
      const authorsCell = row.createEl('td');
      authorsCell.style.cssText = 'padding: 8px; border-bottom: 1px solid var(--background-modifier-border);';
      const authors = Array.isArray(article.authors) ? article.authors : (article.authors ? [article.authors] : []);
      authorsCell.textContent = authors.length > 0 ? authors.slice(0, 2).join(', ') + (authors.length > 2 ? '...' : '') : '(no authors)';

      // URL
      const urlCell = row.createEl('td');
      urlCell.style.cssText = 'padding: 8px; border-bottom: 1px solid var(--background-modifier-border);';
      if (article.url) {
        const link = urlCell.createEl('a', { text: '🔗', href: article.url });
        link.setAttribute('target', '_blank');
      } else {
        urlCell.textContent = '(no URL)';
      }
    });

    // Notes
    if (result.notes) {
      const notesEl = container.createDiv();
      notesEl.style.cssText = 'margin: 15px 0; padding: 10px; background: var(--background-secondary); border-radius: 4px; font-size: 12px;';
      notesEl.createEl('strong', { text: 'Notes: ' });
      notesEl.createEl('span', { text: result.notes });
    }

    // Warning for low confidence
    if (result.confidence < 0.6) {
      const warning = container.createDiv();
      warning.style.cssText = 'margin: 15px 0; padding: 12px; background: #f4433622; border: 1px solid #f44336; border-radius: 4px; font-size: 13px;';
      warning.innerHTML = '⚠️ <strong>Low confidence detected.</strong> The page structure may be unusual. Consider trying a different page on this site, or provide feedback to refine the selectors.';
    }

    // Buttons
    const buttonContainer = container.createDiv();
    buttonContainer.style.cssText = 'display: flex; justify-content: space-between; gap: 10px; margin-top: 30px;';

    const leftButtons = buttonContainer.createDiv();
    leftButtons.style.cssText = 'display: flex; gap: 10px;';

    const backBtn = leftButtons.createEl('button', { text: '← Back' });
    backBtn.style.cssText = 'padding: 10px 20px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    backBtn.onclick = () => {
      this.currentStep = 'input';
      this.onOpen();
    };

    const refineBtn = leftButtons.createEl('button', { text: '✏️ Something\'s Wrong' });
    refineBtn.style.cssText = 'padding: 10px 20px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
    refineBtn.onclick = () => this.promptForRefinement();

    const confirmBtn = buttonContainer.createEl('button', { text: '✓ Looks Good, Save' });
    confirmBtn.style.cssText = 'padding: 10px 20px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px; font-weight: 500;';
    confirmBtn.onclick = () => this.promptForName();
  }

  private async promptForRefinement() {
    const feedback = await this.showInputModal('What\'s incorrect?', 'Describe what\'s wrong (e.g., "The titles are cut off", "These aren\'t papers")', true);

    if (!feedback) return;

    this.currentStep = 'refining';
    this.onOpen();

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/api/workflows/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: this.url,
          current_selectors: {
            _container: this.analysisResult!.article_container_selector,
            ...this.analysisResult!.selectors
          },
          user_feedback: feedback
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Refinement failed');
      }

      this.analysisResult = await response.json();
      this.currentStep = 'review';
      this.onOpen();
    } catch (error) {
      new Notice(`❌ Refinement failed: ${error.message}`);
      this.currentStep = 'review';
      this.onOpen();
    }
  }

  private renderRefiningStep() {
    const container = this.stepContainer;

    const loadingEl = container.createDiv({ cls: 'loading-indicator' });
    loadingEl.style.cssText = 'text-align: center; padding: 60px 20px;';

    const spinner = loadingEl.createEl('div', { cls: 'spinner' });
    spinner.style.cssText = 'margin: 0 auto 20px; width: 50px; height: 50px; border: 4px solid var(--background-modifier-border); border-top-color: var(--interactive-accent); border-radius: 50%; animation: spin 1s linear infinite;';

    loadingEl.createEl('p', { text: 'Refining selectors based on your feedback...' });
  }

  private async promptForName() {
    const name = await this.showInputModal(
      'Name this source',
      'Enter a unique name (e.g., "nber_working_papers", "nature_neuroscience")'
    );

    if (!name) return;

    // Validate name (lowercase, underscores/hyphens only)
    if (!/^[a-z0-9_-]+$/.test(name)) {
      new Notice('❌ Name must be lowercase letters, numbers, underscores, or hyphens only');
      return this.promptForName();
    }

    await this.confirmWorkflow(name);
  }

  private async confirmWorkflow(name: string) {
    if (!this.analysisResult) return;

    this.currentStep = 'saving';
    this.onOpen();

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/api/workflows/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: this.url,
          name: name,
          article_container_selector: this.analysisResult.article_container_selector,
          selectors: this.analysisResult.selectors,
          pagination_selector: this.analysisResult.pagination_selector,
          search_filters: this.analysisResult.search_filters,
          max_articles_per_run: 100
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save workflow');
      }

      const result = await response.json();
      this.currentStep = 'success';
      this.onOpen();
    } catch (error) {
      new Notice(`❌ Save failed: ${error.message}`);
      this.currentStep = 'review';
      this.onOpen();
    }
  }

  private renderSavingStep() {
    const container = this.stepContainer;

    const loadingEl = container.createDiv({ cls: 'loading-indicator' });
    loadingEl.style.cssText = 'text-align: center; padding: 60px 20px;';

    const spinner = loadingEl.createEl('div', { cls: 'spinner' });
    spinner.style.cssText = 'margin: 0 auto 20px; width: 50px; height: 50px; border: 4px solid var(--background-modifier-border); border-top-color: var(--interactive-accent); border-radius: 50%; animation: spin 1s linear infinite;';

    loadingEl.createEl('p', { text: 'Saving workflow...' });
  }

  private renderSuccessStep() {
    const container = this.stepContainer;

    const successEl = container.createDiv({ cls: 'success-message' });
    successEl.style.cssText = 'text-align: center; padding: 40px 20px;';

    successEl.createEl('div', { text: '✅' }).style.cssText = 'font-size: 64px; margin-bottom: 20px;';
    successEl.createEl('h3', { text: 'Custom Source Created!' });
    successEl.createEl('p', {
      text: 'This source is now active and will be included in discovery runs.'
    }).style.cssText = 'margin: 15px 0; color: var(--text-muted);';

    const infoBox = successEl.createDiv();
    infoBox.style.cssText = 'margin: 20px auto; padding: 15px; background: var(--background-secondary); border-radius: 4px; max-width: 500px; text-align: left;';
    infoBox.createEl('strong', { text: 'What happens next:' });
    const list = infoBox.createEl('ul');
    list.style.cssText = 'margin: 10px 0 0 20px; font-size: 13px;';
    [
      'Add this source to a research question\'s selected_sources list',
      'Or use ["*"] to query all sources including this one',
      'Keywords from your research question will be typed into the search box',
      'Articles will be extracted, paginated, and deduplicated automatically'
    ].forEach(item => {
      list.createEl('li', { text: item });
    });

    const closeBtn = successEl.createEl('button', { text: 'Close' });
    closeBtn.style.cssText = 'margin-top: 30px; padding: 10px 30px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px; font-weight: 500;';
    closeBtn.onclick = () => this.close();
  }

  private showInputModal(title: string, placeholder: string, multiline: boolean = false): Promise<string | null> {
    return new Promise((resolve) => {
      const modal = new Modal(this.app);

      modal.onOpen = () => {
        const { contentEl } = modal;
        contentEl.empty();

        contentEl.createEl('h3', { text: title });

        let inputEl: HTMLInputElement | HTMLTextAreaElement;
        if (multiline) {
          inputEl = contentEl.createEl('textarea', { placeholder });
          inputEl.style.cssText = 'width: 100%; min-height: 80px; padding: 8px; margin: 10px 0; border: 1px solid var(--background-modifier-border); border-radius: 4px; resize: vertical;';
        } else {
          inputEl = contentEl.createEl('input', { type: 'text', placeholder });
          inputEl.style.cssText = 'width: 100%; padding: 8px; margin: 10px 0; border: 1px solid var(--background-modifier-border); border-radius: 4px;';
        }
        inputEl.focus();

        const buttonContainer = contentEl.createEl('div');
        buttonContainer.style.cssText = 'display: flex; justify-content: flex-end; gap: 10px; margin-top: 15px;';

        const cancelBtn = buttonContainer.createEl('button', { text: 'Cancel' });
        cancelBtn.style.cssText = 'padding: 8px 16px; border: 1px solid var(--background-modifier-border); background: var(--background-secondary); border-radius: 4px;';
        cancelBtn.onclick = () => {
          resolve(null);
          modal.close();
        };

        const okBtn = buttonContainer.createEl('button', { text: 'OK' });
        okBtn.style.cssText = 'padding: 8px 16px; background: var(--interactive-accent); color: var(--text-on-accent); border: none; border-radius: 4px;';
        okBtn.onclick = () => {
          resolve(inputEl.value.trim() || null);
          modal.close();
        };

        inputEl.addEventListener('keydown', (e: KeyboardEvent) => {
          if (e.key === 'Enter' && !multiline) {
            resolve(inputEl.value.trim() || null);
            modal.close();
          } else if (e.key === 'Escape') {
            resolve(null);
            modal.close();
          }
        });
      };

      modal.open();
    });
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
