/**
 * Thoth-themed thinking verbs for status messages.
 * Inspired by Letta Code's thinkingMessages.ts, customized for Thoth's
 * academic/research focus as the Egyptian god of knowledge and writing.
 */

// General thinking verbs (from Letta + custom)
const THINKING_VERBS = [
  // Classic thinking
  'thinking',
  'pondering',
  'considering',
  'contemplating',
  'reflecting',
  'deliberating',
  'cogitating',
  'ruminating',
  'musing',

  // Processing/Computing
  'processing',
  'computing',
  'calculating',
  'analyzing',
  'synthesizing',
  'evaluating',
  'assessing',

  // Reasoning
  'reasoning',
  'inferring',
  'deducing',
  'interpreting',
  'formulating',

  // Strategy/Planning
  'strategizing',
  'orchestrating',
  'optimizing',
  'calibrating',

  // Technical
  'indexing',
  'compiling',
  'rendering',
  'executing',
  'initializing',

  // Learning/Memory (Thoth-themed)
  'learning',
  'adapting',
  'evolving',
  'remembering',
  'absorbing',
  'internalizing',
  'recalling',

  // Academic/Research (Thoth-specific)
  'researching',
  'investigating',
  'examining',
  'studying',
  'exploring',
  'discovering',
  'uncovering',
  'deciphering',
  'translating',
  'annotating',
  'cross-referencing',
  'cataloguing',
  'archiving',

  // Scholarly
  'consulting the scrolls',
  'perusing the archives',
  'reviewing the literature',
  'gathering knowledge',
  'seeking wisdom',

  // Fun/Playful
  'spinning',
  'focusing',
  'machinating',
  'metathinking',
  'thinking about thinking',
  'connecting the dots',
  'brewing ideas',
  'hatching a plan',
] as const;

// Tool-specific action verbs
const TOOL_VERBS = [
  'searching',
  'looking through',
  'consulting',
  'checking',
  'browsing',
  'scanning',
  'querying',
  'fetching',
  'retrieving',
  'exploring',
  'investigating',
  'probing',
  'examining',
  'inspecting',
  'surveying',
  'sifting through',
  'combing through',
  'diving into',
  'rifling through',
  'perusing',
] as const;

// Processing/results verbs
const PROCESSING_VERBS = [
  'processing',
  'analyzing',
  'reviewing',
  'examining',
  'digesting',
  'parsing',
  'interpreting',
  'synthesizing',
  'compiling',
  'distilling',
  'extracting insights from',
  'making sense of',
  'piecing together',
  'organizing',
  'structuring',
] as const;

export type ThinkingType = 'thinking' | 'tool' | 'processing';

/**
 * Get a random thinking phrase based on context type.
 */
export function getRandomThinkingPhrase(type: ThinkingType): string {
  let verbs: readonly string[];

  switch (type) {
    case 'thinking':
      verbs = THINKING_VERBS;
      break;
    case 'tool':
      verbs = TOOL_VERBS;
      break;
    case 'processing':
      verbs = PROCESSING_VERBS;
      break;
  }

  const verb = verbs[Math.floor(Math.random() * verbs.length)];
  // Capitalize first letter
  return verb.charAt(0).toUpperCase() + verb.slice(1);
}

/**
 * Tool name mappings for human-readable display.
 * Maps internal tool names to friendly descriptions.
 */
const TOOL_NAME_MAP: Record<string, string> = {
  // Document/Search tools
  'search_documents': 'your documents',
  'search_notes': 'your notes',
  'semantic_search': 'related content',
  'query_knowledge_base': 'the knowledge base',
  'query_knowledge': 'the knowledge base',
  'rag_search': 'the research library',
  'vector_search': 'semantic matches',

  // File operations
  'read_file': 'a file',
  'read': 'a file',
  'write_file': 'a file',
  'write': 'a file',
  'get_document_content': 'document content',
  'get_pdf_content': 'PDF content',

  // Web/External
  'web_search': 'the web',
  'fetch_url': 'a webpage',
  'fetch_webpage': 'a webpage',

  // Research-specific
  'search_openalex': 'OpenAlex',
  'search_semantic_scholar': 'Semantic Scholar',
  'search_crossref': 'Crossref',
  'get_citations': 'citations',
  'get_references': 'references',
  'find_related_papers': 'related papers',
  'discover_articles': 'new articles',
  'agentic_research_question': 'your research library (agentic)',
  'answer_research_question': 'your research library',

  // Analysis
  'analyze_document': 'a document',
  'extract_metadata': 'metadata',
  'generate_summary': 'a summary',
  'extract_key_findings': 'key findings',

  // Tags/Organization
  'get_tags': 'tags',
  'add_tag': 'tags',
  'search_by_tag': 'tagged items',

  // Memory/Context
  'memory': 'memory',
  'recall': 'memories',
  'remember': 'context',
};

/**
 * Convert internal tool names to human-readable descriptions.
 */
export function getHumanReadableToolName(toolName: string): string {
  // Check direct mapping
  if (TOOL_NAME_MAP[toolName]) {
    return TOOL_NAME_MAP[toolName];
  }

  // Check lowercase version
  const lowerName = toolName.toLowerCase();
  if (TOOL_NAME_MAP[lowerName]) {
    return TOOL_NAME_MAP[lowerName];
  }

  // Fallback: convert snake_case/camelCase to readable format
  return toolName
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .toLowerCase();
}

/**
 * Get a complete status message for a tool call.
 * Returns something like "Searching your documents..."
 */
export function getToolStatusMessage(toolName: string): string {
  const verb = getRandomThinkingPhrase('tool');
  const target = getHumanReadableToolName(toolName);
  return `${verb} ${target}`;
}

/**
 * Agentic retrieval step icons for UI display.
 * Maps retrieval step names to emoji icons.
 */
export const RETRIEVAL_STEP_ICONS: Record<string, string> = {
  classify: '🔍',
  expand: '🔎',
  decompose: '✂️',
  extract_filters: '🏷️',
  retrieve: '📚',
  grade: '📊',
  rewrite: '✏️',
  rerank: '🏆',
  generate: '💡',
  hallucination_check: '✅',
};

/**
 * Human-readable messages for agentic retrieval steps.
 * These are displayed to users during the retrieval process.
 */
export const RETRIEVAL_STEP_MESSAGES: Record<string, string> = {
  classify: 'Analyzing your question',
  expand: 'Expanding search terms',
  decompose: 'Breaking down into sub-questions',
  extract_filters: 'Extracting search filters',
  retrieve: 'Searching your knowledge base',
  grade: 'Evaluating relevance',
  rewrite: 'Refining search strategy',
  rerank: 'Ranking best results',
  generate: 'Composing answer',
  hallucination_check: 'Verifying accuracy',
};

/**
 * Get icon for a retrieval step.
 */
export function getRetrievalStepIcon(step: string): string {
  return RETRIEVAL_STEP_ICONS[step] || '⚙️';
}

/**
 * Get message for a retrieval step.
 */
export function getRetrievalStepMessage(step: string): string {
  return RETRIEVAL_STEP_MESSAGES[step] || step.replace(/_/g, ' ');
}
