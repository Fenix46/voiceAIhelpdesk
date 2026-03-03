# VoiceHelpDeskAI API Documentation

## Table of Contents
1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Core Endpoints](#core-endpoints)
4. [WebSocket API](#websocket-api)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Examples](#examples)

## API Overview

VoiceHelpDeskAI provides a comprehensive REST API and WebSocket interface for voice-based customer support interactions. The API supports both real-time voice streaming and traditional HTTP requests.

### Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com/api/v1`

### API Versioning
- Current version: `v1`
- Version header: `X-API-Version: v1`

### Content Types
- **Request**: `application/json`, `multipart/form-data` (for audio)
- **Response**: `application/json`
- **WebSocket**: Binary (audio) and JSON (metadata)

## Authentication

### API Key Authentication
```http
Authorization: Bearer your-api-key-here
X-API-Key: your-api-key-here
```

### Session-based Authentication
```http
Cookie: session=session-token-here
```

### OAuth2 (Future)
```http
Authorization: Bearer oauth-token-here
```

## Core Endpoints

### Health Check

#### GET /health
Check system health and status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00Z",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "ai_models": "healthy"
  },
  "uptime": 86400
}
```

### Conversation Management

#### POST /conversations
Start a new conversation session.

**Request:**
```json
{
  "user_id": "user123",
  "channel": "web",
  "language": "en",
  "context": {
    "user_info": {
      "name": "John Doe",
      "email": "john@example.com"
    },
    "session_metadata": {}
  }
}
```

**Response:**
```json
{
  "conversation_id": "conv_abc123",
  "session_id": "sess_xyz789",
  "status": "active",
  "created_at": "2024-01-01T12:00:00Z",
  "websocket_url": "ws://localhost:8000/ws/audio/sess_xyz789"
}
```

#### GET /conversations/{conversation_id}
Get conversation details and history.

**Response:**
```json
{
  "conversation_id": "conv_abc123",
  "session_id": "sess_xyz789",
  "status": "completed",
  "started_at": "2024-01-01T12:00:00Z",
  "ended_at": "2024-01-01T12:05:30Z",
  "messages": [
    {
      "id": "msg_001",
      "type": "user_audio",
      "timestamp": "2024-01-01T12:00:15Z",
      "content": {
        "transcription": "Hello, I need help with my password",
        "confidence": 0.95,
        "audio_url": "/audio/msg_001.wav"
      }
    },
    {
      "id": "msg_002",
      "type": "ai_response",
      "timestamp": "2024-01-01T12:00:18Z",
      "content": {
        "text": "I'd be happy to help you with your password. Can you provide your username?",
        "audio_url": "/audio/msg_002.wav",
        "confidence": 0.98
      }
    }
  ],
  "summary": {
    "issue_type": "password_reset",
    "resolution": "completed",
    "satisfaction_score": 4.5
  }
}
```

#### PUT /conversations/{conversation_id}/status
Update conversation status.

**Request:**
```json
{
  "status": "escalated",
  "reason": "complex_technical_issue",
  "agent_id": "agent_456"
}
```

### Audio Processing

#### POST /audio/transcribe
Transcribe audio to text using STT.

**Request:**
```http
Content-Type: multipart/form-data

audio: (audio file)
language: en
model: whisper-base
```

**Response:**
```json
{
  "transcription": "Hello, I need help with my password reset",
  "confidence": 0.95,
  "language": "en",
  "duration": 3.2,
  "processing_time": 0.8
}
```

#### POST /audio/synthesize
Convert text to speech using TTS.

**Request:**
```json
{
  "text": "I'd be happy to help you with that",
  "voice": "en-US-neural",
  "speed": 1.0,
  "format": "wav"
}
```

**Response:**
```json
{
  "audio_url": "/audio/generated/audio_123.wav",
  "duration": 2.1,
  "format": "wav",
  "sample_rate": 22050
}
```

### AI Processing

#### POST /ai/generate-response
Generate AI response for user query.

**Request:**
```json
{
  "conversation_id": "conv_abc123",
  "user_input": "I forgot my password",
  "context": {
    "previous_messages": 2,
    "user_info": {
      "account_type": "premium"
    }
  }
}
```

**Response:**
```json
{
  "response": "I can help you reset your password. Let me guide you through the process...",
  "confidence": 0.92,
  "intent": "password_reset",
  "entities": [
    {
      "type": "request_type",
      "value": "password_reset",
      "confidence": 0.98
    }
  ],
  "suggested_actions": [
    "initiate_password_reset",
    "verify_identity"
  ],
  "escalation_recommended": false
}
```

### User Management

#### POST /users
Create or update user profile.

**Request:**
```json
{
  "user_id": "user123",
  "profile": {
    "name": "John Doe",
    "email": "john@example.com",
    "language": "en",
    "preferences": {
      "voice_speed": 1.0,
      "preferred_agent": null
    }
  }
}
```

#### GET /users/{user_id}
Get user profile and conversation history.

### Ticket Management

#### POST /tickets
Create a support ticket.

**Request:**
```json
{
  "conversation_id": "conv_abc123",
  "title": "Password reset assistance needed",
  "description": "User unable to reset password through automated system",
  "priority": "medium",
  "category": "account_access",
  "user_info": {
    "user_id": "user123",
    "email": "john@example.com"
  }
}
```

**Response:**
```json
{
  "ticket_id": "TICK-2024-001",
  "status": "open",
  "priority": "medium",
  "assigned_agent": null,
  "created_at": "2024-01-01T12:00:00Z",
  "estimated_response_time": "2h"
}
```

### Analytics & Reporting

#### GET /analytics/conversations
Get conversation analytics.

**Query Parameters:**
- `start_date`: ISO date string
- `end_date`: ISO date string
- `channel`: web, mobile, api
- `resolution_type`: ai_resolved, escalated, abandoned

**Response:**
```json
{
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "metrics": {
    "total_conversations": 1250,
    "ai_resolution_rate": 0.78,
    "average_duration": 180.5,
    "satisfaction_score": 4.2,
    "escalation_rate": 0.15
  },
  "breakdown": {
    "by_channel": {
      "web": 800,
      "mobile": 350,
      "api": 100
    },
    "by_issue_type": {
      "password_reset": 400,
      "technical_support": 300,
      "billing": 250,
      "general_inquiry": 300
    }
  }
}
```

## WebSocket API

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/audio/sess_xyz789');
```

### Real-time Audio Streaming

#### Client → Server Messages

**Start Recording:**
```json
{
  "type": "start_recording",
  "config": {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav"
  }
}
```

**Audio Data:**
```javascript
// Binary audio data
ws.send(audioBuffer);
```

**Stop Recording:**
```json
{
  "type": "stop_recording"
}
```

#### Server → Client Messages

**Recording Started:**
```json
{
  "type": "recording_started",
  "session_id": "sess_xyz789",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Transcription Result:**
```json
{
  "type": "transcription",
  "text": "Hello, I need help with my password",
  "confidence": 0.95,
  "is_final": true,
  "timestamp": "2024-01-01T12:00:03Z"
}
```

**AI Response:**
```json
{
  "type": "ai_response",
  "text": "I'd be happy to help you with your password reset",
  "audio_url": "/audio/response_123.wav",
  "confidence": 0.98,
  "timestamp": "2024-01-01T12:00:05Z"
}
```

**Error:**
```json
{
  "type": "error",
  "code": "TRANSCRIPTION_FAILED",
  "message": "Failed to process audio",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Data Models

### Conversation
```typescript
interface Conversation {
  conversation_id: string;
  session_id: string;
  user_id: string;
  status: 'active' | 'completed' | 'escalated' | 'abandoned';
  channel: 'web' | 'mobile' | 'api';
  language: string;
  started_at: string;
  ended_at?: string;
  messages: Message[];
  context: ConversationContext;
  summary?: ConversationSummary;
}
```

### Message
```typescript
interface Message {
  id: string;
  type: 'user_audio' | 'user_text' | 'ai_response' | 'agent_message';
  timestamp: string;
  content: AudioContent | TextContent;
}

interface AudioContent {
  transcription?: string;
  confidence?: number;
  audio_url?: string;
  duration?: number;
}

interface TextContent {
  text: string;
  audio_url?: string;
  confidence?: number;
}
```

### AI Response
```typescript
interface AIResponse {
  response: string;
  confidence: number;
  intent: string;
  entities: Entity[];
  suggested_actions: string[];
  escalation_recommended: boolean;
  processing_time: number;
}

interface Entity {
  type: string;
  value: string;
  confidence: number;
  start?: number;
  end?: number;
}
```

### User Profile
```typescript
interface UserProfile {
  user_id: string;
  name?: string;
  email?: string;
  language: string;
  created_at: string;
  last_active?: string;
  preferences: UserPreferences;
  conversation_history?: ConversationSummary[];
}

interface UserPreferences {
  voice_speed: number;
  preferred_language: string;
  notification_settings: NotificationSettings;
}
```

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "audio_format",
      "value": "mp4",
      "expected": "wav, mp3, m4a, ogg, flac"
    },
    "timestamp": "2024-01-01T12:00:00Z",
    "request_id": "req_123456"
  }
}
```

### Error Codes

#### 4xx Client Errors
- `400 BAD_REQUEST`: Invalid request format
- `401 UNAUTHORIZED`: Missing or invalid authentication
- `403 FORBIDDEN`: Insufficient permissions
- `404 NOT_FOUND`: Resource not found
- `429 TOO_MANY_REQUESTS`: Rate limit exceeded

#### 5xx Server Errors
- `500 INTERNAL_ERROR`: Server error
- `502 BAD_GATEWAY`: External service error
- `503 SERVICE_UNAVAILABLE`: Service temporarily unavailable
- `504 GATEWAY_TIMEOUT`: Request timeout

#### Custom Error Codes
- `AUDIO_PROCESSING_ERROR`: Audio processing failed
- `TRANSCRIPTION_FAILED`: STT service error
- `AI_SERVICE_ERROR`: AI model error
- `CONVERSATION_NOT_FOUND`: Invalid conversation ID
- `INVALID_AUDIO_FORMAT`: Unsupported audio format

## Rate Limiting

### Default Limits
- **API Requests**: 1000 requests/hour per API key
- **Audio Processing**: 100 requests/hour per user
- **WebSocket Connections**: 10 concurrent per user

### Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1704110400
X-RateLimit-Window: 3600
```

### Rate Limit Exceeded Response
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "API rate limit exceeded",
    "details": {
      "limit": 1000,
      "window": 3600,
      "retry_after": 1800
    }
  }
}
```

## Examples

### Complete Conversation Flow

#### 1. Start Conversation
```bash
curl -X POST http://localhost:8000/conversations \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "channel": "web",
    "language": "en"
  }'
```

#### 2. Upload Audio
```bash
curl -X POST http://localhost:8000/audio/transcribe \
  -H "Authorization: Bearer your-api-key" \
  -F "audio=@audio.wav" \
  -F "language=en"
```

#### 3. Generate AI Response
```bash
curl -X POST http://localhost:8000/ai/generate-response \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_abc123",
    "user_input": "I forgot my password",
    "context": {}
  }'
```

#### 4. Get Conversation History
```bash
curl -X GET http://localhost:8000/conversations/conv_abc123 \
  -H "Authorization: Bearer your-api-key"
```

### WebSocket Example
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/audio/sess_xyz789');

// Send audio data
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    const mediaRecorder = new MediaRecorder(stream);
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        ws.send(event.data);
      }
    };
    
    // Start recording
    ws.send(JSON.stringify({
      type: 'start_recording',
      config: { sample_rate: 16000, format: 'wav' }
    }));
    
    mediaRecorder.start(100); // Send chunks every 100ms
  });

// Handle responses
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'transcription':
      console.log('Transcription:', data.text);
      break;
    case 'ai_response':
      console.log('AI Response:', data.text);
      playAudio(data.audio_url);
      break;
    case 'error':
      console.error('Error:', data.message);
      break;
  }
};
```

### SDK Examples

#### Python
```python
import voicehelpdesk

client = voicehelpdesk.Client(api_key="your-api-key")

# Start conversation
conversation = await client.conversations.create(
    user_id="user123",
    channel="api"
)

# Process audio
result = await client.audio.transcribe(
    audio_file="audio.wav",
    language="en"
)

# Generate response
response = await client.ai.generate_response(
    conversation_id=conversation.id,
    user_input=result.transcription
)
```

#### JavaScript
```javascript
import VoiceHelpDesk from '@voicehelpdesk/sdk';

const client = new VoiceHelpDesk({
  apiKey: 'your-api-key',
  baseUrl: 'http://localhost:8000'
});

// Start conversation
const conversation = await client.conversations.create({
  userId: 'user123',
  channel: 'web'
});

// Real-time audio
const audioStream = await client.audio.createStream(conversation.sessionId);
audioStream.on('transcription', (text) => {
  console.log('User said:', text);
});
audioStream.on('response', (response) => {
  console.log('AI replied:', response.text);
});
```

---

For more information, see:
- [OpenAPI Specification](openapi.json)
- [SDK Documentation](../sdk/)
- [WebSocket Guide](websocket.md)
- [Authentication Guide](authentication.md)