/**
 * Research Tab Component
 *
 * Displays live discovery results, research questions, and browser workflows.
 * Allows users to view, rate, and download discovered papers.
 */

import { Notice } from 'obsidian';
import { InputModal } from '../modals/input-modal';
import { WorkflowBuilderModal } from '../modals/workflow-builder-modal';

export interface ResearchQuestion {
  id: string;
  name: string;
  description?: string;
  keywords: string[];
  topics: string[];
  selected_sources: string[];
  created_at: string;
  last_run_at?: string;
  total_articles?: number;
  new_articles?: number;
}

export interface MatchedArticle {
  match_id: string;
  paper_id: string;  // Changed from article_id to match backend schema
  question_id: string;
  title: string;
  authors?: string[];
  abstract?: string;
  publication_date?: string;
  journal?: string;
  venue?: string;  // Legacy field, kept for compatibility
  doi?: string;
  url?: string;
  pdf_url?: string;
  relevance_score: number;
  matched_keywords?: string[];
  matched_topics?: string[];
  matched_authors?: string[];
  discovered_via_source?: string;
  is_viewed: boolean;
  is_bookmarked: boolean;
  user_sentiment?: 'like' | 'dislike' | 'skip';
  sentiment_recorded_at?: string;
  matched_at: string;
}

export class ResearchTabComponent {
  private containerEl: HTMLElement;
  private plugin: any;
  private questions: ResearchQuestion[] = [];
  private selectedQuestion: ResearchQuestion | null = null;
  private articles: MatchedArticle[] = [];
  private allArticles: MatchedArticle[] = []; // Unfiltered copy
  private currentFilter: string = 'all';

  constructor(containerEl: HTMLElement, plugin: any) {
    this.containerEl = containerEl;
    this.plugin = plugin;
  }

  async render() {
    this.containerEl.empty();

    // Create main layout
    const researchContainer = this.containerEl.createDiv({ cls: 'thoth-research-container' });

    // Header
    const header = researchContainer.createDiv({ cls: 'thoth-research-header' });
    header.createEl('h2', { text: 'Research Dashboard', cls: 'thoth-research-title' });

    const refreshBtn = header.createEl('button', {
      text: '↻ Refresh',
      cls: 'thoth-refresh-btn'
    });
    refreshBtn.onclick = () => this.refresh();

    // Load research questions
    await this.loadResearchQuestions();

    // Questions section
    this.renderQuestionsSection(researchContainer);

    // Articles section (if question selected)
    if (this.selectedQuestion) {
      await this.loadArticles(this.selectedQuestion.id);
      this.renderArticlesSection(researchContainer);
    }
    
    // Browser Workflows section
    await this.renderBrowserWorkflowsSection(researchContainer);
    
    // Quick Actions section
    this.renderQuickActionsSection(researchContainer);
  }

  private async loadResearchQuestions() {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      console.log('[ResearchTab] Loading research questions from:', `${endpoint}/api/research/questions`);
      
      const response = await fetch(`${endpoint}/api/research/questions?limit=50&active_only=true`);
      console.log('[ResearchTab] Response status:', response.status);

      if (response.ok) {
        const data = await response.json();
        console.log('[ResearchTab] Received data:', data);
        this.questions = data.questions || [];
        console.log('[ResearchTab] Loaded questions:', this.questions.length);
      } else {
        const errorText = await response.text();
        console.error('[ResearchTab] API error:', response.status, errorText);
        new Notice(`Failed to load research questions: ${response.status}`);
      }
    } catch (error) {
      console.error('[ResearchTab] Failed to load research questions:', error);
      new Notice('Failed to load research questions');
    }
  }

  private renderQuestionsSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-questions-section' });

    // Section header
    const sectionHeader = section.createDiv({ cls: 'thoth-section-header' });
    sectionHeader.createEl('h3', { text: 'Research Questions' });

    const buttonGroup = sectionHeader.createDiv({ cls: 'thoth-button-group' });
    buttonGroup.style.cssText = 'display: flex; gap: 8px;';

    const newQuestionBtn = buttonGroup.createEl('button', {
      text: '+ New Question',
      cls: 'thoth-new-question-btn'
    });
    newQuestionBtn.onclick = () => this.createNewQuestion();

    const addSourceLink = buttonGroup.createEl('button', {
      text: '+ Add Custom Source',
      cls: 'thoth-add-source-link'
    });
    addSourceLink.style.cssText = 'padding: 6px 12px; font-size: 12px; border: 1px solid var(--background-modifier-border); background: transparent; border-radius: 4px; cursor: pointer; opacity: 0.8;';
    addSourceLink.onclick = () => {
      const modal = new WorkflowBuilderModal((this.plugin as any).app, this.plugin);
      modal.open();
    };

    // Questions list
    if (this.questions.length === 0) {
      const empty = section.createDiv({ cls: 'thoth-empty-state' });
      empty.createEl('div', { text: '🔍', cls: 'thoth-empty-icon' });
      empty.createEl('h4', { text: 'No Research Questions Yet', cls: 'thoth-empty-title' });
      empty.createEl('p', {
        text: 'Create a research question to start discovering relevant papers automatically.',
        cls: 'thoth-empty-description'
      });
    } else {
      const questionsList = section.createDiv({ cls: 'thoth-questions-list' });

      this.questions.forEach(question => {
        const card = questionsList.createDiv({
          cls: `thoth-question-card ${this.selectedQuestion?.id === question.id ? 'active' : ''}`
        });

        card.onclick = () => this.selectQuestion(question);

        // Question header
        const cardHeader = card.createDiv({ cls: 'thoth-card-header' });
        cardHeader.createEl('h4', { text: question.name, cls: 'thoth-card-title' });

        // Stats badge
        if (question.new_articles && question.new_articles > 0) {
          const badge = cardHeader.createEl('span', {
            text: `${question.new_articles} new`,
            cls: 'thoth-badge-new'
          });
        }

        // Question meta
        const meta = card.createDiv({ cls: 'thoth-card-meta' });
        
        // Keywords
        const keywordsTags = meta.createDiv({ cls: 'thoth-tags' });
        question.keywords.slice(0, 3).forEach(keyword => {
          keywordsTags.createEl('span', { text: keyword, cls: 'thoth-tag' });
        });
        if (question.keywords.length > 3) {
          keywordsTags.createEl('span', {
            text: `+${question.keywords.length - 3}`,
            cls: 'thoth-tag thoth-tag-more'
          });
        }

        // Stats
        if (question.total_articles !== undefined) {
          meta.createEl('span', {
            text: `${question.total_articles} articles`,
            cls: 'thoth-stat'
          });
        }

        // Last run
        if (question.last_run_at) {
          const timeAgo = this.getTimeAgo(new Date(question.last_run_at));
          meta.createEl('span', {
            text: `Updated ${timeAgo}`,
            cls: 'thoth-time-ago'
          });
        }
      });
    }
  }

  private async renderArticlesSection(container: HTMLElement) {
    if (!this.selectedQuestion) return;

    const section = container.createDiv({ cls: 'thoth-articles-section' });

    // Section header
    const sectionHeader = section.createDiv({ cls: 'thoth-section-header' });
    sectionHeader.createEl('h3', {
      text: `Discovered Papers: ${this.selectedQuestion.name}`
    });

    const runDiscoveryBtn = sectionHeader.createEl('button', {
      text: '▶ Run Discovery',
      cls: 'thoth-run-discovery-btn'
    });
    runDiscoveryBtn.onclick = () => this.runDiscovery(this.selectedQuestion!.id);

    // Filter tabs
    const filters = section.createDiv({ cls: 'thoth-filters' });
    
    const filterButtons = [
      { label: 'All', filter: 'all' },
      { label: 'New', filter: 'new' },
      { label: 'Liked', filter: 'liked' }
    ];

    filterButtons.forEach(({ label, filter }) => {
      const btn = filters.createEl('button', {
        text: label,
        cls: filter === this.currentFilter ? 'thoth-filter-btn active' : 'thoth-filter-btn'
      });
      btn.onclick = () => this.filterArticles(filter);
    });

    // Articles list
    const articlesList = section.createDiv({ cls: 'thoth-articles-list' });

    if (this.articles.length === 0) {
      const empty = articlesList.createDiv({ cls: 'thoth-empty-state' });
      empty.createEl('div', { text: '📄', cls: 'thoth-empty-icon' });
      empty.createEl('p', { text: 'No articles found yet. Run discovery to find papers.' });
    } else {
      this.articles.forEach(article => {
        this.renderArticleCard(articlesList, article);
      });
    }
  }

  private renderArticleCard(container: HTMLElement, article: MatchedArticle) {
    const card = container.createDiv({ cls: 'thoth-article-card' });

    // Article header
    const header = card.createDiv({ cls: 'thoth-article-header' });
    const title = header.createEl('h4', { text: article.title, cls: 'thoth-article-title' });
    title.onclick = () => this.viewArticle(article);

    // Relevance badge
    const relevancePct = Math.round(article.relevance_score * 100);
    const badge = header.createEl('span', {
      text: `${relevancePct}%`,
      cls: `thoth-relevance-badge ${relevancePct >= 80 ? 'high' : relevancePct >= 60 ? 'medium' : 'low'}`
    });

    // Article meta
    const meta = card.createDiv({ cls: 'thoth-article-meta' });

    if (article.authors && article.authors.length > 0) {
      meta.createEl('span', {
        text: article.authors.slice(0, 2).join(', ') + (article.authors.length > 2 ? ' et al.' : ''),
        cls: 'thoth-authors'
      });
    }

    if (article.publication_date) {
      const year = new Date(article.publication_date).getFullYear();
      meta.createEl('span', { text: `${year}`, cls: 'thoth-year' });
    }

    if (article.discovered_via_source) {
      meta.createEl('span', {
        text: article.discovered_via_source,
        cls: 'thoth-source'
      });
    }

    // Abstract (expandable)
    if (article.abstract) {
      const abstractText = article.abstract; // Store for closure
      const abstractContainer = card.createDiv({ cls: 'thoth-abstract-container' });
      const needsTruncation = abstractText.length > 200;

      const abstract = abstractContainer.createEl('p', {
        text: needsTruncation ? abstractText.slice(0, 200) + '...' : abstractText,
        cls: 'thoth-article-abstract'
      });

      if (needsTruncation) {
        const toggleBtn = abstractContainer.createEl('button', {
          text: 'Show more',
          cls: 'thoth-abstract-toggle'
        });

        let isExpanded = false;
        toggleBtn.onclick = (e) => {
          e.stopPropagation();
          isExpanded = !isExpanded;
          abstract.setText(isExpanded ? abstractText : abstractText.slice(0, 200) + '...');
          toggleBtn.setText(isExpanded ? 'Show less' : 'Show more');
        };
      }
    }

    // Matched keywords/topics
    if (article.matched_keywords && article.matched_keywords.length > 0) {
      const tags = card.createDiv({ cls: 'thoth-matched-tags' });
      article.matched_keywords.forEach(keyword => {
        tags.createEl('span', { text: keyword, cls: 'thoth-tag thoth-tag-matched' });
      });
    }

    // Actions
    const actions = card.createDiv({ cls: 'thoth-article-actions' });

    // Download button - only show if PDF URL exists
    if (article.pdf_url) {
      const downloadBtn = actions.createEl('button', {
        text: '⬇ PDF',
        cls: 'thoth-action-btn'
      });
      downloadBtn.onclick = () => this.downloadArticle(article);
    }

    // View button - opens article URL
    const viewBtn = actions.createEl('button', {
      text: '👁 View',
      cls: `thoth-action-btn ${article.is_viewed ? 'active' : ''}`
    });
    viewBtn.onclick = () => this.viewArticle(article);

    // Rating buttons
    const ratingGroup = actions.createDiv({ cls: 'thoth-rating-group' });

    const likeBtn = ratingGroup.createEl('button', {
      text: '👍',
      cls: `thoth-rating-btn ${article.user_sentiment === 'like' ? 'active' : ''}`
    });
    likeBtn.onclick = () => this.rateArticle(article, 'like');

    const dislikeBtn = ratingGroup.createEl('button', {
      text: '👎',
      cls: `thoth-rating-btn ${article.user_sentiment === 'dislike' ? 'active' : ''}`
    });
    dislikeBtn.onclick = () => this.rateArticle(article, 'dislike');
  }

  private async loadArticles(questionId: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      console.log('[ResearchTab] Loading articles for question:', questionId);
      
      const response = await fetch(
        `${endpoint}/api/research/questions/${questionId}/articles?limit=50`
      );
      console.log('[ResearchTab] Articles response status:', response.status);

      if (response.ok) {
        const data = await response.json();
        console.log('[ResearchTab] Received articles data:', data);
        this.allArticles = data.matches || [];
        this.articles = [...this.allArticles]; // Create filtered copy
        this.currentFilter = 'all'; // Reset filter
        console.log('[ResearchTab] Loaded articles:', this.articles.length);
      } else {
        const errorText = await response.text();
        console.error('[ResearchTab] Articles API error:', response.status, errorText);
      }
    } catch (error) {
      console.error('[ResearchTab] Failed to load articles:', error);
      new Notice('Failed to load articles');
    }
  }

  private async selectQuestion(question: ResearchQuestion) {
    this.selectedQuestion = question;
    await this.render();
  }

  private async rateArticle(article: MatchedArticle, sentiment: 'like' | 'dislike' | 'skip') {
    if (!this.selectedQuestion) {
      console.error('[ResearchTab] Cannot rate article: no question selected');
      new Notice('Please select a research question first');
      return;
    }

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const questionId = this.selectedQuestion.id;
      const matchId = article.match_id;
      
      console.log('[ResearchTab] Rating article:', {
        questionId,
        matchId,
        sentiment,
        articleTitle: article.title
      });
      
      const response = await fetch(
        `${endpoint}/api/research/questions/${questionId}/articles/${matchId}/sentiment`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sentiment })
        }
      );

      console.log('[ResearchTab] Rating response status:', response.status);

      if (response.ok) {
        const updatedArticle = await response.json();
        console.log('[ResearchTab] Article rated successfully:', updatedArticle);
        article.user_sentiment = sentiment;
        await this.render();
        new Notice(`Marked as ${sentiment}`);
      } else {
        const errorText = await response.text();
        console.error('[ResearchTab] Rating API error:', response.status, errorText);
        let errorMessage = 'Failed to rate article';
        try {
          const errorJson = JSON.parse(errorText);
          if (errorJson.detail) {
            errorMessage = errorJson.detail;
          }
        } catch {
          // Use default error message
        }
        new Notice(errorMessage);
      }
    } catch (error) {
      console.error('[ResearchTab] Error rating article:', error);
      new Notice('Failed to rate article - network error');
    }
  }

  private async toggleViewed(article: MatchedArticle) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const newValue = !article.is_viewed;

      const response = await fetch(
        `${endpoint}/api/research/questions/${this.selectedQuestion!.id}/articles/${article.match_id}/status`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_viewed: newValue })
        }
      );

      if (response.ok) {
        article.is_viewed = newValue;
        await this.render();
      } else {
        throw new Error('Failed to update status');
      }
    } catch (error) {
      console.error('Error updating viewed status:', error);
      new Notice('Failed to update status');
    }
  }

  private async toggleBookmark(article: MatchedArticle) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const newValue = !article.is_bookmarked;

      const response = await fetch(
        `${endpoint}/api/research/questions/${this.selectedQuestion!.id}/articles/${article.match_id}/status`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_bookmarked: newValue })
        }
      );

      if (response.ok) {
        article.is_bookmarked = newValue;
        await this.render();
        new Notice(newValue ? 'Bookmarked' : 'Removed bookmark');
      } else {
        throw new Error('Failed to update bookmark');
      }
    } catch (error) {
      console.error('Error updating bookmark:', error);
      new Notice('Failed to update bookmark');
    }
  }

  private async saveArticle(article: MatchedArticle) {
    try {
      if (!article.pdf_url) {
        new Notice('No PDF URL available for this article');
        return;
      }

      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(
        `${endpoint}/api/research/questions/${this.selectedQuestion!.id}/articles/${article.match_id}/download`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        }
      );

      if (response.ok) {
        const result = await response.json();
        new Notice(`PDF downloaded! File monitor will process automatically.`);

        // Update local state
        article.is_bookmarked = true;
        article.is_viewed = true;
        await this.render();

        console.log('Download result:', result);
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to download');
      }
    } catch (error) {
      console.error('Error saving article:', error);
      new Notice(`Failed to save article: ${error.message}`);
    }
  }

  private async downloadArticle(article: MatchedArticle) {
    // Alias to saveArticle for backward compatibility with PDF button
    await this.saveArticle(article);
  }

  private async viewArticle(article: MatchedArticle) {
    // Mark as viewed
    if (!article.is_viewed) {
      await this.toggleViewed(article);
    }

    // Open external URL (Electron-safe using require)
    const url = article.doi ? `https://doi.org/${article.doi}` : article.pdf_url;

    if (url) {
      try {
        // Use electron shell to open external links safely
        require('electron').shell.openExternal(url);
      } catch (error) {
        // Fallback for non-electron environments
        console.warn('electron.shell not available, using window.open');
        window.open(url, '_blank');
      }
    } else {
      new Notice('No URL available for this article');
    }
  }

  private async runDiscovery(questionId: string) {
    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(
        `${endpoint}/api/research/questions/${questionId}/run`,
        { method: 'POST' }
      );

      if (response.ok) {
        new Notice('Discovery started - check back in a few minutes');
        setTimeout(() => this.refresh(), 3000);
      } else {
        throw new Error('Failed to run discovery');
      }
    } catch (error) {
      console.error('Error running discovery:', error);
      new Notice('Failed to run discovery');
    }
  }

  private async createNewQuestion() {
    // Use InputModal instead of prompt() (Electron-compatible)
    const name = await new Promise<string | null>((resolve) => {
      new InputModal((this.plugin as any).app, 'Enter research question name:', resolve).open();
    });
    if (!name) return;

    const keywords = await new Promise<string | null>((resolve) => {
      new InputModal((this.plugin as any).app, 'Enter keywords (comma-separated):', resolve).open();
    });
    if (!keywords) return;

    const keywordsList = keywords.split(',').map(k => k.trim()).filter(k => k);

    try {
      const endpoint = this.plugin.getEndpointUrl();
      const response = await fetch(`${endpoint}/api/research/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          keywords: keywordsList,
          topics: [],
          authors: [],
          selected_sources: ['*'], // All sources
          schedule_frequency: 'on-demand',
          min_relevance_score: 0.5,
          auto_download_pdfs: false,
          auto_process_pdfs: false,
          max_articles_per_run: 50
        })
      });

      if (response.ok) {
        new Notice('Research question created!');
        await this.refresh();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create question');
      }
    } catch (error) {
      console.error('Error creating research question:', error);
      new Notice(`Failed to create research question: ${error.message}`);
    }
  }

  private async filterArticles(filter: string) {
    this.currentFilter = filter;
    
    // Apply filter starting from all articles
    let filtered = [...this.allArticles];

    switch (filter) {
      case 'new':
        filtered = filtered.filter(a => !a.is_viewed);
        break;
      case 'liked':
        filtered = filtered.filter(a => a.user_sentiment === 'like');
        break;
      case 'all':
      default:
        // Show all articles
        break;
    }

    this.articles = filtered;
    await this.render();
  }

  private async refresh() {
    await this.render();
    new Notice('Refreshed');
  }

  private getTimeAgo(date: Date): string {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
    
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    
    return date.toLocaleDateString();
  }

  // Browser Workflows Section
  private async renderBrowserWorkflowsSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-workflows-section' });
    
    const sectionHeader = section.createDiv({ cls: 'thoth-section-header' });
    sectionHeader.createEl('h3', { text: '🌐 Browser Workflows' });
    
    const createBtn = sectionHeader.createEl('button', {
      text: '+ Create Workflow',
      cls: 'thoth-create-btn'
    });
    
    createBtn.onclick = () => {
      const modal = new WorkflowBuilderModal((this.plugin as any).app, this.plugin);
      modal.open();
    };
    
    // Workflows list
    const workflowsList = section.createDiv({ cls: 'thoth-workflows-list' });
    
    try {
      const endpoint = (this.plugin as any).getEndpointUrl();
      const response = await fetch(`${endpoint}/api/workflows`);
      
      if (response.ok) {
        const workflows = await response.json();
        
        if (workflows.length === 0) {
          const empty = workflowsList.createDiv({ cls: 'thoth-empty-state-small' });
          empty.createEl('p', { 
            text: 'No browser workflows yet. Create one to automate paper discovery from custom sources.',
            cls: 'thoth-empty-text' 
          });
        } else {
          workflows.forEach((workflow: any) => {
            this.renderWorkflowCard(workflowsList, workflow);
          });
        }
      }
    } catch (error) {
      workflowsList.createEl('p', {
        text: 'Unable to load workflows',
        cls: 'thoth-error-text'
      });
    }
  }

  private renderWorkflowCard(container: HTMLElement, workflow: any) {
    const card = container.createDiv({ cls: 'thoth-workflow-card' });
    
    const header = card.createDiv({ cls: 'thoth-workflow-header' });
    header.createEl('span', { 
      text: workflow.name || 'Unnamed Workflow',
      cls: 'thoth-workflow-name'
    });
    
    const status = header.createEl('span', {
      cls: `thoth-workflow-status ${workflow.is_active ? 'active' : 'inactive'}`
    });
    status.setText(workflow.is_active ? '● Active' : '○ Inactive');
    
    if (workflow.schedule) {
      card.createEl('p', { 
        text: `Schedule: ${workflow.schedule}`,
        cls: 'thoth-workflow-schedule'
      });
    }
    
    const actions = card.createDiv({ cls: 'thoth-workflow-actions' });
    
    const runBtn = actions.createEl('button', {
      text: '▶ Run',
      cls: 'thoth-workflow-run-btn'
    });
    
    runBtn.onclick = async () => {
      try {
        const endpoint = (this.plugin as any).getEndpointUrl();
        await fetch(`${endpoint}/api/workflows/${workflow.id}/execute`, {
          method: 'POST'
        });
        new Notice(`Executing workflow: ${workflow.name}`);
      } catch (error) {
        new Notice('Failed to execute workflow');
      }
    };
  }

  // Quick Actions Section
  private renderQuickActionsSection(container: HTMLElement) {
    const section = container.createDiv({ cls: 'thoth-quick-actions-section' });
    
    const sectionHeader = section.createDiv({ cls: 'thoth-section-header' });
    sectionHeader.createEl('h3', { text: '⚡ Quick Actions' });
    
    const actionsGrid = section.createDiv({ cls: 'thoth-quick-actions-grid' });
    
    // Search Knowledge Base
    this.createQuickAction(
      actionsGrid,
      '🔍',
      'Search Knowledge Base',
      'Search your processed articles and notes',
      () => {
        new Notice('Opening knowledge base search...');
        // Could open a search modal or trigger RAG search
      }
    );
    
    // Process PDF
    this.createQuickAction(
      actionsGrid,
      '📄',
      'Process PDF',
      'Upload and process a new research paper',
      () => {
        new Notice('PDF processing UI coming soon! Drop PDFs in your vault/thoth/papers/pdfs folder.');
      }
    );
    
    // View Statistics
    this.createQuickAction(
      actionsGrid,
      '📊',
      'View Statistics',
      'See your research collection stats',
      async () => {
        try {
          const endpoint = (this.plugin as any).getEndpointUrl();
          const response = await fetch(`${endpoint}/health`);
          // Accept both 200 (healthy) and 503 (partially unhealthy but running)
          if (response.ok || response.status === 503) {
            const data = await response.json();
            const status = data.healthy ? '✓ Healthy' : '⚠ Partially Degraded';
            new Notice(`System: ${status}. Services: ${Object.keys(data.services || {}).length}`);
          } else {
            new Notice(`Unable to fetch health status (${response.status})`);
          }
        } catch (error) {
          new Notice('Unable to connect to backend');
        }
      }
    );
  }

  private createQuickAction(
    container: HTMLElement,
    icon: string,
    title: string,
    description: string,
    onClick: () => void
  ) {
    const action = container.createDiv({ cls: 'thoth-quick-action' });

    action.createEl('div', {
      text: icon,
      cls: 'thoth-action-icon'
    });

    action.createEl('div', {
      text: title,
      cls: 'thoth-action-title'
    });

    action.createEl('div', {
      text: description,
      cls: 'thoth-action-description'
    });

    action.onclick = onClick;
  }

  private async createNoteFromArticle(article: MatchedArticle) {
    try {
      // Create a note in the Research/Papers folder
      const vault = this.plugin.app.vault;
      const folderPath = 'Research/Papers';

      // Ensure folder exists
      const folder = vault.getAbstractFileByPath(folderPath);
      if (!folder) {
        await vault.createFolder(folderPath);
      }

      // Sanitize filename
      const filename = this.sanitizeFilename(article.title);
      const notePath = `${folderPath}/${filename}.md`;

      // Check if note already exists
      const existingFile = vault.getAbstractFileByPath(notePath);
      if (existingFile) {
        new Notice('Note already exists! Opening it...');
        const leaf = this.plugin.app.workspace.getLeaf(false);
        await leaf.openFile(existingFile as any);
        return;
      }

      // Build note content
      const authors = article.authors?.join(', ') || 'Unknown';
      const year = article.publication_date
        ? new Date(article.publication_date).getFullYear()
        : 'n.d.';
      const url = article.doi
        ? `https://doi.org/${article.doi}`
        : (article.pdf_url || 'No URL');

      const content = `---
title: "${article.title}"
authors: ${authors}
year: ${year}
relevance: ${Math.round(article.relevance_score * 100)}%
source: ${article.discovered_via_source || 'unknown'}
doi: ${article.doi || ''}
url: ${url}
question: ${this.selectedQuestion?.name || ''}
tags:
  - research/paper
  - from-thoth
---

# ${article.title}

## Metadata
- **Authors:** ${authors}
- **Year:** ${year}
- **Relevance:** ${Math.round(article.relevance_score * 100)}%
- **Source:** ${article.discovered_via_source || 'unknown'}
${article.doi ? `- **DOI:** [${article.doi}](https://doi.org/${article.doi})` : ''}
${article.pdf_url ? `- **PDF:** [Download](${article.pdf_url})` : ''}

## Abstract

${article.abstract || 'No abstract available.'}

## Matched Keywords

${article.matched_keywords?.map(k => `- ${k}`).join('\n') || 'None'}

## Notes

<!-- Add your reading notes here -->

---

*Generated from Thoth research question: "${this.selectedQuestion?.name}"*
`;

      // Create the note
      await vault.create(notePath, content);

      // Mark as viewed and bookmarked
      if (!article.is_viewed) {
        await this.toggleViewed(article);
      }
      if (!article.is_bookmarked) {
        await this.toggleBookmark(article);
      }

      new Notice(`Note created: ${filename}`);

      // Open the new note
      const file = vault.getAbstractFileByPath(notePath);
      if (file) {
        const leaf = this.plugin.app.workspace.getLeaf(false);
        await leaf.openFile(file as any);
      }
    } catch (error) {
      console.error('Error creating note from article:', error);
      new Notice('Failed to create note');
    }
  }

  private sanitizeFilename(title: string): string {
    // Remove invalid filename characters
    let filename = title.replace(/[<>:"/\\|?*]/g, '');
    // Replace multiple spaces with single space
    filename = filename.replace(/\s+/g, ' ');
    // Trim and limit length
    filename = filename.trim().substring(0, 100);
    return filename;
  }
}
