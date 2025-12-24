"""
Tests for agent message queue coordination.
"""

import pytest
from thoth.coordination.message_queue import (
    post_message,
    read_messages,
    read_messages_for_agent,
    mark_message_complete,
    clear_old_messages
)


def test_post_message():
    """Test posting a message to the queue."""
    result = post_message(
        sender="thoth_main_orchestrator",
        receiver="system_discovery_scout",
        task="Find papers on quantum computing",
        priority="high",
        metadata={"search_terms": ["quantum", "computing"]}
    )

    assert result is True, "Message posting should succeed"


def test_read_messages():
    """Test reading all messages from queue."""
    messages = read_messages()

    assert isinstance(messages, list), "Should return a list"

    if messages:
        msg = messages[0]
        assert 'sender' in msg
        assert 'receiver' in msg
        assert 'task' in msg
        assert 'priority' in msg
        assert 'status' in msg
        assert 'timestamp' in msg


def test_read_messages_for_agent():
    """Test reading messages for specific agent."""
    # Post a test message
    post_message(
        sender="thoth_main_orchestrator",
        receiver="system_citation_analyzer",
        task="Analyze citation network",
        priority="medium"
    )

    messages = read_messages_for_agent("system_citation_analyzer")

    assert isinstance(messages, list), "Should return a list"

    for msg in messages:
        assert msg['receiver'] == "system_citation_analyzer"


def test_read_pending_messages():
    """Test filtering messages by status."""
    # Post messages
    post_message(
        sender="thoth_main_orchestrator",
        receiver="system_analysis_expert",
        task="Analyze research paper",
        priority="high"
    )

    pending_messages = read_messages_for_agent(
        "system_analysis_expert",
        status="pending"
    )

    assert isinstance(pending_messages, list), "Should return a list"

    for msg in pending_messages:
        assert msg['status'] == "pending"


def test_mark_message_complete():
    """Test marking a message as complete."""
    # Post a message
    post_message(
        sender="orchestrator",
        receiver="scout",
        task="Test task",
        priority="low"
    )

    # Read messages to get timestamp
    messages = read_messages_for_agent("scout", status="pending")

    if messages:
        msg = messages[0]
        result = mark_message_complete(
            sender=msg['sender'],
            receiver=msg['receiver'],
            timestamp=msg['timestamp']
        )

        assert result is True, "Should mark message as complete"

        # Verify status changed
        updated_messages = read_messages_for_agent("scout")
        completed = [m for m in updated_messages if m['timestamp'] == msg['timestamp']]

        if completed:
            assert completed[0]['status'] == "complete"


def test_message_workflow():
    """Test complete message workflow."""
    # 1. Orchestrator posts task to scout
    post_message(
        sender="thoth_main_orchestrator",
        receiver="system_discovery_scout",
        task="Search for papers on neural networks",
        priority="high",
        metadata={"max_results": 10}
    )

    # 2. Scout reads pending messages
    scout_messages = read_messages_for_agent(
        "system_discovery_scout",
        status="pending"
    )

    assert len(scout_messages) > 0, "Scout should have pending messages"

    task = scout_messages[0]
    assert task['sender'] == "thoth_main_orchestrator"
    assert "neural networks" in task['task']

    # 3. Scout completes task and updates status
    mark_message_complete(
        sender=task['sender'],
        receiver=task['receiver'],
        timestamp=task['timestamp']
    )

    # 4. Verify status updated
    completed_messages = read_messages_for_agent(
        "system_discovery_scout",
        status="complete"
    )

    assert any(m['timestamp'] == task['timestamp'] for m in completed_messages)


def test_clear_old_messages():
    """Test clearing old completed messages."""
    # Post several messages
    for i in range(5):
        post_message(
            sender="test_sender",
            receiver="test_receiver",
            task=f"Test task {i}",
            priority="low"
        )

    # Clear old messages, keep only 2
    result = clear_old_messages(keep_recent=2)

    assert result is True, "Should clear messages successfully"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
