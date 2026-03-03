# VoiceHelpDeskAI Mock Ticket API Documentation

## Overview

The VoiceHelpDeskAI Mock Ticket API provides a comprehensive ticketing system for development and testing purposes. It includes full CRUD operations, advanced search capabilities, batch operations, analytics, and webhook support.

**Base URL:** `http://localhost:8000/api/v1/tickets`

**Version:** 1.0.0

## Authentication

Currently, the mock API does not require authentication. In production, implement appropriate authentication mechanisms.

## Rate Limiting

No rate limiting is currently implemented in the mock API.

## Response Format

All responses follow a consistent JSON format:

### Success Response
```json
{
  "data": { ... },
  "status": "success",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Title is required",
    "details": { ... }
  },
  "status": "error",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Endpoints

### 1. Create Ticket

**POST** `/tickets`

Creates a new support ticket.

#### Request Body
```json
{
  "title": "Il computer è molto lento",
  "description": "Il mio computer è diventato estremamente lento negli ultimi giorni...",
  "priority": 3,
  "category": "hardware",
  "subcategory": "performance",
  "user_id": "user-123",
  "reporter_email": "mario.rossi@company.com",
  "reporter_phone": "+39 123 456 7890",
  "affected_systems": ["Windows 10", "Office 365"],
  "asset_ids": ["PC-001", "LIC-OFF365-001"],
  "tags": ["performance", "lentezza"],
  "business_impact": "Ridotta produttività per l'utente",
  "urgency_justification": "Blocca le attività quotidiane"
}
```

#### Response (201 Created)
```json
{
  "id": "tick-789",
  "ticket_number": "TK2024-000123",
  "title": "Il computer è molto lento",
  "description": "Il mio computer è diventato estremamente lento...",
  "status": "open",
  "priority": 3,
  "category": "hardware",
  "subcategory": "performance",
  "user_id": "user-123",
  "assigned_to": null,
  "assigned_group": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "resolved_at": null,
  "closed_at": null,
  "tags": ["performance", "lentezza"],
  "solution": null,
  "customer_satisfaction": null
}
```

### 2. Get Ticket

**GET** `/tickets/{ticket_id}`

Retrieves a specific ticket by ID.

#### Path Parameters
- `ticket_id` (string): Unique ticket identifier

#### Response (200 OK)
```json
{
  "id": "tick-789",
  "ticket_number": "TK2024-000123",
  "title": "Il computer è molto lento",
  "status": "in_progress",
  "priority": 3,
  "category": "hardware",
  "user_id": "user-123",
  "assigned_to": "tech-456",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

### 3. Update Ticket

**PUT** `/tickets/{ticket_id}`

Updates an existing ticket.

#### Request Body (partial update supported)
```json
{
  "status": "resolved",
  "solution": "Aggiornamento driver scheda video risolto il problema",
  "resolution_steps": [
    "Identificazione driver obsoleti",
    "Download nuovi driver",
    "Installazione e riavvio sistema"
  ],
  "internal_notes": "Cliente soddisfatto della soluzione"
}
```

#### Response (200 OK)
```json
{
  "id": "tick-789",
  "ticket_number": "TK2024-000123",
  "status": "resolved",
  "solution": "Aggiornamento driver scheda video risolto il problema",
  "resolved_at": "2024-01-15T14:30:00Z"
}
```

### 4. Delete Ticket

**DELETE** `/tickets/{ticket_id}`

Soft deletes a ticket (marks as deleted but preserves data).

#### Response (200 OK)
```json
{
  "message": "Ticket deleted successfully"
}
```

### 5. Search Tickets

**POST** `/tickets/search`

Advanced ticket search with filtering and pagination.

#### Request Body
```json
{
  "query": "computer lento",
  "status": ["open", "in_progress"],
  "priority": [3, 4, 5],
  "category": ["hardware", "software"],
  "assigned_to": "tech-456",
  "created_after": "2024-01-01T00:00:00Z",
  "created_before": "2024-01-31T23:59:59Z",
  "tags": ["performance"],
  "page": 1,
  "page_size": 20,
  "sort_by": "created_at",
  "sort_order": "desc"
}
```

#### Response (200 OK)
```json
{
  "tickets": [
    {
      "id": "tick-789",
      "ticket_number": "TK2024-000123",
      "title": "Il computer è molto lento",
      "status": "in_progress",
      "priority": 3,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 45,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false
  },
  "facets": {
    "status": {
      "open": 12,
      "in_progress": 18,
      "resolved": 15
    },
    "category": {
      "hardware": 25,
      "software": 15,
      "network": 5
    }
  }
}
```

### 6. Batch Operations

**POST** `/tickets/batch`

Perform batch operations on multiple tickets.

#### Request Body
```json
{
  "ticket_ids": ["tick-789", "tick-790", "tick-791"],
  "operation": "update_status",
  "parameters": {
    "status": "in_progress"
  }
}
```

#### Available Operations
- `update_status`: Change status for multiple tickets
- `assign`: Assign tickets to user or group
- `add_tag`: Add tag to multiple tickets
- `bulk_delete`: Delete multiple tickets

#### Response (200 OK)
```json
{
  "total_requested": 3,
  "successful": 2,
  "failed": 1,
  "errors": [
    {
      "ticket_id": "tick-791",
      "error": "Ticket not found"
    }
  ],
  "results": [
    {
      "ticket_id": "tick-789",
      "old_status": "open",
      "new_status": "in_progress",
      "success": true
    },
    {
      "ticket_id": "tick-790",
      "old_status": "open",
      "new_status": "in_progress",
      "success": true
    }
  ]
}
```

### 7. Get Statistics

**GET** `/tickets/stats`

Retrieve comprehensive ticket statistics and metrics.

#### Query Parameters
- `start_date` (datetime, optional): Start date for statistics
- `end_date` (datetime, optional): End date for statistics

#### Response (200 OK)
```json
{
  "total_tickets": 150,
  "open_tickets": 25,
  "in_progress_tickets": 40,
  "resolved_tickets": 70,
  "closed_tickets": 15,
  "avg_resolution_time_hours": 24.5,
  "avg_response_time_minutes": 35.2,
  "satisfaction_score": 4.2,
  "by_category": {
    "hardware": 60,
    "software": 45,
    "network": 30,
    "security": 15
  },
  "by_priority": {
    "1": 10,
    "2": 45,
    "3": 60,
    "4": 25,
    "5": 10
  },
  "by_status": {
    "open": 25,
    "in_progress": 40,
    "resolved": 70,
    "closed": 15
  },
  "trending_tags": [
    {
      "tag": "performance",
      "count": 25,
      "trend": "increasing"
    },
    {
      "tag": "email",
      "count": 20,
      "trend": "stable"
    }
  ]
}
```

### 8. Export Tickets

**GET** `/tickets/export`

Export tickets in various formats.

#### Query Parameters
- `format` (string): Export format ("csv", "json", "excel")
- `start_date` (datetime, optional): Start date for export
- `end_date` (datetime, optional): End date for export
- `status` (array, optional): Filter by status
- `category` (array, optional): Filter by category

#### Response
Returns file download with appropriate content type.

### 9. Webhook Management

#### Register Webhook

**POST** `/webhooks`

Register a webhook for ticket events.

##### Request Body
```json
{
  "url": "https://your-app.com/webhook/tickets",
  "events": ["created", "updated", "status_changed", "assigned"],
  "secret": "your-webhook-secret",
  "active": true
}
```

#### List Webhooks

**GET** `/webhooks`

List all registered webhooks.

#### Unregister Webhook

**DELETE** `/webhooks/{webhook_id}`

Remove a webhook registration.

## Webhook Events

When configured, webhooks are triggered for the following events:

### Event: ticket.created
```json
{
  "event": "created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "id": "tick-789",
    "ticket_number": "TK2024-000123",
    "title": "Il computer è molto lento",
    "status": "open",
    "priority": 3,
    "user_id": "user-123"
  }
}
```

### Event: ticket.status_changed
```json
{
  "event": "status_changed",
  "timestamp": "2024-01-15T11:00:00Z",
  "data": {
    "id": "tick-789",
    "ticket_number": "TK2024-000123",
    "old_status": "open",
    "new_status": "in_progress",
    "assigned_to": "tech-456"
  }
}
```

## Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Request validation failed |
| `TICKET_NOT_FOUND` | Ticket does not exist |
| `UNAUTHORIZED` | Authentication required |
| `FORBIDDEN` | Insufficient permissions |
| `WORKFLOW_ERROR` | Invalid status transition |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `INTERNAL_ERROR` | Server error |

## Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Access denied
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Data Models

### Ticket Model
```json
{
  "id": "string",
  "ticket_number": "string",
  "title": "string",
  "description": "string",
  "status": "string",
  "priority": "integer (1-5)",
  "category": "string",
  "subcategory": "string",
  "user_id": "string",
  "assigned_to": "string",
  "assigned_group": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "resolved_at": "datetime",
  "closed_at": "datetime",
  "tags": ["string"],
  "solution": "string",
  "customer_satisfaction": "integer (1-5)",
  "business_impact": "string",
  "urgency_justification": "string",
  "affected_systems": ["string"],
  "asset_ids": ["string"]
}
```

### User Model
```json
{
  "id": "string",
  "username": "string",
  "email": "string",
  "full_name": "string",
  "department": "string",
  "role": "string",
  "is_active": "boolean"
}
```

## Examples

### Creating a High Priority Ticket
```bash
curl -X POST "http://localhost:8000/api/v1/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "EMERGENZA: Server di produzione offline",
    "description": "Il server di produzione principale è completamente offline da 10 minuti. Tutti i servizi sono inaccessibili.",
    "priority": 5,
    "category": "hardware",
    "user_id": "user-123",
    "business_impact": "Blocco totale produzione aziendale",
    "urgency_justification": "Perdita economica critica",
    "tags": ["emergenza", "server", "produzione"]
  }'
```

### Searching Tickets by Status
```bash
curl -X POST "http://localhost:8000/api/v1/tickets/search" \
  -H "Content-Type: application/json" \
  -d '{
    "status": ["open", "in_progress"],
    "priority": [4, 5],
    "page": 1,
    "page_size": 10
  }'
```

### Batch Status Update
```bash
curl -X POST "http://localhost:8000/api/v1/tickets/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_ids": ["tick-789", "tick-790"],
    "operation": "update_status",
    "parameters": {
      "status": "resolved"
    }
  }'
```

## Testing

The API includes comprehensive test data generation capabilities:

- Realistic IT problem scenarios
- User personas with different behavior patterns
- Temporal patterns following business hours
- Edge cases and stress testing data

Use the `TestDataGenerator` class to populate the system with realistic test data for development and testing purposes.

## Integration

The mock API is designed to be easily replaceable with real ticketing systems using the adapter pattern. Supported adapters include:

- Mock Adapter (for testing)
- Jira Adapter (placeholder)
- ServiceNow Adapter (placeholder)

Custom adapters can be implemented by extending the `TicketAdapter` base class.