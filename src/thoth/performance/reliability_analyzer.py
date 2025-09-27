"""
Reliability and error pattern analysis for Thoth system.

This module provides comprehensive analysis of system reliability,
error patterns, failure modes, and recovery strategies to improve
system stability and user experience.
"""

import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.performance.metrics_collector import MetricsCollector
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import ThothConfig


class FailureSeverity(Enum):
    """Severity levels for system failures."""

    CRITICAL = 'critical'  # System unavailable
    HIGH = 'high'  # Major functionality impaired
    MEDIUM = 'medium'  # Minor functionality issues
    LOW = 'low'  # Performance degradation


class FailureCategory(Enum):
    """Categories of system failures."""

    API_FAILURE = 'api_failure'
    DATABASE_FAILURE = 'database_failure'
    PROCESSING_FAILURE = 'processing_failure'
    NETWORK_FAILURE = 'network_failure'
    AUTHENTICATION_FAILURE = 'authentication_failure'
    RESOURCE_EXHAUSTION = 'resource_exhaustion'
    CONFIGURATION_ERROR = 'configuration_error'
    DATA_CORRUPTION = 'data_corruption'
    TIMEOUT = 'timeout'
    RATE_LIMITING = 'rate_limiting'


@dataclass
class ErrorEvent:
    """Individual error event record."""

    event_id: str
    timestamp: datetime
    service: str
    error_type: str
    error_message: str
    stack_trace: str | None = None

    # Classification
    category: FailureCategory | None = None
    severity: FailureSeverity | None = None

    # Context
    user_id: str | None = None
    request_id: str | None = None
    operation: str | None = None
    input_data_size: int | None = None

    # Recovery information
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_time_ms: float | None = None

    # System state
    system_load: float | None = None
    memory_usage: float | None = None
    concurrent_operations: int | None = None


@dataclass
class FailurePattern:
    """Pattern of related failures."""

    pattern_id: str
    pattern_name: str
    error_signature: str
    occurrences: int = 0
    first_occurrence: datetime | None = None
    last_occurrence: datetime | None = None

    # Pattern characteristics
    affected_services: set[str] = field(default_factory=set)
    common_triggers: list[str] = field(default_factory=list)
    failure_rate: float = 0.0

    # Impact analysis
    avg_recovery_time_ms: float = 0.0
    user_impact_score: float = 0.0
    system_impact_score: float = 0.0

    # Prevention strategies
    suggested_fixes: list[str] = field(default_factory=list)
    prevention_strategies: list[str] = field(default_factory=list)


@dataclass
class ReliabilityMetrics:
    """Comprehensive system reliability metrics."""

    analysis_period: str
    total_errors: int = 0
    unique_error_types: int = 0

    # Availability metrics
    uptime_percentage: float = 0.0
    mean_time_between_failures_hours: float = 0.0
    mean_time_to_recovery_ms: float = 0.0

    # Error distribution
    error_by_category: dict[FailureCategory, int] = field(default_factory=dict)
    error_by_severity: dict[FailureSeverity, int] = field(default_factory=dict)
    error_by_service: dict[str, int] = field(default_factory=dict)

    # Failure patterns
    top_failure_patterns: list[FailurePattern] = field(default_factory=list)
    recurring_issues: list[str] = field(default_factory=list)

    # Recovery metrics
    recovery_success_rate: float = 0.0
    avg_recovery_time_ms: float = 0.0
    automated_recovery_rate: float = 0.0

    # Trend analysis
    error_trend: str = 'stable'  # increasing, decreasing, stable
    reliability_trend: str = 'stable'

    # Performance correlation
    error_correlation_with_load: float = 0.0
    error_correlation_with_memory: float = 0.0
    peak_error_hours: list[int] = field(default_factory=list)


class ReliabilityAnalyzer:
    """
    Comprehensive reliability and error pattern analysis system.

    Provides:
    - Real-time error tracking and classification
    - Pattern detection and root cause analysis
    - Reliability metrics and trend analysis
    - Automated recovery recommendations
    - Proactive failure prediction
    """

    def __init__(
        self,
        config: ThothConfig,
        service_manager: ServiceManager,
        metrics_collector: MetricsCollector | None = None,
    ):
        """
        Initialize the reliability analyzer.

        Args:
            config: Thoth configuration
            service_manager: ServiceManager instance
            metrics_collector: Optional metrics collector for correlation analysis
        """
        self.config = config
        self.service_manager = service_manager
        self.metrics_collector = metrics_collector

        # Error tracking
        self.error_events: list[ErrorEvent] = []
        self.failure_patterns: dict[str, FailurePattern] = {}

        # Pattern detection
        self.error_signatures: dict[str, int] = {}
        self.temporal_patterns: dict[str, list[datetime]] = defaultdict(list)

        # Analysis storage
        self.reliability_dir = config.workspace_dir / 'reliability'
        self.reliability_dir.mkdir(exist_ok=True)

        # Baseline metrics
        self.baseline_reliability: ReliabilityMetrics | None = None

        logger.info('ReliabilityAnalyzer initialized')

    def record_error(
        self,
        service: str,
        error_type: str,
        error_message: str,
        stack_trace: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        operation: str | None = None,
        input_data_size: int | None = None,
    ) -> str:
        """
        Record a new error event for analysis.

        Args:
            service: Service where error occurred
            error_type: Type/class of error
            error_message: Error message
            stack_trace: Optional stack trace
            user_id: Optional user identifier
            request_id: Optional request identifier
            operation: Optional operation being performed
            input_data_size: Optional size of input data

        Returns:
            str: Error event ID
        """
        event_id = f'error_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}'

        # Get current system state if metrics collector available
        system_load = None
        memory_usage = None
        concurrent_ops = None

        if self.metrics_collector:
            current_metrics = self.metrics_collector.current_metrics
            system_load = current_metrics.cpu_usage
            memory_usage = current_metrics.memory_percent
            concurrent_ops = len(self.metrics_collector._active_operations)

        error_event = ErrorEvent(
            event_id=event_id,
            timestamp=datetime.now(),
            service=service,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            user_id=user_id,
            request_id=request_id,
            operation=operation,
            input_data_size=input_data_size,
            system_load=system_load,
            memory_usage=memory_usage,
            concurrent_operations=concurrent_ops,
        )

        # Classify error
        error_event.category = self._classify_error_category(error_message, error_type)
        error_event.severity = self._classify_error_severity(
            error_message, error_type, service
        )

        # Store error event
        self.error_events.append(error_event)

        # Update pattern tracking
        self._update_pattern_tracking(error_event)

        logger.warning(
            f'Recorded error: {service}:{error_type} '
            f'({error_event.category.value if error_event.category else "unknown"}, '
            f'{error_event.severity.value if error_event.severity else "unknown"})'
        )

        return event_id

    def record_recovery_attempt(
        self, event_id: str, recovery_successful: bool, recovery_time_ms: float
    ) -> None:
        """
        Record a recovery attempt for an error event.

        Args:
            event_id: Error event ID
            recovery_successful: Whether recovery was successful
            recovery_time_ms: Time taken for recovery in milliseconds
        """
        # Find the error event
        error_event = None
        for event in self.error_events:
            if event.event_id == event_id:
                error_event = event
                break

        if not error_event:
            logger.warning(f'Unknown error event ID: {event_id}')
            return

        error_event.recovery_attempted = True
        error_event.recovery_successful = recovery_successful
        error_event.recovery_time_ms = recovery_time_ms

        logger.info(
            f'Recovery {"successful" if recovery_successful else "failed"} '
            f'for {event_id} in {recovery_time_ms:.1f}ms'
        )

    def _classify_error_category(
        self, error_message: str, error_type: str
    ) -> FailureCategory:
        """Classify error into appropriate category."""
        message_lower = error_message.lower()
        type_lower = error_type.lower()

        # API-related errors
        if any(
            term in message_lower
            for term in ['api', 'http', 'status code', 'request failed']
        ):
            return FailureCategory.API_FAILURE

        # Database/storage errors
        if any(
            term in message_lower
            for term in ['database', 'chroma', 'index', 'vector', 'connection']
        ):
            return FailureCategory.DATABASE_FAILURE

        # Network errors
        if any(
            term in message_lower
            for term in ['network', 'connection', 'timeout', 'unreachable']
        ):
            return FailureCategory.NETWORK_FAILURE

        # Authentication errors
        if any(
            term in message_lower
            for term in ['auth', 'unauthorized', 'forbidden', 'api key', 'token']
        ):
            return FailureCategory.AUTHENTICATION_FAILURE

        # Resource exhaustion
        if any(
            term in message_lower
            for term in ['memory', 'disk space', 'quota', 'limit exceeded']
        ):
            return FailureCategory.RESOURCE_EXHAUSTION

        # Rate limiting
        if any(
            term in message_lower
            for term in ['rate limit', 'too many requests', 'throttle']
        ):
            return FailureCategory.RATE_LIMITING

        # Timeouts
        if any(term in message_lower for term in ['timeout', 'timed out']):
            return FailureCategory.TIMEOUT

        # Processing errors
        if any(
            term in message_lower
            for term in ['processing', 'parse', 'format', 'invalid']
        ):
            return FailureCategory.PROCESSING_FAILURE

        # Configuration errors
        if any(term in message_lower for term in ['config', 'setting', 'parameter']):
            return FailureCategory.CONFIGURATION_ERROR

        # Data corruption
        if any(
            term in message_lower for term in ['corrupt', 'invalid data', 'malformed']
        ):
            return FailureCategory.DATA_CORRUPTION

        return FailureCategory.PROCESSING_FAILURE  # Default

    def _classify_error_severity(
        self, error_message: str, error_type: str, service: str
    ) -> FailureSeverity:
        """Classify error severity based on impact."""
        message_lower = error_message.lower()

        # Critical errors - system unavailable
        if any(
            term in message_lower
            for term in [
                'system down',
                'service unavailable',
                'fatal error',
                'critical failure',
                'database unreachable',
            ]
        ):
            return FailureSeverity.CRITICAL

        # High severity - major functionality impaired
        if any(
            term in message_lower
            for term in [
                'authentication failed',
                'permission denied',
                'data corruption',
                'out of memory',
            ]
        ) or service in ['llm', 'rag', 'processing']:
            return FailureSeverity.HIGH

        # Medium severity - some functionality affected
        if any(
            term in message_lower
            for term in [
                'timeout',
                'rate limit',
                'temporary failure',
                'retry limit exceeded',
            ]
        ):
            return FailureSeverity.MEDIUM

        # Low severity - performance issues
        return FailureSeverity.LOW

    def _update_pattern_tracking(self, error_event: ErrorEvent) -> None:
        """Update failure pattern tracking with new error event."""
        # Create error signature for pattern matching
        signature = self._create_error_signature(error_event)

        # Update signature tracking
        self.error_signatures[signature] = self.error_signatures.get(signature, 0) + 1

        # Update temporal patterns
        self.temporal_patterns[signature].append(error_event.timestamp)

        # Update or create failure pattern
        if signature in self.failure_patterns:
            pattern = self.failure_patterns[signature]
            pattern.occurrences += 1
            pattern.last_occurrence = error_event.timestamp
            pattern.affected_services.add(error_event.service)
        else:
            pattern = FailurePattern(
                pattern_id=f'pattern_{len(self.failure_patterns)}',
                pattern_name=self._generate_pattern_name(signature, error_event),
                error_signature=signature,
                occurrences=1,
                first_occurrence=error_event.timestamp,
                last_occurrence=error_event.timestamp,
                affected_services={error_event.service},
            )
            self.failure_patterns[signature] = pattern

    def _create_error_signature(self, error_event: ErrorEvent) -> str:
        """Create a signature for error pattern matching."""
        # Normalize error message for pattern matching
        normalized_message = self._normalize_error_message(error_event.error_message)

        # Create signature from key components
        signature_parts = [
            error_event.service,
            error_event.error_type,
            normalized_message,
            error_event.category.value if error_event.category else 'unknown',
        ]

        return '|'.join(signature_parts)

    def _normalize_error_message(self, error_message: str) -> str:
        """Normalize error message for pattern matching."""
        # Remove specific values that vary between instances
        normalized = error_message.lower()

        # Replace numbers with placeholder
        normalized = re.sub(r'\b\d+\b', 'N', normalized)

        # Replace file paths with placeholder
        normalized = re.sub(r'[/\\][^\s]+', '/PATH', normalized)

        # Replace URLs with placeholder
        normalized = re.sub(r'https?://[^\s]+', 'URL', normalized)

        # Replace UUIDs with placeholder
        normalized = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            'UUID',
            normalized,
        )

        # Truncate very long messages
        if len(normalized) > 200:
            normalized = normalized[:200] + '...'

        return normalized

    def _generate_pattern_name(self, signature: str, error_event: ErrorEvent) -> str:
        """Generate human-readable name for failure pattern."""
        service = error_event.service
        category = error_event.category.value if error_event.category else 'unknown'

        # Extract key terms from error message
        message_words = error_event.error_message.lower().split()
        key_terms = [
            word
            for word in message_words
            if len(word) > 4
            and word not in ['error', 'failed', 'exception', 'cannot', 'unable']
        ]

        if key_terms:
            key_term = key_terms[0]
            return f'{service}_{category}_{key_term}'
        else:
            return f'{service}_{category}_error'

    def analyze_reliability(self, time_window_hours: int = 24) -> ReliabilityMetrics:
        """
        Analyze system reliability over specified time window.

        Args:
            time_window_hours: Time window for analysis

        Returns:
            ReliabilityMetrics: Comprehensive reliability analysis
        """
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

        # Filter events in time window
        relevant_events = [
            event for event in self.error_events if event.timestamp > cutoff_time
        ]

        metrics = ReliabilityMetrics(analysis_period=f'{time_window_hours} hours')

        if not relevant_events:
            metrics.uptime_percentage = 100.0
            return metrics

        # Basic error counts
        metrics.total_errors = len(relevant_events)
        metrics.unique_error_types = len(
            set(event.error_type for event in relevant_events)
        )

        # Error distribution analysis
        metrics.error_by_category = self._analyze_error_distribution_by_category(
            relevant_events
        )
        metrics.error_by_severity = self._analyze_error_distribution_by_severity(
            relevant_events
        )
        metrics.error_by_service = self._analyze_error_distribution_by_service(
            relevant_events
        )

        # Availability metrics
        metrics.uptime_percentage = self._calculate_uptime_percentage(
            relevant_events, time_window_hours
        )
        metrics.mean_time_between_failures_hours = self._calculate_mtbf(
            relevant_events, time_window_hours
        )
        metrics.mean_time_to_recovery_ms = self._calculate_mttr(relevant_events)

        # Recovery metrics
        recovery_events = [e for e in relevant_events if e.recovery_attempted]
        if recovery_events:
            successful_recoveries = [
                e for e in recovery_events if e.recovery_successful
            ]
            metrics.recovery_success_rate = len(successful_recoveries) / len(
                recovery_events
            )

            recovery_times = [
                e.recovery_time_ms for e in recovery_events if e.recovery_time_ms
            ]
            if recovery_times:
                metrics.avg_recovery_time_ms = statistics.mean(recovery_times)

        # Pattern analysis
        metrics.top_failure_patterns = self._analyze_top_failure_patterns()
        metrics.recurring_issues = self._identify_recurring_issues(relevant_events)

        # Trend analysis
        metrics.error_trend = self._analyze_error_trend(time_window_hours)
        metrics.reliability_trend = self._analyze_reliability_trend()

        # Correlation analysis with system metrics
        if self.metrics_collector:
            metrics.error_correlation_with_load = self._analyze_error_load_correlation(
                relevant_events
            )
            metrics.error_correlation_with_memory = (
                self._analyze_error_memory_correlation(relevant_events)
            )

        # Peak error analysis
        metrics.peak_error_hours = self._analyze_peak_error_hours(relevant_events)

        # Store as baseline
        self.baseline_reliability = metrics

        return metrics

    def _analyze_error_distribution_by_category(
        self, events: list[ErrorEvent]
    ) -> dict[FailureCategory, int]:
        """Analyze error distribution by category."""
        distribution = {}
        for event in events:
            if event.category:
                distribution[event.category] = distribution.get(event.category, 0) + 1
        return distribution

    def _analyze_error_distribution_by_severity(
        self, events: list[ErrorEvent]
    ) -> dict[FailureSeverity, int]:
        """Analyze error distribution by severity."""
        distribution = {}
        for event in events:
            if event.severity:
                distribution[event.severity] = distribution.get(event.severity, 0) + 1
        return distribution

    def _analyze_error_distribution_by_service(
        self, events: list[ErrorEvent]
    ) -> dict[str, int]:
        """Analyze error distribution by service."""
        distribution = Counter(event.service for event in events)
        return dict(distribution.most_common(10))

    def _calculate_uptime_percentage(
        self, events: list[ErrorEvent], time_window_hours: int
    ) -> float:
        """Calculate system uptime percentage."""
        # Count critical and high severity errors as downtime
        downtime_events = [
            event
            for event in events
            if event.severity in [FailureSeverity.CRITICAL, FailureSeverity.HIGH]
        ]

        if not downtime_events:
            return 100.0

        # Estimate downtime (simplified calculation)
        # Assume each critical/high error causes 1 minute of downtime
        estimated_downtime_minutes = len(downtime_events) * 1
        total_minutes = time_window_hours * 60

        uptime_percentage = (
            (total_minutes - estimated_downtime_minutes) / total_minutes
        ) * 100
        return max(0.0, min(100.0, uptime_percentage))

    def _calculate_mtbf(
        self, events: list[ErrorEvent], time_window_hours: int
    ) -> float:
        """Calculate Mean Time Between Failures."""
        if len(events) <= 1:
            return time_window_hours

        return time_window_hours / len(events)

    def _calculate_mttr(self, events: list[ErrorEvent]) -> float:
        """Calculate Mean Time To Recovery."""
        recovery_times = [
            event.recovery_time_ms
            for event in events
            if event.recovery_attempted and event.recovery_time_ms is not None
        ]

        if not recovery_times:
            return 0.0

        return statistics.mean(recovery_times)

    def _analyze_top_failure_patterns(self) -> list[FailurePattern]:
        """Analyze top failure patterns."""
        # Sort patterns by occurrence count
        sorted_patterns = sorted(
            self.failure_patterns.values(), key=lambda p: p.occurrences, reverse=True
        )

        # Update pattern metrics
        for pattern in sorted_patterns[:10]:  # Top 10 patterns
            self._update_pattern_metrics(pattern)

        return sorted_patterns[:5]  # Return top 5

    def _update_pattern_metrics(self, pattern: FailurePattern) -> None:
        """Update metrics for a failure pattern."""
        signature = pattern.error_signature
        timestamps = self.temporal_patterns.get(signature, [])

        if len(timestamps) > 1:
            # Calculate failure rate (failures per hour)
            time_span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
            pattern.failure_rate = pattern.occurrences / max(time_span_hours, 1)

        # Find related events for recovery analysis
        related_events = [
            event
            for event in self.error_events
            if self._create_error_signature(event) == signature
        ]

        recovery_times = [
            event.recovery_time_ms
            for event in related_events
            if event.recovery_time_ms is not None
        ]

        if recovery_times:
            pattern.avg_recovery_time_ms = statistics.mean(recovery_times)

        # Generate suggestions
        pattern.suggested_fixes = self._generate_pattern_fixes(pattern)
        pattern.prevention_strategies = self._generate_prevention_strategies(pattern)

    def _generate_pattern_fixes(self, pattern: FailurePattern) -> list[str]:
        """Generate suggested fixes for failure pattern."""
        fixes = []
        signature_parts = pattern.error_signature.split('|')

        if len(signature_parts) >= 4:
            service, error_type, message, category = signature_parts[:4]

            if 'api' in category:
                fixes.extend(
                    [
                        'Implement exponential backoff retry logic',
                        'Add circuit breaker pattern',
                        'Monitor API rate limits and quotas',
                    ]
                )

            elif 'timeout' in category:
                fixes.extend(
                    [
                        'Increase timeout values for slow operations',
                        'Implement async processing for long-running tasks',
                        'Add progress indicators for user-facing operations',
                    ]
                )

            elif 'database' in category:
                fixes.extend(
                    [
                        'Optimize database queries and indexes',
                        'Implement connection pooling',
                        'Add database health checks',
                    ]
                )

            elif 'authentication' in category:
                fixes.extend(
                    [
                        'Implement token refresh logic',
                        'Add API key rotation mechanism',
                        'Monitor authentication service health',
                    ]
                )

        return fixes

    def _generate_prevention_strategies(self, pattern: FailurePattern) -> list[str]:
        """Generate prevention strategies for failure pattern."""
        strategies = []

        if pattern.failure_rate > 1.0:  # More than 1 failure per hour
            strategies.append('Implement proactive monitoring and alerting')

        if pattern.avg_recovery_time_ms > 10000:  # More than 10 seconds
            strategies.append('Develop automated recovery procedures')

        if len(pattern.affected_services) > 1:
            strategies.append('Implement service isolation and fallback mechanisms')

        strategies.extend(
            [
                'Add comprehensive logging and diagnostics',
                'Implement health checks and monitoring',
                'Develop runbook for manual intervention',
            ]
        )

        return strategies

    def _identify_recurring_issues(self, events: list[ErrorEvent]) -> list[str]:
        """Identify recurring issues from error events."""
        # Group similar errors
        error_groups = defaultdict(list)
        for event in events:
            key = f'{event.service}:{event.error_type}'
            error_groups[key].append(event)

        # Find issues that occur frequently
        recurring = []
        for key, group_events in error_groups.items():
            if len(group_events) >= 3:  # At least 3 occurrences
                recurring.append(f'{key} ({len(group_events)} occurrences)')

        return sorted(recurring)

    def _analyze_error_trend(self, time_window_hours: int) -> str:
        """Analyze error trend over time."""
        if len(self.error_events) < 10:
            return 'insufficient_data'

        # Compare error rates in first and second half of time window
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        midpoint = cutoff_time + timedelta(hours=time_window_hours / 2)

        first_half_errors = len(
            [
                event
                for event in self.error_events
                if cutoff_time <= event.timestamp <= midpoint
            ]
        )

        second_half_errors = len(
            [event for event in self.error_events if midpoint < event.timestamp]
        )

        if second_half_errors > first_half_errors * 1.2:
            return 'increasing'
        elif second_half_errors < first_half_errors * 0.8:
            return 'decreasing'
        else:
            return 'stable'

    def _analyze_reliability_trend(self) -> str:
        """Analyze overall reliability trend."""
        # This would compare current metrics with historical baselines
        # For now, return based on recent error patterns
        if not self.failure_patterns:
            return 'stable'

        recent_failures = sum(
            1
            for pattern in self.failure_patterns.values()
            if pattern.last_occurrence
            and pattern.last_occurrence > datetime.now() - timedelta(hours=1)
        )

        if recent_failures > 5:
            return 'degrading'
        elif recent_failures == 0:
            return 'improving'
        else:
            return 'stable'

    def _analyze_error_load_correlation(self, events: list[ErrorEvent]) -> float:
        """Analyze correlation between errors and system load."""
        if not events:
            return 0.0

        error_loads = [
            event.system_load for event in events if event.system_load is not None
        ]
        if len(error_loads) < 5:
            return 0.0

        # Simple correlation calculation
        mean_load = statistics.mean(error_loads)
        high_load_errors = sum(1 for load in error_loads if load > mean_load * 1.2)

        return high_load_errors / len(error_loads)

    def _analyze_error_memory_correlation(self, events: list[ErrorEvent]) -> float:
        """Analyze correlation between errors and memory usage."""
        if not events:
            return 0.0

        memory_values = [
            event.memory_usage for event in events if event.memory_usage is not None
        ]
        if len(memory_values) < 5:
            return 0.0

        # Simple correlation calculation
        mean_memory = statistics.mean(memory_values)
        high_memory_errors = sum(1 for mem in memory_values if mem > mean_memory * 1.2)

        return high_memory_errors / len(memory_values)

    def _analyze_peak_error_hours(self, events: list[ErrorEvent]) -> list[int]:
        """Analyze peak error hours."""
        hourly_counts = defaultdict(int)
        for event in events:
            hourly_counts[event.timestamp.hour] += 1

        # Get top 3 hours with most errors
        sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
        return [hour for hour, count in sorted_hours[:3]]

    def generate_reliability_report(
        self, output_path: Path | None = None
    ) -> dict[str, Any]:
        """
        Generate comprehensive reliability report.

        Args:
            output_path: Optional path to save report

        Returns:
            Dict containing reliability report
        """
        metrics = self.analyze_reliability()

        report = {
            'generation_time': datetime.now().isoformat(),
            'analysis_period': metrics.analysis_period,
            'reliability_summary': {
                'uptime_percentage': metrics.uptime_percentage,
                'total_errors': metrics.total_errors,
                'mtbf_hours': metrics.mean_time_between_failures_hours,
                'mttr_ms': metrics.mean_time_to_recovery_ms,
                'recovery_success_rate': metrics.recovery_success_rate,
            },
            'error_analysis': {
                'by_category': {
                    cat.value: count for cat, count in metrics.error_by_category.items()
                },
                'by_severity': {
                    sev.value: count for sev, count in metrics.error_by_severity.items()
                },
                'by_service': metrics.error_by_service,
                'recurring_issues': metrics.recurring_issues,
            },
            'failure_patterns': [
                {
                    'pattern_name': pattern.pattern_name,
                    'occurrences': pattern.occurrences,
                    'failure_rate': pattern.failure_rate,
                    'avg_recovery_time_ms': pattern.avg_recovery_time_ms,
                    'affected_services': list(pattern.affected_services),
                    'suggested_fixes': pattern.suggested_fixes[:3],  # Top 3 fixes
                }
                for pattern in metrics.top_failure_patterns
            ],
            'trends': {
                'error_trend': metrics.error_trend,
                'reliability_trend': metrics.reliability_trend,
                'peak_error_hours': metrics.peak_error_hours,
            },
            'recommendations': self._generate_reliability_recommendations(metrics),
        }

        # Save report if path provided
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f'Reliability report saved to {output_path}')

        return report

    def _generate_reliability_recommendations(
        self, metrics: ReliabilityMetrics
    ) -> dict[str, list[str]]:
        """Generate reliability improvement recommendations."""
        recommendations = {'immediate': [], 'short_term': [], 'long_term': []}

        # Immediate actions
        if metrics.uptime_percentage < 99.0:
            recommendations['immediate'].append(
                f'Address uptime issues (current: {metrics.uptime_percentage:.1f}%)'
            )

        if metrics.recovery_success_rate < 0.8:
            recommendations['immediate'].append(
                'Improve error recovery mechanisms (current success rate: '
                f'{metrics.recovery_success_rate:.1%})'
            )

        # High severity errors
        high_severity_count = metrics.error_by_severity.get(FailureSeverity.HIGH, 0)
        critical_count = metrics.error_by_severity.get(FailureSeverity.CRITICAL, 0)

        if critical_count > 0:
            recommendations['immediate'].append(
                f'Address {critical_count} critical errors immediately'
            )

        if high_severity_count > 5:
            recommendations['immediate'].append(
                f'Investigate {high_severity_count} high-severity errors'
            )

        # Short-term improvements
        if metrics.mean_time_to_recovery_ms > 30000:  # 30 seconds
            recommendations['short_term'].append(
                'Implement faster recovery mechanisms (current MTTR: '
                f'{metrics.mean_time_to_recovery_ms / 1000:.1f}s)'
            )

        # Top failure patterns
        for pattern in metrics.top_failure_patterns[:3]:
            if pattern.occurrences > 5:
                recommendations['short_term'].extend(pattern.suggested_fixes[:2])

        # Long-term optimizations
        recommendations['long_term'].extend(
            [
                'Implement comprehensive monitoring and alerting system',
                'Develop automated recovery procedures',
                'Create detailed incident response runbooks',
                'Implement chaos engineering practices',
                'Set up proactive failure prediction system',
            ]
        )

        return recommendations
