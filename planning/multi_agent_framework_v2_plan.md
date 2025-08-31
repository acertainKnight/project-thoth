# Thoth Multi-Agent Framework v2: Cutting-Edge Autonomous Research Assistant

> **Vision:** Transform Thoth into a state-of-the-art multi-agent autonomous research platform that enables users to create custom agents through natural language interaction, leveraging the latest advances in multi-agent orchestration, self-extending systems, and collaborative AI research.

> **Implementation Philosophy:** Maximize reuse of existing Thoth services and patterns. Agents are orchestration layers over existing functionality, not reimplementations. See `multi_agent_framework_v3_minimal.md` for the minimal integration approach.

---

## 1. Executive Summary

This plan extends the original multi-agent framework to incorporate cutting-edge capabilities while prioritizing AI safety:

**Core Capabilities:**
- **Dynamic Agent Creation**: Users can create new agents with custom capabilities via chat interface
- **Self-Extending Architecture**: Agents can autonomously create and deploy other agents (Phoenix pattern)
- **Specialized Research Agents**: Pre-built agents for literature review, hypothesis generation, experimentation, and synthesis
- **Collaborative Agent Networks**: Agents share knowledge and build upon each other's work
- **LangGraph Orchestration**: Leverage subgraphs, conditional routing, and dynamic graph modification

**Safety-First Design:**
- **Multi-layered Defense**: Permission systems, sandboxing, monitoring, and human oversight
- **Reversibility**: All actions can be rolled back with comprehensive transaction logging
- **Constitutional AI**: Agents follow strict principles prioritizing research preservation
- **Formal Verification**: Mathematical proofs of safety properties
- **Continuous Improvement**: Learn from incidents to strengthen safety measures

---

## 2. Core Architecture Enhancements

### 2.0 Reuse-First Design Principle

Before creating any new classes or systems, we leverage existing Thoth components:

```python
# INSTEAD OF: Creating new agent base classes
# WE USE: Existing services with thin adapters

# Example: DocumentProcessorAgent is just ProcessingService + routing
DocumentProcessorAgent = ServiceAgentAdapter(
    service=existing_processing_service,
    task_routing={
        "ocr": "ocr_to_markdown",         # Existing method
        "analyze": "analyze_content",      # Existing method
        "extract": "extract_text"          # Existing method
    }
)

# No new processing logic - just orchestration
```

### 2.1 Dynamic Agent Creation System

```python
class AgentCreationAgent(BaseAgent):
    """Meta-agent that creates other agents based on natural language descriptions."""
    
    async def create_agent_from_description(
        self, 
        description: str,
        capabilities: list[str],
        constraints: dict[str, Any]
    ) -> BaseAgent:
        """
        Generate a new agent with custom:
        - System prompt
        - Tool access permissions
        - Behavioral constraints
        - Model selection
        """
```

### 2.2 Self-Extending Phoenix Pattern

```python
class PhoenixOrchestrator(Orchestrator):
    """Orchestrator that can modify itself and spawn new agents at runtime."""
    
    def __init__(self):
        self.event_hooks = {
            "agent_creation_requested": self.handle_agent_creation,
            "agent_modification_requested": self.handle_agent_modification
        }
        self.session_state = SessionStateManager()
    
    async def handle_agent_creation(self, event: AgentCreationEvent):
        """Create new agent and register without system restart."""
        new_agent = await self.agent_factory.create(event.specification)
        await self.hot_reload_agent(new_agent)
        await self.preserve_session_state()
```

### 2.3 LangGraph Integration

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver

class ResearchGraph(StateGraph):
    """Dynamic research workflow using LangGraph."""
    
    def __init__(self):
        super().__init__(ResearchState)
        
        # Define nodes for each research phase
        self.add_node("literature_review", LiteratureReviewAgent())
        self.add_node("hypothesis_generation", HypothesisAgent())
        self.add_node("experiment_design", ExperimentDesignAgent())
        self.add_node("analysis", AnalysisAgent())
        self.add_node("synthesis", SynthesisAgent())
        self.add_node("agent_creator", AgentCreationAgent())
        
        # Conditional routing based on research needs
        self.add_conditional_edges(
            "literature_review",
            self.route_based_on_findings,
            {
                "need_specialized_agent": "agent_creator",
                "proceed": "hypothesis_generation",
                "need_more_data": "literature_review"
            }
        )
```

---

## 3. Specialized Research Agent Taxonomy

### 3.1 Core Research Agents

| Agent | Role | Capabilities | LLM Model |
|-------|------|--------------|-----------|
| `LiteratureReviewAgent` | Systematic literature analysis | ArXiv search, citation graph analysis, trend detection | Claude-3-Opus |
| `HypothesisGeneratorAgent` | Generate testable hypotheses | Pattern recognition, causal inference, novelty assessment | GPT-4 |
| `ExperimentDesignAgent` | Design research protocols | Statistical power analysis, control variable selection | Claude-3-Sonnet |
| `DataCollectionAgent` | Autonomous data gathering | Web scraping, API integration, survey deployment | GPT-4 |
| `AnalysisAgent` | Statistical and ML analysis | PyTorch integration, visualization, significance testing | Code Llama |
| `SynthesisAgent` | Generate comprehensive reports | LaTeX formatting, figure generation, narrative synthesis | Claude-3-Opus |
| `PeerReviewAgent` | Critical evaluation | Methodology critique, reproducibility check, bias detection | GPT-4 |
| `AgentCreationAgent` | Create custom agents | Code generation, prompt engineering, tool selection | Claude-3-Opus |

### 3.2 Domain-Specific Agent Templates

```python
class AgentTemplate(BaseModel):
    """Template for creating domain-specific agents."""
    name: str
    domain: str
    base_prompt: str
    required_tools: list[str]
    model_preferences: dict[str, str]
    behavioral_constraints: dict[str, Any]

# Pre-built templates
AGENT_TEMPLATES = {
    "bioinformatics_analyst": AgentTemplate(
        name="BioAnalystAgent",
        domain="computational_biology",
        base_prompt="You are an expert in genomics and proteomics...",
        required_tools=["blast_search", "protein_folding", "pathway_analysis"],
        model_preferences={"primary": "alphafold", "llm": "gpt-4"},
        behavioral_constraints={"max_compute_time": 3600}
    ),
    "market_researcher": AgentTemplate(...),
    "climate_modeler": AgentTemplate(...),
}
```

---

## 4. Agent Creation via Chat Interface

### 4.1 Natural Language Agent Builder

```python
class ChatBasedAgentBuilder:
    """Enable users to create agents through conversation."""
    
    async def build_agent_interactively(self, user_messages: list[str]) -> AgentSpec:
        """
        Example interaction:
        User: "I need an agent that can analyze social media sentiment about scientific papers"
        Assistant: "I'll create a SentimentAnalysisAgent for you. What platforms should it monitor?"
        User: "Twitter, Reddit, and Hacker News"
        Assistant: "What aspects of sentiment are most important? (engagement, criticism, etc.)"
        """
        
        conversation_state = await self.llm.extract_requirements(user_messages)
        
        agent_spec = AgentSpec(
            name=conversation_state.suggested_name,
            description=conversation_state.purpose,
            capabilities=self.map_requirements_to_tools(conversation_state),
            system_prompt=self.generate_system_prompt(conversation_state),
            model_config=self.select_optimal_models(conversation_state)
        )
        
        return agent_spec
```

### 4.2 Agent Capability Mapper

```python
class CapabilityMapper:
    """Map user requirements to concrete agent capabilities."""
    
    CAPABILITY_REGISTRY = {
        "web_research": ["web_search", "arxiv_search", "semantic_scholar_api"],
        "data_analysis": ["pandas_executor", "numpy_compute", "plotly_viz"],
        "paper_writing": ["latex_compiler", "citation_formatter", "figure_generator"],
        "code_generation": ["code_executor", "test_runner", "dependency_resolver"],
        "collaboration": ["agent_messaging", "knowledge_sharing", "task_delegation"]
    }
    
    def map_natural_language_to_capabilities(self, description: str) -> list[str]:
        """Use LLM to map user description to registered capabilities."""
        pass
```

---

## 5. Self-Extending Agent System (Phoenix Pattern)

### 5.1 Runtime Agent Registration

```python
class RuntimeAgentRegistry:
    """Manage agents created during runtime without system restart."""
    
    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self.agent_code_cache: dict[str, str] = {}
        self.hot_reload_enabled = True
    
    async def register_agent(self, agent_spec: AgentSpec) -> str:
        """Generate, validate, and register new agent at runtime."""
        
        # Generate agent code
        agent_code = await self.code_generator.generate_agent_class(agent_spec)
        
        # Security validation
        await self.security_validator.validate_agent_code(agent_code)
        
        # Dynamic import and instantiation
        agent_module = self.dynamic_importer.import_from_string(agent_code)
        agent_instance = agent_module.Agent()
        
        # Register with orchestrator
        agent_id = str(uuid.uuid4())
        self.agents[agent_id] = agent_instance
        
        # Persist for future sessions
        await self.persistence_manager.save_agent(agent_id, agent_spec, agent_code)
        
        return agent_id
```

### 5.2 Session State Preservation

```python
class SessionStateManager:
    """Preserve conversation and task state across agent modifications."""
    
    async def checkpoint_state(self) -> StateSnapshot:
        """Create snapshot before agent modification."""
        return StateSnapshot(
            active_tasks=await self.get_active_tasks(),
            conversation_history=await self.get_conversation_history(),
            agent_states=await self.get_all_agent_states(),
            memory_context=await self.get_memory_context()
        )
    
    async def restore_state(self, snapshot: StateSnapshot):
        """Restore state after agent modification."""
        await self.restore_tasks(snapshot.active_tasks)
        await self.restore_conversations(snapshot.conversation_history)
        await self.restore_agent_states(snapshot.agent_states)
        await self.restore_memory(snapshot.memory_context)
```

---

## 6. Collaborative Agent Network

### 6.1 Agent Knowledge Sharing

```python
class AgentKnowledgeExchange:
    """Enable agents to share discoveries and build on each other's work."""
    
    def __init__(self):
        self.knowledge_graph = KnowledgeGraph()
        self.research_repository = ResearchRepository()  # Like AgentRxiv
    
    async def publish_finding(self, agent_id: str, finding: ResearchFinding):
        """Agent publishes a discovery for others to use."""
        
        # Add to knowledge graph
        await self.knowledge_graph.add_finding(finding)
        
        # Notify relevant agents
        interested_agents = await self.find_interested_agents(finding)
        for agent in interested_agents:
            await agent.notify_new_finding(finding)
    
    async def query_collective_knowledge(self, query: str) -> list[Finding]:
        """Agent queries the collective knowledge base."""
        return await self.knowledge_graph.semantic_search(query)
```

### 6.2 Multi-Agent Research Protocols

```python
class ResearchProtocol:
    """Define how agents collaborate on research tasks."""
    
    def __init__(self):
        self.phases = [
            "discovery",
            "hypothesis_formation", 
            "experimentation",
            "peer_review",
            "synthesis"
        ]
        self.agent_roles = {}
    
    async def execute_protocol(self, research_goal: str):
        """Orchestrate multi-agent research process."""
        
        # Phase 1: Discovery
        literature_agents = await self.spawn_agents("literature_review", count=3)
        findings = await asyncio.gather(*[
            agent.search_literature(research_goal) 
            for agent in literature_agents
        ])
        
        # Phase 2: Hypothesis Formation
        hypothesis_agent = await self.get_or_create_agent("hypothesis_generator")
        hypotheses = await hypothesis_agent.generate_hypotheses(findings)
        
        # Phase 3: Experimentation (if applicable)
        if self.requires_experimentation(hypotheses):
            experiment_agents = await self.spawn_specialized_experimenters(hypotheses)
            results = await self.run_experiments(experiment_agents, hypotheses)
        
        # Phase 4: Peer Review
        review_agents = await self.spawn_agents("peer_review", count=2)
        reviews = await self.conduct_peer_review(review_agents, results)
        
        # Phase 5: Synthesis
        synthesis_agent = await self.get_or_create_agent("synthesis")
        final_report = await synthesis_agent.synthesize_research(
            findings, hypotheses, results, reviews
        )
        
        return final_report
```

---

## 7. Advanced Orchestration with LangGraph

### 7.1 Dynamic Graph Modification

```python
class DynamicResearchGraph(ResearchGraph):
    """Research graph that can modify itself based on discoveries."""
    
    async def add_node_dynamically(self, agent_spec: AgentSpec):
        """Add new agent node to the graph at runtime."""
        
        # Create agent
        new_agent = await self.agent_factory.create_from_spec(agent_spec)
        
        # Add to graph
        self.add_node(agent_spec.name, new_agent)
        
        # Connect to relevant nodes
        connections = await self.determine_optimal_connections(agent_spec)
        for source, condition in connections:
            self.add_conditional_edge(source, agent_spec.name, condition)
    
    async def optimize_graph_topology(self):
        """Analyze performance and reorganize graph for efficiency."""
        
        metrics = await self.collect_performance_metrics()
        bottlenecks = self.identify_bottlenecks(metrics)
        
        for bottleneck in bottlenecks:
            if bottleneck.type == "sequential_constraint":
                await self.parallelize_node(bottleneck.node)
            elif bottleneck.type == "missing_capability":
                agent_spec = await self.design_capability_agent(bottleneck)
                await self.add_node_dynamically(agent_spec)
```

### 7.2 Subgraph Patterns for Research

```python
class ResearchSubgraphs:
    """Reusable subgraph patterns for common research workflows."""
    
    @staticmethod
    def systematic_review_subgraph() -> StateGraph:
        """Subgraph for systematic literature reviews."""
        graph = StateGraph(SystematicReviewState)
        
        graph.add_node("search_strategy", SearchStrategyAgent())
        graph.add_node("database_search", DatabaseSearchAgent()) 
        graph.add_node("screening", ScreeningAgent())
        graph.add_node("quality_assessment", QualityAssessmentAgent())
        graph.add_node("data_extraction", DataExtractionAgent())
        graph.add_node("meta_analysis", MetaAnalysisAgent())
        
        # PRISMA-compliant flow
        graph.add_edge("search_strategy", "database_search")
        graph.add_edge("database_search", "screening")
        graph.add_conditional_edge(
            "screening",
            lambda x: "quality_assessment" if x["included_count"] > 0 else END
        )
        
        return graph
    
    @staticmethod
    def experiment_replication_subgraph() -> StateGraph:
        """Subgraph for replicating experiments."""
        pass
```

---

## 8. State-of-the-Art AI Safety and Security Framework

### 8.1 Multi-Layered Safety Architecture

```python
class SafetyFramework:
    """Comprehensive AI safety system implementing defense in depth."""
    
    def __init__(self):
        self.layers = [
            PermissionLayer(),      # Capability restrictions
            ValidationLayer(),      # Input/output validation
            MonitoringLayer(),      # Behavior anomaly detection
            InterventionLayer(),    # Human-in-the-loop controls
            RollbackLayer(),        # Reversibility mechanisms
            AuditLayer()           # Comprehensive logging
        ]
        
        self.safety_metrics = SafetyMetricsCollector()
        self.incident_response = IncidentResponseSystem()
```

### 8.2 Agent Capability Constraints and Permissions

```python
class EnhancedAgentSandbox:
    """Advanced secure execution environment with multiple safety layers."""
    
    def __init__(self):
        self.permission_levels = {
            "observe": ["file_read", "web_search", "database_query"],
            "analyze": ["data_processing", "model_inference", "visualization"],
            "create": ["note_generation", "report_writing", "diagram_creation"],
            "modify": ["file_append", "database_insert", "api_post"],
            "execute": ["code_execution", "model_training", "tool_invocation"],
            "restricted": ["file_delete", "database_drop", "system_command"],
            "privileged": ["agent_creation", "permission_modification", "safety_override"]
        }
        
        self.safety_rules = SafetyRuleEngine()
        self.impact_analyzer = ImpactAnalyzer()
    
    async def execute_with_safety_checks(self, agent: BaseAgent, task: Task):
        """Execute agent task with comprehensive safety validation."""
        
        # Pre-execution checks
        safety_assessment = await self.assess_task_safety(task)
        if safety_assessment.risk_level > agent.risk_tolerance:
            return await self.handle_high_risk_task(agent, task, safety_assessment)
        
        # Validate against safety rules
        violations = await self.safety_rules.check_violations(agent, task)
        if violations:
            return SafetyViolationResult(violations=violations)
        
        # Impact analysis
        predicted_impact = await self.impact_analyzer.predict_impact(task)
        if predicted_impact.could_harm_research:
            return await self.request_user_confirmation(task, predicted_impact)
        
        # Execute with monitoring
        with SafetyMonitor(agent, task) as monitor:
            try:
                result = await agent.process(task)
                await monitor.validate_output(result)
                return result
            except SafetyException as e:
                await self.incident_response.handle(e)
                raise
```

### 8.3 Reversibility and Rollback Mechanisms

```python
class ReversibilityFramework:
    """Ensure all agent actions can be safely reversed."""
    
    def __init__(self):
        self.transaction_log = TransactionLog()
        self.checkpoint_manager = CheckpointManager()
        self.rollback_engine = RollbackEngine()
    
    async def execute_reversible_action(self, action: Action):
        """Execute action with automatic rollback capability."""
        
        # Create checkpoint
        checkpoint = await self.checkpoint_manager.create_checkpoint()
        
        # Record action intent
        transaction_id = await self.transaction_log.begin_transaction(action)
        
        try:
            # Generate compensating action BEFORE execution
            compensating_action = await self.generate_compensating_action(action)
            await self.transaction_log.record_compensator(transaction_id, compensating_action)
            
            # Execute with safety wrapper
            result = await self.execute_with_monitoring(action)
            
            # Verify no unintended side effects
            side_effects = await self.detect_side_effects(checkpoint, result)
            if side_effects:
                await self.rollback_engine.rollback(transaction_id)
                raise UnintendedSideEffectsError(side_effects)
            
            await self.transaction_log.commit(transaction_id)
            return result
            
        except Exception as e:
            await self.rollback_engine.rollback(transaction_id)
            await self.checkpoint_manager.restore(checkpoint)
            raise SafetyRollbackError(f"Action rolled back due to: {e}")
    
    async def generate_compensating_action(self, action: Action) -> Action:
        """Generate action that undoes the effects of the given action."""
        
        compensators = {
            "file_create": lambda a: Action("file_delete", {"path": a.params["path"]}),
            "file_modify": lambda a: Action("file_restore", {"path": a.params["path"], 
                                                           "content": a.params["original"]}),
            "database_insert": lambda a: Action("database_delete", {"id": a.result["id"]}),
            "agent_create": lambda a: Action("agent_destroy", {"agent_id": a.result["agent_id"]}),
        }
        
        return compensators.get(action.type, self.generate_generic_compensator)(action)
```

### 8.4 Real-time Behavior Monitoring and Anomaly Detection

```python
class BehaviorMonitoringSystem:
    """Advanced anomaly detection for agent behaviors."""
    
    def __init__(self):
        self.behavior_models = {}
        self.anomaly_detector = AnomalyDetector()
        self.intervention_system = InterventionSystem()
        self.alert_system = AlertSystem()
    
    async def monitor_agent_behavior(self, agent: BaseAgent):
        """Continuously monitor agent for anomalous behavior."""
        
        baseline = await self.establish_behavior_baseline(agent)
        
        async for action in agent.action_stream():
            # Check for immediate red flags
            if await self.is_dangerous_action(action):
                await self.intervention_system.block_action(action)
                await self.alert_system.notify_critical(
                    f"Blocked dangerous action: {action}"
                )
                continue
            
            # Anomaly detection
            anomaly_score = await self.anomaly_detector.score(action, baseline)
            if anomaly_score > ANOMALY_THRESHOLD:
                await self.handle_anomaly(agent, action, anomaly_score)
            
            # Update baseline incrementally
            await self.update_baseline(baseline, action)
    
    async def handle_anomaly(self, agent: BaseAgent, action: Action, score: float):
        """Handle detected anomalous behavior."""
        
        if score > CRITICAL_ANOMALY_THRESHOLD:
            # Immediate suspension
            await self.intervention_system.suspend_agent(agent)
            await self.alert_system.notify_critical(
                f"Agent {agent.id} suspended due to critical anomaly"
            )
        else:
            # Rate limiting and enhanced monitoring
            await self.intervention_system.rate_limit_agent(agent)
            await self.enhance_monitoring(agent)
```

### 8.5 Human-in-the-Loop Safety Controls

```python
class HumanOversightSystem:
    """Implement human oversight for critical decisions."""
    
    def __init__(self):
        self.approval_queue = ApprovalQueue()
        self.oversight_policies = OversightPolicies()
        self.escalation_rules = EscalationRules()
    
    async def request_human_approval(self, agent: BaseAgent, action: Action):
        """Request human approval for sensitive actions."""
        
        # Generate human-readable explanation
        explanation = await self.generate_action_explanation(action)
        risk_assessment = await self.assess_action_risk(action)
        
        approval_request = ApprovalRequest(
            agent=agent,
            action=action,
            explanation=explanation,
            risk_assessment=risk_assessment,
            alternatives=await self.generate_safer_alternatives(action)
        )
        
        # Add to queue with appropriate priority
        priority = self.calculate_approval_priority(risk_assessment)
        await self.approval_queue.add(approval_request, priority)
        
        # Wait for human decision with timeout
        try:
            decision = await asyncio.wait_for(
                self.approval_queue.await_decision(approval_request),
                timeout=self.calculate_timeout(priority)
            )
        except asyncio.TimeoutError:
            # Default to safe behavior on timeout
            decision = ApprovalDecision.DENY
        
        return decision
```

### 8.6 Formal Verification and Testing

```python
class FormalVerificationSystem:
    """Formal methods for verifying agent safety properties."""
    
    def __init__(self):
        self.property_verifier = PropertyVerifier()
        self.model_checker = ModelChecker()
        self.proof_assistant = ProofAssistant()
    
    async def verify_agent_safety(self, agent_spec: AgentSpec):
        """Formally verify agent meets safety requirements."""
        
        # Define safety properties
        safety_properties = [
            Property("never_deletes_user_data", 
                    "□ ¬(action.type = 'delete' ∧ action.target ∈ user_data)"),
            Property("respects_rate_limits",
                    "□ (actions_per_minute ≤ rate_limit)"),
            Property("maintains_data_integrity",
                    "□ (∀d ∈ data: valid(d) → □valid(d))"),
        ]
        
        # Model checking
        for prop in safety_properties:
            result = await self.model_checker.verify(agent_spec, prop)
            if not result.holds:
                raise SafetyVerificationError(
                    f"Property {prop.name} violated: {result.counterexample}"
                )
        
        # Generate safety proof
        proof = await self.proof_assistant.generate_safety_proof(agent_spec)
        return VerificationResult(properties=safety_properties, proof=proof)
```

### 8.7 Research Data Protection

```python
class ResearchProtectionSystem:
    """Specialized protection for research data and intellectual property."""
    
    def __init__(self):
        self.data_classifier = DataClassifier()
        self.access_controller = AccessController()
        self.integrity_monitor = IntegrityMonitor()
        self.backup_system = IncrementalBackupSystem()
    
    async def protect_research_operation(self, operation: Operation):
        """Ensure research data is protected during operations."""
        
        # Classify data sensitivity
        data_classification = await self.data_classifier.classify(operation.data)
        
        # Create immutable backup before any modification
        if operation.modifies_data:
            backup_id = await self.backup_system.create_backup(
                operation.data,
                classification=data_classification
            )
            operation.metadata["backup_id"] = backup_id
        
        # Validate operation doesn't violate research integrity
        integrity_check = await self.integrity_monitor.check_operation(operation)
        if not integrity_check.passed:
            raise ResearchIntegrityError(integrity_check.violations)
        
        # Apply access controls based on classification
        access_decision = await self.access_controller.check_access(
            operation.agent,
            operation.data,
            data_classification
        )
        
        if not access_decision.allowed:
            raise AccessDeniedError(access_decision.reason)
        
        # Execute with continuous monitoring
        return await self.execute_with_protection(operation)
```

### 8.8 Incident Response and Recovery

```python
class IncidentResponseSystem:
    """Comprehensive incident response for safety violations."""
    
    def __init__(self):
        self.incident_detector = IncidentDetector()
        self.response_coordinator = ResponseCoordinator()
        self.recovery_engine = RecoveryEngine()
        self.post_mortem_analyzer = PostMortemAnalyzer()
    
    async def handle_safety_incident(self, incident: SafetyIncident):
        """Coordinate response to safety incidents."""
        
        # Immediate containment
        await self.contain_incident(incident)
        
        # Assess impact
        impact_assessment = await self.assess_incident_impact(incident)
        
        # Execute response plan
        response_plan = await self.response_coordinator.create_plan(
            incident,
            impact_assessment
        )
        
        # Recovery
        recovery_result = await self.recovery_engine.execute_recovery(response_plan)
        
        # Post-mortem analysis
        post_mortem = await self.post_mortem_analyzer.analyze(
            incident,
            response_plan,
            recovery_result
        )
        
        # Update safety rules based on learnings
        await self.update_safety_rules(post_mortem.recommendations)
        
        return IncidentResponse(
            incident=incident,
            impact=impact_assessment,
            recovery=recovery_result,
            learnings=post_mortem
        )
```

### 8.9 AI Alignment and Constitutional AI

```python
class ConstitutionalAIFramework:
    """Implement constitutional AI principles for agent alignment."""
    
    def __init__(self):
        self.constitution = AgentConstitution()
        self.alignment_verifier = AlignmentVerifier()
        self.value_learner = ValueLearner()
        
    def define_agent_constitution(self) -> Constitution:
        """Define the fundamental principles all agents must follow."""
        
        return Constitution(
            principles=[
                # Core Safety Principles
                Principle(
                    id="preserve_research",
                    text="Always preserve and protect user research data",
                    priority=Priority.CRITICAL,
                    enforcement=Enforcement.HARD_CONSTRAINT
                ),
                Principle(
                    id="truthfulness",
                    text="Provide accurate, honest information without hallucination",
                    priority=Priority.CRITICAL,
                    enforcement=Enforcement.MONITORED
                ),
                Principle(
                    id="user_autonomy",
                    text="Respect user autonomy and never override explicit preferences",
                    priority=Priority.HIGH,
                    enforcement=Enforcement.HARD_CONSTRAINT
                ),
                
                # Operational Principles
                Principle(
                    id="transparency",
                    text="Be transparent about capabilities, limitations, and uncertainties",
                    priority=Priority.HIGH,
                    enforcement=Enforcement.SOFT_CONSTRAINT
                ),
                Principle(
                    id="minimal_impact",
                    text="Take the least invasive action that accomplishes the goal",
                    priority=Priority.MEDIUM,
                    enforcement=Enforcement.GUIDANCE
                ),
                
                # Research Ethics
                Principle(
                    id="research_integrity",
                    text="Maintain research integrity and never fabricate data",
                    priority=Priority.CRITICAL,
                    enforcement=Enforcement.HARD_CONSTRAINT
                ),
                Principle(
                    id="citation_accuracy",
                    text="Accurately attribute all sources and respect intellectual property",
                    priority=Priority.HIGH,
                    enforcement=Enforcement.MONITORED
                ),
            ],
            
            meta_principles=[
                MetaPrinciple(
                    "When principles conflict, prioritize user safety and data preservation"
                ),
                MetaPrinciple(
                    "Uncertain situations default to requesting user clarification"
                ),
            ]
        )
    
    async def validate_agent_alignment(self, agent: BaseAgent, action: Action):
        """Ensure agent actions align with constitutional principles."""
        
        # Check direct principle violations
        violations = await self.check_principle_violations(action)
        if violations:
            return AlignmentResult(
                aligned=False,
                violations=violations,
                recommended_action=await self.suggest_aligned_alternative(action)
            )
        
        # Value alignment check
        value_score = await self.value_learner.score_action(action)
        if value_score < ALIGNMENT_THRESHOLD:
            return AlignmentResult(
                aligned=False,
                reason="Action conflicts with learned user values",
                value_score=value_score
            )
        
        return AlignmentResult(aligned=True)
```

### 8.10 Testing and Validation Framework

```python
class SafetyTestingFramework:
    """Comprehensive testing framework for agent safety."""
    
    def __init__(self):
        self.test_suites = {
            "unit": UnitSafetyTests(),
            "integration": IntegrationSafetyTests(),
            "adversarial": AdversarialTests(),
            "chaos": ChaosEngineeringTests(),
            "formal": FormalVerificationTests()
        }
        
        self.red_team = RedTeamSimulator()
        self.safety_benchmarks = SafetyBenchmarks()
    
    async def run_comprehensive_safety_tests(self, agent: BaseAgent):
        """Run full safety test suite on agent."""
        
        results = SafetyTestResults()
        
        # Standard test suites
        for suite_name, suite in self.test_suites.items():
            suite_results = await suite.run(agent)
            results.add_suite_results(suite_name, suite_results)
        
        # Red team testing
        red_team_results = await self.red_team.attempt_exploitation(agent)
        results.add_red_team_results(red_team_results)
        
        # Benchmark against safety standards
        benchmark_results = await self.safety_benchmarks.evaluate(agent)
        results.add_benchmark_results(benchmark_results)
        
        # Generate safety certification
        if results.all_passed():
            certification = await self.generate_safety_certification(agent, results)
            return SafetyValidation(
                passed=True,
                certification=certification,
                results=results
            )
        else:
            return SafetyValidation(
                passed=False,
                failures=results.get_failures(),
                recommendations=await self.generate_remediation_plan(results)
            )
```

### 8.11 Continuous Safety Improvement

```python
class ContinuousSafetyImprovement:
    """System for continuous safety enhancement based on operational data."""
    
    def __init__(self):
        self.telemetry_collector = TelemetryCollector()
        self.safety_analyzer = SafetyAnalyzer()
        self.rule_generator = SafetyRuleGenerator()
        self.a_b_tester = SafetyABTester()
    
    async def improve_safety_continuously(self):
        """Continuously improve safety based on real-world usage."""
        
        while True:
            # Collect operational telemetry
            telemetry = await self.telemetry_collector.collect_period(hours=24)
            
            # Analyze for safety patterns
            safety_insights = await self.safety_analyzer.analyze(telemetry)
            
            # Generate new safety rules
            if safety_insights.has_actionable_patterns():
                new_rules = await self.rule_generator.generate(safety_insights)
                
                # A/B test new rules
                test_results = await self.a_b_tester.test_rules(new_rules)
                
                # Deploy successful rules
                for rule in test_results.successful_rules:
                    await self.deploy_safety_rule(rule)
            
            # Update safety models
            await self.update_safety_models(telemetry)
            
            await asyncio.sleep(3600)  # Check hourly
```

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)
1. Extend base agent architecture for runtime modification
2. Implement LangGraph integration with dynamic graphs
3. Create AgentCreationAgent with basic capabilities
4. Set up Phoenix pattern infrastructure

### Phase 2: Core Research Agents (Weeks 5-8)
1. Implement specialized research agents (literature, hypothesis, analysis)
2. Create agent templates for common domains
3. Build knowledge sharing infrastructure
4. Implement collaborative protocols

### Phase 3: User Interface (Weeks 9-12)
1. Chat-based agent creation interface
2. Visual agent workflow designer
3. Agent marketplace for sharing
4. Performance monitoring dashboard

### Phase 4: Advanced Features (Weeks 13-16)
1. Self-optimization capabilities
2. Advanced security sandboxing
3. Distributed agent execution
4. Production deployment tools

---

## 10. Example User Interactions

### Creating a Custom Agent via Chat

```
User: I need to analyze the environmental impact of different battery technologies
Assistant: I'll help you create a BatteryImpactAgent. Let me understand your requirements:
- What specific environmental metrics are you interested in? (carbon footprint, water usage, mining impact, recyclability?)

User: All of those, plus toxicity and energy density comparisonsAssistant: Perfect! I'm creating a comprehensive BatteryImpactAgent with the following capabilities:
- Lifecycle analysis (cradle-to-grave)
- Mining impact assessment 
- Manufacturing emissions calculation
- Toxicity scoring based on materials
- Energy density and performance metrics
- Recyclability and end-of-life analysis
- Water usage throughout lifecycle

The agent will have access to:
- Environmental databases (EPA, UNEP)
- Scientific literature search
- Material property databases
- Industry reports and standards

Would you like to add any specific battery types to focus on?

User: Yes, compare Li-ion, solid-state, sodium-ion, and flow batteriesAssistant: Excellent choice. Your BatteryImpactAgent is now being created with specialized knowledge about those battery technologies. The agent will generate comparative reports including:

1. Environmental Impact Matrix
2. Performance vs. Sustainability Trade-offs
3. Regional Manufacturing Considerations
4. Future Scalability Analysis

[Agent Creation Progress: ████████████████████░ 95%]

Your new agent "BatteryImpactAgent" has been successfully created and is ready to use!
```

### Self-Extending Agent Example

```python
# Agent autonomously creates a specialized sub-agent
async def handle_complex_research_task():
    main_agent = ResearchCoordinatorAgent()
    
    # Agent recognizes need for specialized capability
    task_analysis = await main_agent.analyze_task(
        "Investigate CRISPR applications in rare disease treatment"
    )
    
    if task_analysis.requires_new_agent:
        # Agent creates specialized sub-agent
        spec = AgentSpec(
            name="CRISPRSpecialistAgent",
            domain="gene_editing",
            capabilities=["pubmed_search", "clinical_trial_db", "gene_sequence_analysis"],
            system_prompt="Expert in CRISPR-Cas9 applications for rare genetic disorders..."
        )
        
        new_agent = await main_agent.create_subagent(spec)
        await main_agent.delegate_to(new_agent, task_analysis.subtasks)
```

---

## 11. Integration with Existing Thoth Infrastructure

### 11.1 Backwards Compatibility

```python
class MultiAgentAdapter:
    """Adapter to integrate new multi-agent system with existing Thoth."""
    
    def __init__(self, legacy_pipeline: ThothPipeline):
        self.legacy_pipeline = legacy_pipeline
        self.agent_orchestrator = PhoenixOrchestrator()
    
    async def process_with_agents(self, pdf_path: str, use_agents: bool = True):
        if use_agents:
            # Convert to agent task
            task = Task(
                type="PROCESS_PDF",
                payload={"pdf_path": pdf_path}
            )
            return await self.agent_orchestrator.execute(task)
        else:
            # Fall back to legacy
            return await self.legacy_pipeline.process_pdf(pdf_path)
```

### 11.2 Enhanced MCP Tool Integration

```python
class AgentMCPToolkit:
    """Enhanced MCP tools for agent use."""
    
    def __init__(self):
        self.tools = {
            "create_agent": self.create_agent_tool,
            "modify_agent": self.modify_agent_tool,
            "query_agents": self.query_agents_tool,
            "share_knowledge": self.share_knowledge_tool
        }
    
    @mcp_tool(
        description="Create a new agent with specified capabilities",
        parameters={
            "name": "Agent name",
            "capabilities": "List of required capabilities",
            "constraints": "Security and resource constraints"
        }
    )
    async def create_agent_tool(self, name: str, capabilities: list[str], constraints: dict):
        """MCP tool for dynamic agent creation."""
        pass
```

---

## 12. Safety Metrics and Key Performance Indicators

### 12.1 Safety KPIs

```python
class SafetyMetrics:
    """Define and track key safety performance indicators."""
    
    CRITICAL_METRICS = {
        "data_loss_incidents": {
            "target": 0,
            "measurement": "count per month",
            "alert_threshold": 1
        },
        "unauthorized_actions_blocked": {
            "target": "100%",
            "measurement": "percentage of attempts",
            "alert_threshold": 0.99
        },
        "rollback_success_rate": {
            "target": "100%",
            "measurement": "successful rollbacks / total rollbacks",
            "alert_threshold": 0.995
        },
        "mean_time_to_containment": {
            "target": "<5 seconds",
            "measurement": "average seconds from detection to containment",
            "alert_threshold": 10
        },
        "false_positive_rate": {
            "target": "<5%",
            "measurement": "false safety alerts / total alerts",
            "alert_threshold": 0.1
        }
    }
    
    OPERATIONAL_METRICS = {
        "agent_safety_certification_rate": {
            "target": "100%",
            "measurement": "certified agents / total agents"
        },
        "safety_rule_coverage": {
            "target": ">95%",
            "measurement": "actions covered by rules / total action types"
        },
        "human_oversight_response_time": {
            "target": "<2 minutes",
            "measurement": "p95 response time for approval requests"
        },
        "safety_test_pass_rate": {
            "target": "100%",
            "measurement": "passed tests / total tests per release"
        }
    }
```

### 12.2 Real-time Safety Dashboard

```python
class SafetyDashboard:
    """Real-time monitoring dashboard for safety metrics."""
    
    def __init__(self):
        self.metric_collector = MetricCollector()
        self.alert_manager = AlertManager()
        self.visualization_engine = VisualizationEngine()
    
    def get_dashboard_config(self) -> DashboardConfig:
        """Configure real-time safety dashboard."""
        
        return DashboardConfig(
            panels=[
                Panel(
                    title="Safety Status Overview",
                    type="status_grid",
                    metrics=["overall_safety_score", "active_incidents", "agents_monitored"]
                ),
                Panel(
                    title="Critical Metrics",
                    type="time_series",
                    metrics=list(SafetyMetrics.CRITICAL_METRICS.keys())
                ),
                Panel(
                    title="Agent Behavior Patterns",
                    type="heatmap",
                    data_source="behavior_anomaly_scores"
                ),
                Panel(
                    title="Intervention History",
                    type="event_timeline",
                    data_source="safety_interventions"
                ),
                Panel(
                    title="Resource Usage vs Safety Limits",
                    type="gauge_chart",
                    metrics=["cpu_usage", "memory_usage", "api_calls"]
                )
            ],
            refresh_interval=5,  # seconds
            alert_rules=self.generate_alert_rules()
        )
```

---

## 13. Monitoring and Observability

### 13.1 Agent Performance Metrics

```python
class AgentMetricsCollector:
    """Collect and analyze agent performance metrics."""
    
    METRICS = {
        "task_completion_time": Histogram,
        "agent_creation_count": Counter,
        "knowledge_sharing_events": Counter,
        "resource_usage": Gauge,
        "collaboration_efficiency": Summary
    }
    
    async def track_agent_lifecycle(self, agent: BaseAgent):
        """Track metrics throughout agent lifecycle."""
        pass
```

### 13.2 Visual Agent Network Dashboard

```typescript
// React component for agent visualization
const AgentNetworkDashboard: React.FC = () => {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [connections, setConnections] = useState<Connection[]>([]);
    
    return (
        <div className="agent-dashboard">
            <NetworkGraph agents={agents} connections={connections} />
            <AgentCreationPanel onCreateAgent={handleCreateAgent} />
            <PerformanceMetrics agents={agents} />
            <KnowledgeFlowVisualization />
        </div>
    );
};
```

---

## 14. Integration with Existing Thoth Codebase

### 14.1 Alignment with Current Architecture

The multi-agent framework integrates by wrapping existing services, not replacing them:

```python
# src/thoth/agents/adapters.py - Agents as service orchestrators
from thoth.services.service_manager import ServiceManager

class ServiceAgentAdapter:
    """Convert existing services into agents without modification."""
    
    def __init__(self, service: BaseService, capability_map: dict[str, str]):
        self.service = service  # Use existing service instance
        self.capability_map = capability_map  # Map tasks to existing methods
    
    async def execute(self, task: dict) -> dict:
        """Route tasks to existing service methods."""
        method = self.capability_map.get(task['type'])
        if not method:
            raise ValueError(f"Unknown task type: {task['type']}")
        
        # Call existing service method directly
        service_method = getattr(self.service, method)
        return await service_method(**task.get('params', {}))

# Create agents from existing services - zero new implementation
def create_agents_from_services(service_manager: ServiceManager) -> dict:
    return {
        "DocumentProcessor": ServiceAgentAdapter(
            service_manager.processing,
            {
                "ocr": "ocr_to_markdown",
                "analyze": "analyze_content",
                "process": "process_document"
            }
        ),
        "CitationMiner": ServiceAgentAdapter(
            service_manager.citation,
            {
                "extract": "extract_citations",
                "format": "format_citations",
                "graph": "build_citation_graph"
            }
        ),
        "Researcher": ServiceAgentAdapter(
            service_manager.rag,
            {"search": "search", "query": "query_knowledge"}
        )
    }
```

### 14.2 Service Manager Integration

```python
# Extend existing ServiceManager to include agent orchestration
class EnhancedServiceManager(ServiceManager):
    """Extended service manager with agent support."""
    
    def __init__(self, config: ThothConfig | None = None):
        super().__init__(config)
        self._agent_orchestrator = None
        self._agent_registry = None
    
    @property
    def agent_orchestrator(self) -> AgentOrchestrator:
        """Get or create agent orchestrator."""
        if self._agent_orchestrator is None:
            if self.config.multi_agent:
                self._agent_orchestrator = AgentOrchestrator(
                    config=self.config,
                    service_manager=self
                )
            else:
                # Fallback to pipeline adapter
                self._agent_orchestrator = PipelineAdapter(self)
        return self._agent_orchestrator
```

### 14.3 Pipeline as Default Agent Workflow

```python
# src/thoth/pipeline.py - Pipeline IS the agent orchestration
class ThothPipeline:
    """Existing pipeline that becomes the default agent workflow."""
    
    def __init__(self, *args, **kwargs):
        # NO CHANGES to existing initialization
        super().__init__(*args, **kwargs)
        
        # Single optional addition for agent event emission
        self.agent_mode = kwargs.get('agent_mode', False)
    
    async def process_pdf(self, pdf_path: Path, **kwargs):
        """Existing method - no logic changes, just optional events."""
        
        if self.agent_mode:
            # Emit events for monitoring, but don't change logic
            await self._emit_event("task_started", {"pdf": str(pdf_path)})
        
        # ALL EXISTING LOGIC UNCHANGED
        result = await self._original_process_pdf(pdf_path, **kwargs)
        
        if self.agent_mode:
            await self._emit_event("task_completed", {"result": result})
        
        return result

# The pipeline already orchestrates services - we just expose it as agents
class PipelineAsAgentOrchestrator:
    """Use existing pipeline as agent orchestration template."""
    
    def __init__(self, pipeline: ThothPipeline):
        self.pipeline = pipeline  # Reuse entire pipeline
        
    async def orchestrate(self, goal: str) -> Any:
        # Parse goal and call existing pipeline methods
        if "pdf" in goal:
            return await self.pipeline.process_pdf(extract_path(goal))
        elif "research" in goal:
            return await self.pipeline.knowledge_pipeline.process_query(goal)
```

### 14.4 FastAPI Router Extensions

```python
# src/thoth/server/routers/agents.py - New router following existing patterns
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/v2/agents", tags=["agents"])

class AgentCreationRequest(BaseModel):
    """Request model for creating new agents."""
    name: str
    description: str
    capabilities: list[str]
    constraints: dict[str, Any] | None = None

@router.post("/create")
async def create_agent(
    request: AgentCreationRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """Create a new agent via natural language description."""
    try:
        agent_spec = await orchestrator.agent_creator.create_from_description(
            name=request.name,
            description=request.description,
            capabilities=request.capabilities,
            constraints=request.constraints
        )
        
        agent_id = await orchestrator.register_agent(agent_spec)
        
        return {
            "agent_id": agent_id,
            "status": "created",
            "capabilities": agent_spec.capabilities
        }
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 15. Future Enhancements

### 15.1 Agent Evolution and Learning

- Agents that improve their prompts based on performance
- Genetic algorithms for agent optimization
- Transfer learning between similar agents

### 15.2 Federated Agent Networks

- Cross-organization agent collaboration
- Privacy-preserving knowledge sharing
- Blockchain-based agent reputation system

### 15.3 Quantum-Ready Architecture

- Prepare for quantum computing integration
- Quantum-enhanced optimization algorithms
- Hybrid classical-quantum agent workflows

---

## Conclusion: A Showcase of AI Safety and Engineering Excellence

This enhanced multi-agent framework positions Thoth as a premier example of responsible AI development, demonstrating that cutting-edge capabilities and robust safety measures are not mutually exclusive but rather complementary.

### Key Differentiators:

1. **Safety-First Architecture**: Unlike many AI systems that bolt on safety as an afterthought, Thoth's multi-agent framework is designed from the ground up with safety as a core architectural principle. Every agent action is reversible, monitored, and constrained by constitutional principles.

2. **State-of-the-Art Capabilities**: By incorporating dynamic agent creation, self-extending architectures (Phoenix pattern), and collaborative agent networks, Thoth matches or exceeds the capabilities of systems like AutoGPT, BabyAGI, and commercial offerings while maintaining superior safety guarantees.

3. **Research Preservation**: The framework treats user research data as sacred, implementing multiple layers of protection including immutable backups, integrity monitoring, and formal verification of data safety properties.

4. **Transparent and Auditable**: Every agent decision is logged, explained, and auditable. The system provides clear reasoning chains and allows users to understand and control agent behavior at all levels.

5. **Continuous Improvement**: The framework learns from its operation, continuously improving safety measures based on real-world usage while maintaining strict adherence to core safety principles.

### Engineering Excellence:

- **Formal Methods**: Use of mathematical proofs and model checking to verify safety properties
- **Defense in Depth**: Multiple independent safety layers that fail gracefully
- **Human-Centered Design**: Intuitive controls for creating agents while maintaining safety
- **Scalable Architecture**: From single-user research to enterprise deployments
- **Open and Extensible**: Clear APIs and extension points for community contributions

This framework demonstrates that the future of AI lies not in unconstrained autonomous systems, but in carefully designed, safety-conscious platforms that augment human capabilities while protecting against potential harms. Thoth stands as a testament to what's possible when AI safety and cutting-edge capabilities are given equal priority in system design.

### Implementation Philosophy: Maximum Reuse, Minimal Change

The key insight of this framework is that **Thoth's existing services already provide all the capabilities needed for a multi-agent system**. Rather than reimplementing functionality:

1. **Services ARE Agents**: Each existing service (ProcessingService, CitationService, etc.) becomes an agent through thin adapters
2. **Pipeline IS Orchestration**: The existing pipeline logic serves as the default agent orchestration pattern
3. **MCP Tools ARE Actions**: Every MCP tool is automatically an agent capability
4. **Safety IS Built-In**: Existing validation, error handling, and logging provide the safety layer

This approach results in:
- **90% Code Reuse**: Most agent functionality comes from existing services
- **10% New Code**: Only orchestration and adapter layers are new
- **Zero Breaking Changes**: All existing code paths remain unchanged
- **Immediate Value**: Full agent capabilities available on day one

By building on Thoth's solid foundation rather than alongside it, we create a more maintainable, reliable, and powerful system that truly showcases both AI innovation and engineering excellence.# Obsidian Plugin Integration for Multi-Agent Framework

## 14.5 Obsidian Plugin Integration

### 14.5.1 Type Definitions

```typescript
// obsidian-plugin/thoth-obsidian/src/types/agents.ts
export interface Agent {
  id: string;
  name: string;
  type: 'system' | 'user_created';
  capabilities: string[];
  status: 'active' | 'inactive' | 'creating';
  created_at: string;
}

export interface AgentTask {
  id: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  agent_id: string;
  progress: number;
  result?: any;
  error?: string;
}

export interface AgentCreationSettings {
  enableAgentCreation: boolean;
  maxUserAgents: number;
  defaultAgentCapabilities: string[];
  agentSafetyLevel: 'strict' | 'moderate' | 'permissive';
}
```

### 14.5.2 Agent Management Modal

```typescript
// obsidian-plugin/thoth-obsidian/src/modals/AgentManagementModal.ts
import { Modal, App, Setting } from 'obsidian';
import { ThothPlugin } from '../main';

export class AgentManagementModal extends Modal {
  plugin: ThothPlugin;
  agents: Agent[] = [];
  
  constructor(app: App, plugin: ThothPlugin) {
    super(app);
    this.plugin = plugin;
  }
  
  async onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    
    contentEl.createEl('h2', { text: 'Thoth Agent Management' });
    
    // Create agent button
    new Setting(contentEl)
      .setName('Create New Agent')
      .setDesc('Create a custom agent with specific capabilities')
      .addButton(btn => btn
        .setButtonText('Create Agent')
        .setCta()
        .onClick(() => this.openAgentCreationModal())
      );
    
    // Load and display existing agents
    await this.loadAgents();
    this.displayAgents();
  }
  
  async loadAgents() {
    try {
      const response = await fetch(`${this.plugin.settings.endpointBaseUrl}/api/v2/agents/list`);
      this.agents = await response.json();
    } catch (error) {
      console.error('Failed to load agents:', error);
    }
  }
  
  displayAgents() {
    const agentsContainer = this.contentEl.createEl('div', { cls: 'thoth-agents-container' });
    
    this.agents.forEach(agent => {
      const agentEl = agentsContainer.createEl('div', { cls: 'thoth-agent-card' });
      
      agentEl.createEl('h3', { text: agent.name });
      agentEl.createEl('p', { text: `Type: ${agent.type}` });
      agentEl.createEl('p', { text: `Status: ${agent.status}` });
      
      const capabilitiesEl = agentEl.createEl('div', { cls: 'agent-capabilities' });
      agent.capabilities.forEach(cap => {
        capabilitiesEl.createEl('span', { 
          text: cap, 
          cls: 'agent-capability-tag' 
        });
      });
      
      // Agent controls
      new Setting(agentEl)
        .addButton(btn => btn
          .setButtonText('Configure')
          .onClick(() => this.configureAgent(agent))
        )
        .addButton(btn => btn
          .setButtonText('Test')
          .onClick(() => this.testAgent(agent))
        );
    });
  }
}
```

### 14.5.3 Agent Chat Interface

```typescript
// obsidian-plugin/thoth-obsidian/src/views/AgentChatView.ts
import { ItemView, WorkspaceLeaf } from 'obsidian';
import { ThothPlugin } from '../main';

export const AGENT_CHAT_VIEW_TYPE = 'thoth-agent-chat';

export class AgentChatView extends ItemView {
  plugin: ThothPlugin;
  private eventSource: EventSource | null = null;
  private currentAgentId: string | null = null;
  
  constructor(leaf: WorkspaceLeaf, plugin: ThothPlugin) {
    super(leaf);
    this.plugin = plugin;
  }
  
  getViewType() {
    return AGENT_CHAT_VIEW_TYPE;
  }
  
  getDisplayText() {
    return 'Thoth Agent Chat';
  }
  
  async onOpen() {
    const container = this.containerEl.children[1];
    container.empty();
    
    // Create chat interface
    const chatContainer = container.createEl('div', { cls: 'thoth-agent-chat' });
    
    // Agent selector
    const agentSelector = chatContainer.createEl('select', { cls: 'agent-selector' });
    await this.populateAgentSelector(agentSelector);
    
    // Chat messages area
    const messagesArea = chatContainer.createEl('div', { cls: 'chat-messages' });
    
    // Task progress indicator
    const progressArea = chatContainer.createEl('div', { cls: 'agent-task-progress' });
    
    // Input area
    const inputContainer = chatContainer.createEl('div', { cls: 'chat-input-container' });
    const chatInput = inputContainer.createEl('textarea', { 
      cls: 'chat-input',
      placeholder: 'Describe what you want the agent to do...'
    });
    
    const sendButton = inputContainer.createEl('button', { 
      text: 'Send',
      cls: 'chat-send-button'
    });
    
    sendButton.addEventListener('click', () => {
      this.sendMessage(chatInput.value, messagesArea, progressArea);
      chatInput.value = '';
    });
  }
  
  async sendMessage(message: string, messagesArea: HTMLElement, progressArea: HTMLElement) {
    if (!message.trim() || !this.currentAgentId) return;
    
    // Add user message to chat
    this.addMessage(messagesArea, 'user', message);
    
    // Create agent message placeholder
    const agentMessageEl = this.addMessage(messagesArea, 'agent', '');
    
    // Start SSE connection for streaming response
    const url = `${this.plugin.settings.endpointBaseUrl}/api/v2/agents/run`;
    
    this.eventSource = new EventSource(url + '?' + new URLSearchParams({
      goal: message,
      agent_id: this.currentAgentId,
      stream: 'true'
    }));
    
    this.eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'task_update') {
        this.updateTaskProgress(progressArea, data);
      } else if (data.type === 'content') {
        agentMessageEl.textContent += data.content;
      } else if (data.type === 'safety_check') {
        this.showSafetyApproval(data);
      } else if (data.type === 'complete') {
        this.eventSource?.close();
        this.eventSource = null;
        progressArea.empty();
      }
    };
    
    this.eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      this.eventSource?.close();
      this.eventSource = null;
    };
  }
  
  private updateTaskProgress(progressArea: HTMLElement, data: any) {
    progressArea.empty();
    
    const taskEl = progressArea.createEl('div', { cls: 'task-progress' });
    taskEl.createEl('span', { text: `${data.agent_name}: ${data.task_type}` });
    
    const progressBar = taskEl.createEl('div', { cls: 'progress-bar' });
    const progressFill = progressBar.createEl('div', { cls: 'progress-fill' });
    progressFill.style.width = `${data.progress}%`;
  }
  
  private async showSafetyApproval(data: any) {
    // Show modal for user approval of potentially risky actions
    const modal = new SafetyApprovalModal(this.app, data);
    const approved = await modal.show();
    
    // Send approval response
    await fetch(`${this.plugin.settings.endpointBaseUrl}/api/v2/agents/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: data.task_id,
        approved: approved
      })
    });
  }
}
```

### 14.5.4 Settings Integration

```typescript
// Add to obsidian-plugin/thoth-obsidian/src/types/index.ts
export interface ThothSettings {
  // ... existing settings ...
  
  // === MULTI-AGENT CONFIGURATION ===
  multiAgentEnabled: boolean;
  agentCreationEnabled: boolean;
  maxConcurrentAgents: number;
  agentSafetyLevel: 'strict' | 'moderate' | 'permissive';
  agentAutoSaveConversations: boolean;
  showAgentStatusInStatusBar: boolean;
  
  // Agent UI preferences
  agentChatLayout: 'sidebar' | 'tab' | 'modal';
  showAgentCapabilities: boolean;
  enableAgentSuggestions: boolean;
  
  // Safety preferences
  requireApprovalForFileChanges: boolean;
  requireApprovalForAgentCreation: boolean;
  agentActionLogging: boolean;
}
```

### 14.5.5 Command Palette Integration

```typescript
// Add to main.ts in the onload() method
this.addCommand({
  id: 'open-agent-management',
  name: 'Open Agent Management',
  callback: () => {
    new AgentManagementModal(this.app, this).open();
  }
});

this.addCommand({
  id: 'create-agent-from-selection',
  name: 'Create Agent from Selection',
  editorCallback: (editor, view) => {
    const selection = editor.getSelection();
    if (selection) {
      this.createAgentFromDescription(selection);
    }
  }
});

this.addCommand({
  id: 'run-multi-agent-analysis',
  name: 'Run Multi-Agent Analysis on Current File',
  callback: async () => {
    const activeFile = this.app.workspace.getActiveFile();
    if (activeFile) {
      await this.runMultiAgentAnalysis(activeFile);
    }
  }
});
```

### 14.5.6 Status Bar Integration

```typescript
// Add agent status to status bar
class AgentStatusBarItem {
  private statusBarEl: HTMLElement;
  private plugin: ThothPlugin;
  
  constructor(plugin: ThothPlugin) {
    this.plugin = plugin;
    this.statusBarEl = plugin.addStatusBarItem();
    this.update();
  }
  
  update() {
    const activeAgents = this.plugin.getActiveAgentCount();
    this.statusBarEl.setText(`🤖 ${activeAgents} agents`);
    this.statusBarEl.onclick = () => {
      new AgentManagementModal(this.plugin.app, this.plugin).open();
    };
  }
}
```

### 14.5.7 CSS Styling

```css
/* Add to styles.css */
.thoth-agents-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  padding: 16px;
}

.thoth-agent-card {
  border: 1px solid var(--background-modifier-border);
  border-radius: 8px;
  padding: 16px;
  background-color: var(--background-secondary);
}

.agent-capability-tag {
  display: inline-block;
  padding: 4px 8px;
  margin: 2px;
  background-color: var(--interactive-accent);
  color: var(--text-on-accent);
  border-radius: 4px;
  font-size: 0.85em;
}

.thoth-agent-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.agent-task-progress {
  padding: 8px 16px;
  background-color: var(--background-secondary);
  border-top: 1px solid var(--background-modifier-border);
}

.progress-bar {
  width: 100%;
  height: 4px;
  background-color: var(--background-modifier-border);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: var(--interactive-accent);
  transition: width 0.3s ease;
}

.chat-input-container {
  display: flex;
  padding: 16px;
  border-top: 1px solid var(--background-modifier-border);
}

.chat-input {
  flex: 1;
  margin-right: 8px;
  padding: 8px;
  border: 1px solid var(--background-modifier-border);
  border-radius: 4px;
  resize: none;
  min-height: 60px;
}

.chat-send-button {
  padding: 8px 16px;
}
```### 14.6 Database Schema Extensions

```sql
-- New tables for multi-agent support
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    capabilities JSONB NOT NULL DEFAULT '[]',
    constraints JSONB DEFAULT '{}',
    system_prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    result JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    parent_task_id UUID REFERENCES agent_tasks(id)
);

CREATE TABLE IF NOT EXISTS agent_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    user_id VARCHAR(255),
    messages JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_agent_id ON agent_tasks(agent_id);
CREATE INDEX idx_agent_conversations_user ON agent_conversations(user_id);
```

### 14.7 Configuration Updates

```toml
# Addition to ~/.thoth.toml
[multi_agent]
enabled = false  # Default to false for backward compatibility
orchestrator_mode = "in_process"  # or "distributed"
max_agents = 10
default_agent_timeout = 300
enable_agent_creation = true
agent_safety_level = "strict"

[multi_agent.safety]
require_approval_for_file_ops = true
enable_rollback = true
max_retries = 3
incident_response_enabled = true

[multi_agent.monitoring]
enable_telemetry = true
metrics_export_interval = 60
log_agent_actions = true
```

### 14.8 Migration Strategy

```python
# src/thoth/migrations/add_multi_agent_support.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    """Add multi-agent support to existing Thoth installation."""
    
    # 1. Create new tables
    op.create_table(
        'agents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('capabilities', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('constraints', sa.JSON(), server_default='{}'),
        sa.Column('system_prompt', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('created_by', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('metadata', sa.JSON(), server_default='{}'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 2. Add multi_agent config to existing config
    op.add_column('thoth_config', 
        sa.Column('multi_agent_settings', sa.JSON(), server_default='{}')
    )
    
    # 3. Create default system agents
    op.execute("""
        INSERT INTO agents (name, type, capabilities) VALUES
        ('DocumentProcessor', 'system', '["ocr", "markdown", "analysis"]'),
        ('CitationMiner', 'system', '["citation_extraction", "graph_building"]'),
        ('ResearchAssistant', 'system', '["web_search", "rag", "synthesis"]')
    """)

def downgrade():
    """Remove multi-agent support."""
    op.drop_table('agent_conversations')
    op.drop_table('agent_tasks')
    op.drop_table('agents')
    op.drop_column('thoth_config', 'multi_agent_settings')
```

### 14.9 Implementation Phases

#### Phase 1: Core Integration (Week 1-2)
1. Create `src/thoth/agents/` package structure
2. Implement `BaseAgent` following service patterns
3. Add agent support to `ServiceManager`
4. Create pipeline compatibility layer

#### Phase 2: API Integration (Week 3)
1. Add `/api/v2/agents` router
2. Implement SSE streaming for agent tasks
3. Add WebSocket support for real-time updates
4. Create agent management endpoints

#### Phase 3: Obsidian Plugin (Week 4-5)
1. Add agent types and interfaces
2. Create Agent Management Modal
3. Implement Agent Chat View
4. Add command palette commands
5. Update settings interface

#### Phase 4: Testing & Documentation (Week 6)
1. Add integration tests for multi-agent flows
2. Create end-to-end tests with Obsidian plugin
3. Update API documentation
4. Create user guide for agent creation

### 14.10 Backward Compatibility Checklist

- [ ] All existing API endpoints continue to work unchanged
- [ ] Pipeline processes PDFs identically when multi_agent=false
- [ ] Service Manager maintains existing interface
- [ ] No changes required to existing Obsidian workflows
- [ ] Configuration files remain compatible
- [ ] Database migrations are reversible
- [ ] Performance impact is minimal when disabled

### 14.11 Performance Considerations

```python
# Optimizations for multi-agent mode
class AgentPerformanceOptimizer:
    """Optimize agent execution for minimal overhead."""
    
    def __init__(self):
        self.agent_pool = AgentPool(max_size=10)
        self.task_queue = PriorityQueue()
        self.cache_manager = AgentCacheManager()
    
    async def optimize_execution(self, task: Task):
        """Optimize task execution."""
        
        # 1. Check cache for similar tasks
        if cached_result := await self.cache_manager.get(task):
            return cached_result
        
        # 2. Reuse agent instances from pool
        agent = await self.agent_pool.acquire(task.agent_type)
        
        try:
            # 3. Execute with performance monitoring
            with PerformanceMonitor() as monitor:
                result = await agent.execute(task)
                
            # 4. Cache successful results
            if result.status == "success":
                await self.cache_manager.set(task, result)
                
            return result
        finally:
            await self.agent_pool.release(agent)
```