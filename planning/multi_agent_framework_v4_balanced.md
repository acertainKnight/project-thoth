# Thoth Multi-Agent Framework v4: Advanced Capabilities with Smart Code Reuse

> **Vision:** Implement all cutting-edge multi-agent capabilities (Phoenix pattern, dynamic agent creation, specialized research agents) while building on Thoth's existing foundation rather than duplicating it.

---

## 1. Core Philosophy: Innovation Through Composition

The key insight: **Advanced capabilities emerge from intelligent orchestration of existing services**, not from reimplementing them.

```python
# Example: A sophisticated research agent that uses existing services creatively
class AdvancedResearchAgent:
    def __init__(self, service_manager: ServiceManager):
        # Reuse ALL existing services
        self.services = service_manager
        
        # Add NEW orchestration intelligence
        self.research_planner = ResearchPlanner()
        self.hypothesis_generator = HypothesisGenerator()
        self.experiment_designer = ExperimentDesigner()
    
    async def conduct_research(self, topic: str):
        # Step 1: Use existing RAG service for initial exploration
        background = await self.services.rag.search(topic)
        
        # Step 2: NEW - Generate hypotheses using LLM service
        hypotheses = await self.hypothesis_generator.generate(
            background, 
            llm=self.services.llm  # Reuse existing LLM
        )
        
        # Step 3: Use existing discovery service to find papers
        papers = await self.services.discovery.search_arxiv(
            self._hypotheses_to_queries(hypotheses)
        )
        
        # Step 4: NEW - Design experiments based on findings
        experiments = await self.experiment_designer.design(
            hypotheses, papers, 
            processor=self.services.processing  # Reuse for analysis
        )
        
        # This is NEW capability through ORCHESTRATION, not reimplementation
```

---

## 2. Phoenix Pattern with Existing Services

### 2.1 Self-Extending Architecture Built on Current Foundation

```python
class PhoenixOrchestrator:
    """Self-modifying orchestrator that creates new agents at runtime."""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.agent_registry = {}
        self.runtime_compiler = RuntimeAgentCompiler()
        
        # Hot reload WITHOUT disrupting existing services
        self.hot_reload_enabled = True
        self.session_state = SessionStateManager()
    
    async def create_agent_dynamically(self, description: str):
        """Create new agent by composing existing services in new ways."""
        
        # Step 1: Use LLM to understand requirements
        agent_spec = await self.service_manager.llm.extract_agent_spec(description)
        
        # Step 2: Map to existing service capabilities
        capabilities = self._map_to_existing_services(agent_spec)
        
        # Step 3: Generate orchestration code (not service code!)
        orchestration_code = await self.runtime_compiler.generate_orchestrator(
            agent_spec, 
            capabilities
        )
        
        # Step 4: Hot reload the NEW orchestration logic
        new_agent = await self._hot_load_orchestrator(orchestration_code)
        
        # The agent reuses existing services but orchestrates them in new ways
        return new_agent
    
    def _map_to_existing_services(self, spec):
        """Map requirements to existing service methods."""
        capability_map = {
            "analyze_text": self.service_manager.processing.analyze_content,
            "extract_data": self.service_manager.processing.extract_text,
            "find_papers": self.service_manager.discovery.search_arxiv,
            "web_search": self.service_manager.web_search.search,
            "generate_note": self.service_manager.note.generate_note,
            "extract_citations": self.service_manager.citation.extract_citations,
        }
        
        return [capability_map[cap] for cap in spec.required_capabilities 
                if cap in capability_map]
```

### 2.2 Session State Preservation During Agent Evolution

```python
class EnhancedSessionStateManager:
    """Preserve state while allowing dynamic agent creation."""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        # Reuse existing cache service for state storage
        self.cache = service_manager.cache if hasattr(service_manager, 'cache') else None
        
    async def checkpoint_before_agent_creation(self):
        """Save state using existing services."""
        state = {
            'active_pipelines': self._get_active_pipelines(),
            'service_states': await self._capture_service_states(),
            'conversation_context': await self._get_conversation_context()
        }
        
        if self.cache:
            await self.cache.set('phoenix_checkpoint', state)
        
        return state
    
    async def restore_after_agent_creation(self, checkpoint):
        """Restore state without disrupting services."""
        # Services continue running - we just restore context
        await self._restore_conversation_context(checkpoint['conversation_context'])
        await self._restore_pipeline_states(checkpoint['active_pipelines'])
```

---

## 3. Dynamic Agent Creation Through Service Composition

### 3.1 Natural Language Agent Builder

```python
class NaturalLanguageAgentBuilder:
    """Create custom agents by intelligently composing existing services."""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.capability_mapper = ServiceCapabilityMapper(service_manager)
        self.orchestration_generator = OrchestrationGenerator()
    
    async def create_from_conversation(self, conversation: list[str]):
        """Create agent through natural language dialogue."""
        
        # Example conversation:
        # User: "I need an agent that monitors new ML papers and creates summaries"
        # System: "I'll create that by combining discovery, processing, and note services..."
        
        # Extract requirements using existing LLM service
        requirements = await self.service_manager.llm.extract_requirements(
            conversation, 
            prompt_template="agent_requirements_extraction"
        )
        
        # Map to service composition
        service_composition = {
            'monitor_papers': {
                'service': 'discovery',
                'method': 'monitor_sources',
                'config': {'sources': ['arxiv'], 'query': requirements.topic}
            },
            'process_papers': {
                'service': 'processing', 
                'method': 'analyze_content',
                'config': {'analysis_type': 'summary'}
            },
            'create_notes': {
                'service': 'note',
                'method': 'generate_note',
                'config': {'template': 'research_summary'}
            }
        }
        
        # Generate orchestration logic
        agent = await self.orchestration_generator.create_agent(
            name=requirements.agent_name,
            composition=service_composition,
            workflow=self._design_workflow(requirements)
        )
        
        return agent
```

### 3.2 Agent Templates Using Service Patterns

```python
class ResearchAgentTemplates:
    """Pre-built agent templates that showcase service composition patterns."""
    
    @staticmethod
    def literature_review_agent(service_manager: ServiceManager):
        """Systematic literature review using existing services."""
        
        class LiteratureReviewAgent:
            def __init__(self):
                self.discovery = service_manager.discovery
                self.processing = service_manager.processing
                self.citation = service_manager.citation
                self.rag = service_manager.rag
                self.note = service_manager.note
                
            async def conduct_review(self, topic: str, criteria: dict):
                # Phase 1: Discovery using existing service
                papers = await self.discovery.search_multiple_sources(
                    query=topic,
                    sources=['arxiv', 'semantic_scholar', 'pubmed'],
                    filters=criteria
                )
                
                # Phase 2: Process papers using existing pipeline
                processed = []
                for paper in papers:
                    if paper.pdf_path:
                        # Reuse entire processing pipeline
                        result = await self.processing.process_document(paper.pdf_path)
                        processed.append(result)
                
                # Phase 3: Extract citation network
                citation_graph = await self.citation.build_citation_graph(processed)
                
                # Phase 4: Identify key papers using graph analysis
                key_papers = self._analyze_citation_graph(citation_graph)
                
                # Phase 5: Generate review using existing note service
                review = await self.note.generate_note(
                    template='literature_review',
                    data={
                        'topic': topic,
                        'papers': key_papers,
                        'citation_graph': citation_graph
                    }
                )
                
                return review
        
        return LiteratureReviewAgent()
```

---

## 4. Specialized Research Agents as Advanced Orchestrators

### 4.1 Hypothesis Generation Agent

```python
class HypothesisGeneratorAgent:
    """Generate research hypotheses by creatively using existing services."""
    
    def __init__(self, service_manager: ServiceManager):
        self.llm = service_manager.llm
        self.rag = service_manager.rag
        self.discovery = service_manager.discovery
        
        # NEW: Hypothesis-specific logic
        self.hypothesis_ranker = HypothesisRanker()
        self.novelty_checker = NoveltyChecker()
    
    async def generate_hypotheses(self, research_area: str):
        # Step 1: Use RAG to find existing knowledge
        existing_knowledge = await self.rag.search(
            f"hypotheses theories {research_area}",
            top_k=20
        )
        
        # Step 2: Find recent papers using discovery
        recent_papers = await self.discovery.search_arxiv(
            query=research_area,
            sort_by='submitted_date',
            max_results=50
        )
        
        # Step 3: Generate novel hypotheses using LLM
        hypotheses = await self.llm.generate(
            prompt=self._build_hypothesis_prompt(existing_knowledge, recent_papers),
            temperature=0.8  # Higher for creativity
        )
        
        # Step 4: Check novelty against existing literature
        novel_hypotheses = []
        for hypothesis in hypotheses:
            if await self.novelty_checker.is_novel(hypothesis, existing_knowledge):
                novel_hypotheses.append(hypothesis)
        
        # Step 5: Rank by potential impact
        ranked = await self.hypothesis_ranker.rank(
            novel_hypotheses,
            criteria=['feasibility', 'impact', 'novelty']
        )
        
        return ranked
```

### 4.2 Experimental Design Agent

```python
class ExperimentDesignAgent:
    """Design experiments using existing analysis capabilities."""
    
    def __init__(self, service_manager: ServiceManager):
        self.services = service_manager
        self.experiment_planner = ExperimentPlanner()
        
    async def design_experiment(self, hypothesis: str, constraints: dict):
        # Use existing services in creative ways for experiment design
        
        # Find similar experiments in literature
        similar = await self.services.rag.search(
            f"experimental design {hypothesis}",
            filters={'type': 'methodology'}
        )
        
        # Analyze successful approaches
        approaches = await self.services.processing.analyze_content(
            similar,
            analysis_type='methodology_extraction'
        )
        
        # Generate experiment design
        design = await self.experiment_planner.create_design(
            hypothesis=hypothesis,
            approaches=approaches,
            constraints=constraints,
            llm=self.services.llm  # Use existing LLM for generation
        )
        
        return design
```

---

## 5. Collaborative Agent Networks Using Existing Infrastructure

### 5.1 Knowledge Sharing via Enhanced Citation Graph

```python
class CollaborativeKnowledgeNetwork:
    """Agents share knowledge through existing citation graph infrastructure."""
    
    def __init__(self, service_manager: ServiceManager):
        # Reuse existing citation graph as knowledge backbone
        self.citation_graph = service_manager.citation.get_graph()
        self.rag = service_manager.rag
        
        # NEW: Agent collaboration layer
        self.agent_discoveries = {}
        self.collaboration_protocol = CollaborationProtocol()
    
    async def share_discovery(self, agent_id: str, discovery: dict):
        """Share agent discoveries through existing graph."""
        
        # Add to citation graph with agent metadata
        node_id = await self.citation_graph.add_node(
            title=discovery['title'],
            content=discovery['content'],
            metadata={'agent_id': agent_id, 'type': 'agent_discovery'}
        )
        
        # Index in RAG for other agents to find
        await self.rag.index_document(
            content=discovery['content'],
            metadata={
                'source': f'agent_{agent_id}',
                'discovery_type': discovery['type'],
                'timestamp': discovery['timestamp']
            }
        )
        
        # Notify interested agents
        await self._notify_relevant_agents(discovery)
```

### 5.2 Multi-Agent Research Protocol

```python
class MultiAgentResearchProtocol:
    """Coordinate multiple specialized agents for complex research."""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        
        # Create specialized agents from templates
        self.agents = {
            'literature': LiteratureReviewAgent(service_manager),
            'hypothesis': HypothesisGeneratorAgent(service_manager),
            'experiment': ExperimentDesignAgent(service_manager),
            'analysis': DataAnalysisAgent(service_manager),
            'synthesis': SynthesisAgent(service_manager)
        }
        
        # Reuse existing pipeline for coordination
        self.pipeline = service_manager.pipeline
        
    async def conduct_research(self, research_question: str):
        """Orchestrate multi-agent research process."""
        
        # Phase 1: Literature Review
        literature = await self.agents['literature'].conduct_review(
            research_question
        )
        
        # Phase 2: Hypothesis Generation based on gaps
        hypotheses = await self.agents['hypothesis'].generate_from_gaps(
            literature.identified_gaps
        )
        
        # Phase 3: Experimental Design for top hypotheses
        experiments = []
        for hypothesis in hypotheses[:3]:  # Top 3
            design = await self.agents['experiment'].design(hypothesis)
            experiments.append(design)
        
        # Phase 4: Analysis planning
        analysis_plan = await self.agents['analysis'].plan_analyses(
            experiments
        )
        
        # Phase 5: Synthesis of research plan
        research_plan = await self.agents['synthesis'].create_plan(
            question=research_question,
            literature=literature,
            hypotheses=hypotheses,
            experiments=experiments,
            analyses=analysis_plan
        )
        
        return research_plan
```

---

## 6. Implementation Strategy: Phased Enhancement

### Phase 1: Foundation (Week 1-2)
1. Create `ServiceAgentAdapter` for wrapping existing services
2. Implement `PhoenixOrchestrator` with hot reload capability
3. Add event emission to existing pipeline (minimal change)

### Phase 2: Dynamic Creation (Week 3-4)
1. Build `NaturalLanguageAgentBuilder` using LLM service
2. Create agent templates demonstrating service composition
3. Implement runtime agent compilation

### Phase 3: Specialized Agents (Week 5-6)
1. Implement research agent templates
2. Create collaboration protocol using citation graph
3. Build multi-agent research workflows

### Phase 4: Advanced Features (Week 7-8)
1. Add self-modification capabilities
2. Implement agent learning from outcomes
3. Create agent marketplace

---

## 7. Key Advantages of This Balanced Approach

1. **Full Innovation**: All cutting-edge features (Phoenix, dynamic creation, specialized agents)
2. **Maximum Reuse**: 80% existing code, 20% new orchestration
3. **No Redundancy**: Services aren't reimplemented, just orchestrated creatively
4. **Immediate Power**: Advanced capabilities from day one
5. **Maintainability**: Clear separation between services (stable) and orchestration (innovative)

---

## Conclusion

This balanced approach delivers all the advanced multi-agent capabilities while respecting and building upon Thoth's existing architecture. The key insight is that **innovation comes from creative orchestration of existing capabilities**, not from reimplementing them. 

By treating existing services as a rich palette of capabilities that can be combined in infinite ways, we create a system that is both cutting-edge and maintainable, showcasing the best of AI innovation and engineering excellence.