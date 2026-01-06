"""
Message queue implementation using Letta shared memory blocks.
Enables asynchronous agent-to-agent communication.
"""

import httpx
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

API_BASE = "http://localhost:8283/v1"


def _get_message_queue_block_id() -> Optional[str]:
    """Get the message_queue block ID from saved configuration."""
    blocks_file = Path(__file__).parent.parent.parent.parent / "scripts" / "shared_memory_blocks.json"

    if not blocks_file.exists():
        return None

    with open(blocks_file, 'r') as f:
        blocks = json.load(f)

    return blocks.get('message_queue')


def _get_block_content(block_id: str) -> str:
    """Get current content of message_queue block."""
    response = httpx.get(f"{API_BASE}/blocks/{block_id}")

    if response.status_code == 200:
        return response.json().get('value', '')

    return ''


def _update_block_content(block_id: str, new_content: str) -> bool:
    """Update message_queue block content."""
    response = httpx.patch(
        f"{API_BASE}/blocks/{block_id}",
        json={"value": new_content}
    )

    return response.status_code == 200


def post_message(
    sender: str,
    receiver: str,
    task: str,
    priority: str = "medium",
    metadata: Optional[Dict] = None
) -> bool:
    """
    Post a message to the agent message queue.

    Args:
        sender: Agent name posting the message
        receiver: Agent name receiving the message
        task: Task description
        priority: Priority level (low/medium/high/critical)
        metadata: Optional additional data

    Returns:
        True if message posted successfully
    """
    block_id = _get_message_queue_block_id()
    if not block_id:
        print("❌ Message queue block not found")
        return False

    current_content = _get_block_content(block_id)

    # Format message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"""
[{timestamp}] {sender} -> {receiver}
Task: {task}
Priority: {priority}
Status: pending
"""

    if metadata:
        message += f"Metadata: {json.dumps(metadata)}\n"

    message += "---\n"

    # Append to queue (keep header, append after it)
    if "[No messages]" in current_content:
        # First message, replace placeholder
        new_content = current_content.replace("[No messages]\n\n", message)
    else:
        # Find the header end and append
        header_end = current_content.find("=== Message Format ===")
        if header_end > 0:
            messages_section = current_content[:header_end]
            format_section = current_content[header_end:]
            new_content = messages_section + message + "\n" + format_section
        else:
            new_content = current_content + "\n" + message

    return _update_block_content(block_id, new_content)


def read_messages() -> List[Dict]:
    """
    Read all messages from the queue.

    Returns:
        List of message dictionaries
    """
    block_id = _get_message_queue_block_id()
    if not block_id:
        return []

    content = _get_block_content(block_id)

    messages = []
    message_blocks = content.split("---\n")

    for block in message_blocks:
        if not block.strip() or "===" in block or "[No messages]" in block:
            continue

        lines = block.strip().split("\n")
        if len(lines) < 4:
            continue

        # Parse message
        header = lines[0]
        if " -> " not in header:
            continue

        timestamp_sender = header.split("] ")[0] + "]"
        timestamp = timestamp_sender.strip("[]")
        sender_receiver = header.split("] ")[1]
        sender, receiver = sender_receiver.split(" -> ")

        task = ""
        priority = "medium"
        status = "pending"
        metadata = {}

        for line in lines[1:]:
            if line.startswith("Task: "):
                task = line.replace("Task: ", "").strip()
            elif line.startswith("Priority: "):
                priority = line.replace("Priority: ", "").strip()
            elif line.startswith("Status: "):
                status = line.replace("Status: ", "").strip()
            elif line.startswith("Metadata: "):
                try:
                    metadata = json.loads(line.replace("Metadata: ", ""))
                except:
                    pass

        messages.append({
            "timestamp": timestamp,
            "sender": sender,
            "receiver": receiver,
            "task": task,
            "priority": priority,
            "status": status,
            "metadata": metadata
        })

    return messages


def read_messages_for_agent(agent_name: str, status: Optional[str] = None) -> List[Dict]:
    """
    Read messages addressed to a specific agent.

    Args:
        agent_name: Name of the receiving agent
        status: Optional status filter (pending/in_progress/complete)

    Returns:
        List of messages for this agent
    """
    all_messages = read_messages()

    filtered = [m for m in all_messages if m['receiver'] == agent_name]

    if status:
        filtered = [m for m in filtered if m['status'] == status]

    return filtered


def mark_message_complete(sender: str, receiver: str, timestamp: str) -> bool:
    """
    Mark a specific message as complete.

    Args:
        sender: Original sender
        receiver: Original receiver
        timestamp: Message timestamp for identification

    Returns:
        True if message updated successfully
    """
    block_id = _get_message_queue_block_id()
    if not block_id:
        return False

    content = _get_block_content(block_id)

    # Find and update the specific message
    target = f"[{timestamp}] {sender} -> {receiver}"

    if target in content:
        # Replace status line
        new_content = content.replace(
            f"{target}\nTask:",
            f"{target}\nTask:"
        )

        # Find status line and update
        lines = new_content.split("\n")
        updated_lines = []
        in_target_message = False

        for line in lines:
            if target in line:
                in_target_message = True

            if in_target_message and line.startswith("Status: "):
                updated_lines.append("Status: complete")
                in_target_message = False
            else:
                updated_lines.append(line)

        new_content = "\n".join(updated_lines)
        return _update_block_content(block_id, new_content)

    return False


def clear_old_messages(keep_recent: int = 10) -> bool:
    """
    Clear old completed messages, keeping only recent ones.

    Args:
        keep_recent: Number of recent messages to keep

    Returns:
        True if cleared successfully
    """
    block_id = _get_message_queue_block_id()
    if not block_id:
        return False

    messages = read_messages()

    # Keep pending/in_progress and recent completed
    pending = [m for m in messages if m['status'] != 'complete']
    completed = [m for m in messages if m['status'] == 'complete']

    # Keep only recent completed messages
    recent_completed = sorted(completed, key=lambda x: x['timestamp'], reverse=True)[:keep_recent]

    messages_to_keep = pending + recent_completed

    # Rebuild content
    header = """=== Agent Message Queue ===

"""

    if not messages_to_keep:
        header += "[No messages]\n\n"
    else:
        for msg in messages_to_keep:
            header += f"""[{msg['timestamp']}] {msg['sender']} -> {msg['receiver']}
Task: {msg['task']}
Priority: {msg['priority']}
Status: {msg['status']}
"""
            if msg['metadata']:
                header += f"Metadata: {json.dumps(msg['metadata'])}\n"
            header += "---\n"

    header += """
=== Message Format ===
[timestamp] sender -> receiver
Task: description
Priority: high/medium/low
Status: pending/in_progress/complete
---"""

    return _update_block_content(block_id, header)
