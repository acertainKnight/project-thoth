-- ============================================================================
-- Browser-Based Discovery Source Workflows Migration
-- ============================================================================
-- Purpose: Add tables for browser automation workflows with parameterized search
-- Version: 002
-- Date: 2025-12-26
-- ============================================================================

-- ============================================================================
-- BROWSER_WORKFLOWS: Main workflow definition
-- ============================================================================

CREATE TABLE IF NOT EXISTS browser_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic Info
    name VARCHAR(200) NOT NULL,
    description TEXT,
    website_domain VARCHAR(200) NOT NULL,

    -- Access Configuration
    start_url TEXT NOT NULL,
    requires_authentication BOOLEAN DEFAULT FALSE,
    authentication_type VARCHAR(50), -- 'username_password', 'oauth', 'api_key', 'none'

    -- Extraction Configuration
    extraction_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    pagination_config JSONB DEFAULT NULL,

    -- Execution Settings
    max_articles_per_run INTEGER DEFAULT 100,
    timeout_seconds INTEGER DEFAULT 60,

    -- Status & Statistics
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'unknown',
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,
    total_articles_extracted INTEGER DEFAULT 0,
    average_execution_time_ms INTEGER,

    -- Timing
    last_executed_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT workflows_name_unique UNIQUE(name),
    CONSTRAINT valid_health_status CHECK (
        health_status IN ('unknown', 'healthy', 'degraded', 'down', 'maintenance')
    ),
    CONSTRAINT valid_auth_type CHECK (
        authentication_type IS NULL OR
        authentication_type IN ('username_password', 'oauth', 'api_key', 'none')
    ),
    CONSTRAINT valid_timeout CHECK (timeout_seconds > 0 AND timeout_seconds <= 600),
    CONSTRAINT valid_max_articles CHECK (max_articles_per_run > 0 AND max_articles_per_run <= 1000)
);

-- Indexes for browser_workflows
CREATE INDEX IF NOT EXISTS idx_workflows_domain ON browser_workflows(website_domain);
CREATE INDEX IF NOT EXISTS idx_workflows_active ON browser_workflows(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_workflows_health ON browser_workflows(health_status);
CREATE INDEX IF NOT EXISTS idx_workflows_name ON browser_workflows(name);
CREATE INDEX IF NOT EXISTS idx_workflows_last_executed ON browser_workflows(last_executed_at DESC NULLS LAST);

-- ============================================================================
-- WORKFLOW_ACTIONS: Recorded steps
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES browser_workflows(id) ON DELETE CASCADE,

    -- Action Details
    step_number INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL, -- 'navigate', 'click', 'type', 'wait', 'select', 'extract'

    -- Target Element
    target_selector JSONB DEFAULT NULL, -- {"css": "input#search", "xpath": "//input[@id='search']", "text": "Search"}
    target_description TEXT,

    -- Action Parameters
    action_value TEXT, -- Fixed value or parameter name
    is_parameterized BOOLEAN DEFAULT FALSE, -- TRUE if value comes from query
    parameter_name VARCHAR(100), -- e.g., "keywords", "date_range", "subject"

    -- Wait Conditions
    wait_condition VARCHAR(50), -- 'networkidle', 'load', 'domcontentloaded', 'selector', 'timeout'
    wait_timeout_ms INTEGER DEFAULT 30000,

    -- Error Handling
    retry_on_failure BOOLEAN DEFAULT TRUE,
    max_retries INTEGER DEFAULT 3,
    continue_on_error BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT workflow_actions_step UNIQUE(workflow_id, step_number),
    CONSTRAINT valid_action_type CHECK (
        action_type IN ('navigate', 'click', 'type', 'wait', 'select', 'extract', 'scroll')
    ),
    CONSTRAINT valid_wait_condition CHECK (
        wait_condition IS NULL OR
        wait_condition IN ('networkidle', 'load', 'domcontentloaded', 'selector', 'timeout')
    ),
    CONSTRAINT valid_wait_timeout CHECK (wait_timeout_ms > 0 AND wait_timeout_ms <= 120000),
    CONSTRAINT valid_max_retries CHECK (max_retries >= 0 AND max_retries <= 10),
    CONSTRAINT parameterized_requires_name CHECK (
        NOT is_parameterized OR parameter_name IS NOT NULL
    )
);

-- Indexes for workflow_actions
CREATE INDEX IF NOT EXISTS idx_actions_workflow ON workflow_actions(workflow_id, step_number);
CREATE INDEX IF NOT EXISTS idx_actions_parameterized ON workflow_actions(workflow_id)
    WHERE is_parameterized = TRUE;
CREATE INDEX IF NOT EXISTS idx_actions_type ON workflow_actions(action_type);

-- ============================================================================
-- WORKFLOW_SEARCH_CONFIG: Search and filter configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_search_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL UNIQUE REFERENCES browser_workflows(id) ON DELETE CASCADE,

    -- Search Type
    search_type VARCHAR(20) NOT NULL, -- 'simple', 'advanced', 'none'

    -- Search Input Configuration
    search_input_selector JSONB DEFAULT NULL, -- {"css": "input#search-box"}
    search_button_selector JSONB DEFAULT NULL, -- {"css": "button#search-btn"}
    keywords_format VARCHAR(50) DEFAULT 'space_separated', -- How to join keywords

    -- Filters Configuration
    filters JSONB DEFAULT '[]'::jsonb, -- Array of filter configurations

    -- Advanced Search Fields (for multi-field forms)
    advanced_fields JSONB DEFAULT NULL,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_search_type CHECK (
        search_type IN ('simple', 'advanced', 'none')
    ),
    CONSTRAINT valid_keywords_format CHECK (
        keywords_format IN ('space_separated', 'comma_separated', 'boolean_and', 'boolean_or', 'plus_separated')
    ),
    CONSTRAINT search_requires_selectors CHECK (
        search_type = 'none' OR
        (search_input_selector IS NOT NULL AND search_button_selector IS NOT NULL)
    )
);

-- Indexes for workflow_search_config
CREATE INDEX IF NOT EXISTS idx_search_config_workflow ON workflow_search_config(workflow_id);
CREATE INDEX IF NOT EXISTS idx_search_config_type ON workflow_search_config(search_type);

-- ============================================================================
-- WORKFLOW_CREDENTIALS: Encrypted authentication credentials
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL UNIQUE REFERENCES browser_workflows(id) ON DELETE CASCADE,

    -- Encrypted Credentials
    encrypted_credentials BYTEA NOT NULL,
    encryption_algorithm VARCHAR(50) DEFAULT 'fernet',

    -- Credential Type
    credential_type VARCHAR(50) NOT NULL, -- 'username_password', 'oauth', 'api_key'

    -- Session Management
    session_storage_state JSONB DEFAULT NULL, -- Playwright storage state (cookies, localStorage)
    session_valid_until TIMESTAMPTZ,

    -- Metadata
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Security Audit Trail
    access_log JSONB DEFAULT '[]'::jsonb, -- Array of access events

    -- Constraints
    CONSTRAINT valid_credential_type CHECK (
        credential_type IN ('username_password', 'oauth', 'api_key', 'token')
    ),
    CONSTRAINT valid_encryption_algorithm CHECK (
        encryption_algorithm IN ('fernet', 'aes-256-gcm', 'aes-256-cbc')
    )
);

-- Indexes for workflow_credentials
CREATE INDEX IF NOT EXISTS idx_credentials_workflow ON workflow_credentials(workflow_id);
CREATE INDEX IF NOT EXISTS idx_credentials_last_used ON workflow_credentials(last_used_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_credentials_session_valid ON workflow_credentials(session_valid_until)
    WHERE session_valid_until IS NOT NULL;

-- ============================================================================
-- WORKFLOW_EXECUTIONS: Execution logs with parameters
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES browser_workflows(id) ON DELETE CASCADE,

    -- Execution Details
    status VARCHAR(20) NOT NULL, -- 'pending', 'running', 'success', 'failed', 'cancelled'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Parameters Used
    execution_parameters JSONB DEFAULT '{}'::jsonb, -- {"keywords": ["neural", "pathways"], "date_range": "last_24h"}

    -- Results
    articles_extracted INTEGER DEFAULT 0,
    pages_visited INTEGER DEFAULT 0,

    -- Error Information
    error_message TEXT,
    error_step_number INTEGER,
    error_screenshot_url TEXT,
    error_type VARCHAR(50), -- 'timeout', 'selector_not_found', 'authentication_failed', 'extraction_failed'

    -- Execution Metadata
    execution_log JSONB DEFAULT '[]'::jsonb, -- Array of execution events
    browser_console_logs JSONB DEFAULT '[]'::jsonb, -- Array of browser console messages

    -- Trigger
    triggered_by VARCHAR(50), -- 'schedule', 'manual', 'query', 'api'
    triggered_by_query_id UUID, -- Link to research question (if triggered by query)

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_execution_status CHECK (
        status IN ('pending', 'running', 'success', 'failed', 'cancelled')
    ),
    CONSTRAINT valid_triggered_by CHECK (
        triggered_by IN ('schedule', 'manual', 'query', 'api', 'test')
    ),
    CONSTRAINT valid_error_type CHECK (
        error_type IS NULL OR
        error_type IN ('timeout', 'selector_not_found', 'authentication_failed',
                       'extraction_failed', 'network_error', 'unknown')
    ),
    CONSTRAINT completed_requires_duration CHECK (
        completed_at IS NULL OR duration_ms IS NOT NULL
    )
);

-- Indexes for workflow_executions
CREATE INDEX IF NOT EXISTS idx_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_started ON workflow_executions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_query ON workflow_executions(triggered_by_query_id)
    WHERE triggered_by_query_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_executions_triggered_by ON workflow_executions(triggered_by);
CREATE INDEX IF NOT EXISTS idx_executions_workflow_status ON workflow_executions(workflow_id, status, started_at DESC);

-- ============================================================================
-- TRIGGERS: Auto-update timestamps and maintain statistics
-- ============================================================================

-- Update updated_at timestamp on browser_workflows
CREATE OR REPLACE FUNCTION update_browser_workflows_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER browser_workflows_updated_at
    BEFORE UPDATE ON browser_workflows
    FOR EACH ROW
    EXECUTE FUNCTION update_browser_workflows_updated_at();

-- Update updated_at timestamp on workflow_search_config
CREATE OR REPLACE FUNCTION update_workflow_search_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workflow_search_config_updated_at
    BEFORE UPDATE ON workflow_search_config
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_search_config_updated_at();

-- Update updated_at timestamp on workflow_credentials
CREATE OR REPLACE FUNCTION update_workflow_credentials_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workflow_credentials_updated_at
    BEFORE UPDATE ON workflow_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_credentials_updated_at();

-- Update workflow statistics when execution completes
CREATE OR REPLACE FUNCTION update_workflow_execution_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE browser_workflows
        SET
            total_executions = total_executions + 1,
            last_executed_at = NEW.started_at
        WHERE id = NEW.workflow_id;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.status != NEW.status THEN
        IF NEW.status = 'success' THEN
            UPDATE browser_workflows
            SET
                successful_executions = successful_executions + 1,
                total_articles_extracted = total_articles_extracted + COALESCE(NEW.articles_extracted, 0),
                last_success_at = NEW.completed_at,
                health_status = 'healthy',
                average_execution_time_ms = CASE
                    WHEN average_execution_time_ms IS NULL THEN NEW.duration_ms
                    ELSE (average_execution_time_ms * (successful_executions) + NEW.duration_ms) / (successful_executions + 1)
                END
            WHERE id = NEW.workflow_id;
        ELSIF NEW.status = 'failed' THEN
            UPDATE browser_workflows
            SET
                failed_executions = failed_executions + 1,
                last_failure_at = NEW.completed_at,
                health_status = CASE
                    WHEN failed_executions + 1 >= 3 THEN 'down'
                    WHEN failed_executions + 1 >= 2 THEN 'degraded'
                    ELSE health_status
                END
            WHERE id = NEW.workflow_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workflow_executions_stats
    AFTER INSERT OR UPDATE ON workflow_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_workflow_execution_stats();

-- Auto-calculate duration when execution completes
CREATE OR REPLACE FUNCTION calculate_execution_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND NEW.duration_ms IS NULL THEN
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workflow_executions_duration
    BEFORE UPDATE ON workflow_executions
    FOR EACH ROW
    WHEN (NEW.completed_at IS NOT NULL AND OLD.completed_at IS NULL)
    EXECUTE FUNCTION calculate_execution_duration();

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to get active workflows
CREATE OR REPLACE FUNCTION get_active_workflows()
RETURNS TABLE (
    workflow_id UUID,
    name VARCHAR(200),
    website_domain VARCHAR(200),
    health_status VARCHAR(20),
    total_executions INTEGER,
    success_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        bw.id,
        bw.name,
        bw.website_domain,
        bw.health_status,
        bw.total_executions,
        CASE
            WHEN bw.total_executions > 0 THEN
                ROUND((bw.successful_executions::NUMERIC / bw.total_executions::NUMERIC) * 100, 2)
            ELSE 0
        END
    FROM browser_workflows bw
    WHERE bw.is_active = TRUE
    ORDER BY bw.name;
END;
$$ LANGUAGE plpgsql;

-- Function to get workflow execution summary
CREATE OR REPLACE FUNCTION get_workflow_execution_summary(
    p_workflow_id UUID,
    p_days INTEGER DEFAULT 7
)
RETURNS TABLE (
    total_executions BIGINT,
    successful_executions BIGINT,
    failed_executions BIGINT,
    avg_duration_ms NUMERIC,
    total_articles_extracted BIGINT,
    success_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE status = 'success'),
        COUNT(*) FILTER (WHERE status = 'failed'),
        ROUND(AVG(duration_ms)::NUMERIC, 2),
        SUM(articles_extracted),
        CASE
            WHEN COUNT(*) > 0 THEN
                ROUND((COUNT(*) FILTER (WHERE status = 'success')::NUMERIC / COUNT(*)::NUMERIC) * 100, 2)
            ELSE 0
        END
    FROM workflow_executions
    WHERE workflow_id = p_workflow_id
      AND started_at >= NOW() - (p_days || ' days')::INTERVAL;
END;
$$ LANGUAGE plpgsql;

-- Function to check if workflow needs session refresh
CREATE OR REPLACE FUNCTION needs_session_refresh(p_workflow_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    session_valid TIMESTAMPTZ;
BEGIN
    SELECT session_valid_until INTO session_valid
    FROM workflow_credentials
    WHERE workflow_id = p_workflow_id;

    RETURN session_valid IS NULL OR session_valid < NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to mark workflow as requiring maintenance
CREATE OR REPLACE FUNCTION mark_workflow_maintenance(
    p_workflow_id UUID,
    p_reason TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE browser_workflows
    SET
        health_status = 'maintenance',
        is_active = FALSE,
        updated_at = NOW()
    WHERE id = p_workflow_id;

    -- Log the maintenance action
    INSERT INTO workflow_executions (
        workflow_id,
        status,
        triggered_by,
        error_message,
        started_at,
        completed_at
    ) VALUES (
        p_workflow_id,
        'cancelled',
        'manual',
        'Workflow marked for maintenance: ' || COALESCE(p_reason, 'No reason provided'),
        NOW(),
        NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS: Convenient access patterns
-- ============================================================================

-- View: Workflow with search configuration
CREATE OR REPLACE VIEW workflows_with_search AS
SELECT
    bw.*,
    wsc.search_type,
    wsc.keywords_format,
    wsc.filters
FROM browser_workflows bw
LEFT JOIN workflow_search_config wsc ON bw.id = wsc.workflow_id;

-- View: Recent workflow executions
CREATE OR REPLACE VIEW recent_workflow_executions AS
SELECT
    we.*,
    bw.name as workflow_name,
    bw.website_domain
FROM workflow_executions we
JOIN browser_workflows bw ON we.workflow_id = bw.id
WHERE we.started_at >= NOW() - INTERVAL '7 days'
ORDER BY we.started_at DESC;

-- View: Workflow health status
CREATE OR REPLACE VIEW workflow_health_status AS
SELECT
    bw.id,
    bw.name,
    bw.website_domain,
    bw.health_status,
    bw.is_active,
    bw.total_executions,
    bw.successful_executions,
    bw.failed_executions,
    CASE
        WHEN bw.total_executions > 0 THEN
            ROUND((bw.successful_executions::NUMERIC / bw.total_executions::NUMERIC) * 100, 2)
        ELSE 0
    END as success_rate,
    bw.last_executed_at,
    bw.last_success_at,
    bw.last_failure_at,
    CASE
        WHEN bw.last_executed_at IS NULL THEN 'never_run'
        WHEN bw.last_executed_at < NOW() - INTERVAL '7 days' THEN 'stale'
        WHEN bw.health_status = 'down' THEN 'down'
        WHEN bw.health_status = 'degraded' THEN 'degraded'
        ELSE 'active'
    END as overall_status
FROM browser_workflows bw;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE browser_workflows IS 'Main workflow definitions for browser automation';
COMMENT ON TABLE workflow_actions IS 'Individual recorded steps in a workflow';
COMMENT ON TABLE workflow_search_config IS 'Search and filter configuration for parameterized workflows';
COMMENT ON TABLE workflow_credentials IS 'Encrypted authentication credentials and session state';
COMMENT ON TABLE workflow_executions IS 'Execution logs with parameters and results';

COMMENT ON COLUMN browser_workflows.extraction_rules IS 'JSONB configuration for extracting article metadata from pages';
COMMENT ON COLUMN workflow_actions.is_parameterized IS 'TRUE if this action receives values from query parameters';
COMMENT ON COLUMN workflow_search_config.filters IS 'Array of filter configurations with selectors and parameter mappings';
COMMENT ON COLUMN workflow_credentials.session_storage_state IS 'Playwright storage state (cookies, localStorage) for session reuse';
COMMENT ON COLUMN workflow_executions.execution_parameters IS 'Query parameters passed to this execution (keywords, date_range, etc.)';

-- ============================================================================
-- INTEGRATION: Link to available_sources table
-- ============================================================================

-- Add foreign key to existing available_sources table
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'available_sources') THEN
        -- Add column if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'available_sources'
            AND column_name = 'browser_workflow_id'
        ) THEN
            ALTER TABLE available_sources
            ADD COLUMN browser_workflow_id UUID REFERENCES browser_workflows(id) ON DELETE SET NULL;

            CREATE INDEX IF NOT EXISTS idx_sources_workflow
                ON available_sources(browser_workflow_id)
                WHERE browser_workflow_id IS NOT NULL;

            COMMENT ON COLUMN available_sources.browser_workflow_id IS 'Link to browser workflow for browser-based discovery sources';

            RAISE NOTICE 'Added browser_workflow_id column to available_sources';
        ELSE
            RAISE NOTICE 'Column browser_workflow_id already exists in available_sources';
        END IF;
    ELSE
        RAISE NOTICE 'Table available_sources does not exist yet - skipping foreign key addition';
    END IF;
END $$;

-- ============================================================================
-- SAMPLE DATA: Example workflow for testing
-- ============================================================================

-- Insert sample workflow (commented out - uncomment for testing)
/*
DO $$
DECLARE
    sample_workflow_id UUID;
BEGIN
    -- Insert sample workflow
    INSERT INTO browser_workflows (
        name,
        description,
        website_domain,
        start_url,
        requires_authentication,
        authentication_type,
        extraction_rules,
        max_articles_per_run,
        is_active
    ) VALUES (
        'Sample Journal Workflow',
        'Example workflow for testing browser discovery',
        'example.com',
        'https://example.com/search',
        FALSE,
        'none',
        '{"title": {"selector": {"css": "h2.article-title"}}, "authors": {"selector": {"css": ".author-list"}}}',
        50,
        FALSE
    ) RETURNING id INTO sample_workflow_id;

    -- Insert sample search config
    INSERT INTO workflow_search_config (
        workflow_id,
        search_type,
        search_input_selector,
        search_button_selector,
        keywords_format,
        filters
    ) VALUES (
        sample_workflow_id,
        'simple',
        '{"css": "input#search-box"}',
        '{"css": "button#search-submit"}',
        'space_separated',
        '[{"name": "date_range", "type": "dropdown", "selector": {"css": "select#date-filter"}, "parameter": "date_range"}]'
    );

    RAISE NOTICE 'Sample workflow created with ID: %', sample_workflow_id;
END $$;
*/

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
