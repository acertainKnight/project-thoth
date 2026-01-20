# Proposed Fix for Letta Code CLI Resume Bug

## Quick Summary
Change the `getResumeData` function to use the global conversation endpoint instead of the agent-scoped endpoint.

## Code Location
**File**: `src/index.ts` (or similar main entry point)
**Function**: `getResumeData` (compiled to letta.js:81096)

## The Fix

### Before (Current - Broken)
```typescript
async function getResumeData(
  conversationId: string,
  agentId: string,
  client: Letta
): Promise<ConversationData> {
  try {
    // ❌ WRONG: Using agent-scoped endpoint that doesn't exist
    const conversation = await client.agents.conversations.retrieve(
      agentId,
      conversationId
    );
    
    return {
      id: conversation.id,
      messages: conversation.in_context_message_ids || [],
      // ... other fields
    };
  } catch (error) {
    // This throws 404 because endpoint doesn't exist
    throw error;
  }
}
```

### After (Fixed)
```typescript
async function getResumeData(
  conversationId: string,
  agentId: string,
  client: Letta
): Promise<ConversationData> {
  try {
    // ✅ CORRECT: Using global conversation endpoint
    const conversation = await client.conversations.retrieve(conversationId);
    
    // Optional: Verify the conversation belongs to the expected agent
    if (conversation.agent_id !== agentId) {
      throw new Error(
        `Conversation ${conversationId} belongs to agent ${conversation.agent_id}, ` +
        `but expected agent ${agentId}`
      );
    }
    
    return {
      id: conversation.id,
      messages: conversation.in_context_message_ids || [],
      // ... other fields
    };
  } catch (error) {
    throw error;
  }
}
```

## Alternative: If API Client Doesn't Have Direct Method

If the Letta SDK doesn't expose `client.conversations.retrieve()` directly, use the HTTP client:

```typescript
async function getResumeData(
  conversationId: string,
  agentId: string,
  client: Letta
): Promise<ConversationData> {
  try {
    // Use the REST API directly
    const response = await client.get(`/v1/conversations/${conversationId}`);
    const conversation = response.data;
    
    // Optional: Verify agent ownership
    if (conversation.agent_id !== agentId) {
      throw new Error(
        `Conversation ${conversationId} belongs to agent ${conversation.agent_id}, ` +
        `but expected agent ${agentId}`
      );
    }
    
    return {
      id: conversation.id,
      messages: conversation.in_context_message_ids || [],
      // ... other fields
    };
  } catch (error) {
    if (error.status === 404) {
      throw new Error(`Conversation ${conversationId} not found`);
    }
    throw error;
  }
}
```

## API Endpoint Reference

### ✅ Correct Endpoints (use these)
```
GET  /v1/conversations              - List all conversations
GET  /v1/conversations/{id}         - Retrieve specific conversation
POST /v1/conversations              - Create new conversation
PUT  /v1/conversations/{id}         - Update conversation
```

### ❌ Incorrect Endpoints (don't use)
```
GET /v1/agents/{agent_id}/conversations/{id}  - Does NOT exist in Letta 0.16.x
```

## Testing the Fix

### Manual Test Script
```bash
#!/bin/bash
# test_conversation_retrieve.sh

LETTA_URL="http://localhost:8283"
API_KEY="your-api-key-here"

# List conversations to get IDs
echo "Listing conversations..."
CONVERSATIONS=$(curl -s "${LETTA_URL}/v1/conversations" \
  -H "Authorization: Bearer ${API_KEY}")

echo "$CONVERSATIONS" | jq '.[] | {id, agent_id}'

# Get first conversation ID
CONV_ID=$(echo "$CONVERSATIONS" | jq -r '.[0].id')
AGENT_ID=$(echo "$CONVERSATIONS" | jq -r '.[0].agent_id')

echo ""
echo "Testing retrieval of conversation: $CONV_ID"

# Test global endpoint (should work)
echo "Testing global endpoint..."
curl -s "${LETTA_URL}/v1/conversations/${CONV_ID}" \
  -H "Authorization: Bearer ${API_KEY}" | jq '.'

# Test agent-scoped endpoint (currently fails)
echo ""
echo "Testing agent-scoped endpoint (this should fail)..."
curl -s "${LETTA_URL}/v1/agents/${AGENT_ID}/conversations/${CONV_ID}" \
  -H "Authorization: Bearer ${API_KEY}" | jq '.'
```

### TypeScript Unit Test
```typescript
import { describe, it, expect, jest } from '@jest/globals';
import { getResumeData } from './index';
import { Letta } from '@letta/sdk';

describe('getResumeData', () => {
  let mockClient: jest.Mocked<Letta>;

  beforeEach(() => {
    mockClient = {
      conversations: {
        retrieve: jest.fn(),
      },
      agents: {
        conversations: {
          retrieve: jest.fn(),
        },
      },
    } as any;
  });

  it('should use global conversation endpoint', async () => {
    const conversationId = 'conv-test-123';
    const agentId = 'agent-test-456';
    
    const mockConversation = {
      id: conversationId,
      agent_id: agentId,
      in_context_message_ids: ['msg1', 'msg2'],
    };

    mockClient.conversations.retrieve.mockResolvedValue(mockConversation);

    const result = await getResumeData(conversationId, agentId, mockClient);

    // Verify it called the global endpoint
    expect(mockClient.conversations.retrieve).toHaveBeenCalledWith(conversationId);
    expect(mockClient.conversations.retrieve).toHaveBeenCalledTimes(1);
    
    // Verify it did NOT call agent-scoped endpoint
    expect(mockClient.agents.conversations.retrieve).not.toHaveBeenCalled();
    
    // Verify result
    expect(result.id).toBe(conversationId);
    expect(result.messages).toEqual(['msg1', 'msg2']);
  });

  it('should throw error if conversation belongs to different agent', async () => {
    const conversationId = 'conv-test-123';
    const expectedAgentId = 'agent-test-456';
    const actualAgentId = 'agent-different-789';
    
    const mockConversation = {
      id: conversationId,
      agent_id: actualAgentId,
      in_context_message_ids: [],
    };

    mockClient.conversations.retrieve.mockResolvedValue(mockConversation);

    await expect(
      getResumeData(conversationId, expectedAgentId, mockClient)
    ).rejects.toThrow(/belongs to agent/);
  });

  it('should handle 404 errors gracefully', async () => {
    const conversationId = 'conv-nonexistent';
    const agentId = 'agent-test-456';
    
    const error = new Error('Not Found');
    (error as any).status = 404;
    
    mockClient.conversations.retrieve.mockRejectedValue(error);

    await expect(
      getResumeData(conversationId, agentId, mockClient)
    ).rejects.toThrow('not found');
  });
});
```

## Diff Format (for PR)

```diff
--- a/src/index.ts
+++ b/src/index.ts
@@ -xxx,yy +xxx,yy @@ async function getResumeData(
   client: Letta
 ): Promise<ConversationData> {
   try {
-    // Using agent-scoped endpoint
-    const conversation = await client.agents.conversations.retrieve(
-      agentId,
-      conversationId
-    );
+    // Use global conversation endpoint (Letta 0.16.x)
+    const conversation = await client.conversations.retrieve(conversationId);
+    
+    // Verify conversation belongs to expected agent
+    if (conversation.agent_id !== agentId) {
+      throw new Error(
+        `Conversation ${conversationId} belongs to agent ${conversation.agent_id}, ` +
+        `but expected agent ${agentId}`
+      );
+    }
     
     return {
       id: conversation.id,
```

## Migration Path for Users

### No User Action Required
This is a bug fix, not a breaking change. Users will automatically get the fix when they:
1. Update to the next Letta Code CLI version
2. Conversations will resume correctly without any configuration changes

### For Developers Running from Source
```bash
# Pull the latest changes
git pull origin main

# Rebuild
npm run build

# Test
npm test

# Install globally
npm link
```

## Backward Compatibility

### Letta Server 0.15.x and Earlier
- ✅ Should still work if those versions also support global conversation endpoint
- Need to verify: Did 0.15.x support `/v1/conversations/{id}`?
- If not, may need version detection logic

### Letta Server 0.16.x and Later
- ✅ Definitely works (verified with 0.16.2)
- This is the primary target for the fix

## Related SDK Changes

If the Letta TypeScript SDK doesn't currently expose `client.conversations.retrieve()`, that also needs to be added:

```typescript
// In Letta SDK
export class Letta {
  // ... existing code ...
  
  public conversations = {
    list: async (): Promise<Conversation[]> => {
      return this.get('/v1/conversations');
    },
    
    retrieve: async (id: string): Promise<Conversation> => {
      return this.get(`/v1/conversations/${id}`);
    },
    
    create: async (data: CreateConversationRequest): Promise<Conversation> => {
      return this.post('/v1/conversations', data);
    },
    
    update: async (id: string, data: UpdateConversationRequest): Promise<Conversation> => {
      return this.put(`/v1/conversations/${id}`, data);
    },
  };
}
```

## Rollback Plan

If this fix causes issues, rollback is simple:
```typescript
// Revert to agent-scoped endpoint (will fail on 0.16.x)
const conversation = await client.agents.conversations.retrieve(agentId, conversationId);
```

But this shouldn't be necessary since the global endpoint is the correct one per Letta server API.

---

## Questions for Letta Team

1. **Was the agent-scoped conversation endpoint intentionally removed in 0.16.x?**
   - If yes, this CLI fix is correct
   - If no, the server needs to restore the endpoint

2. **Should conversations be scoped to agents?**
   - Current API suggests conversations are global entities
   - But they have an `agent_id` field, suggesting ownership
   - Should CLI verify agent ownership when resuming?

3. **What's the recommended pattern for accessing conversations?**
   - Global endpoint for all operations?
   - Or different endpoints for different use cases?

4. **Backward compatibility?**
   - Should CLI support both old and new Letta server versions?
   - If yes, need version detection logic
