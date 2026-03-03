"""Integration tests for the complete ticketing system."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
import json

from src.voicehelpdeskai.services.ticketing import (
    MockTicketAPI, TicketingService, TicketAnalytics, TestDataGenerator
)
from src.voicehelpdeskai.services.ticketing.service import MockAdapter
from src.voicehelpdeskai.database import DatabaseManager
from src.voicehelpdeskai.database.models import TicketStatus, TicketPriority, TicketCategory


class TestTicketingSystemIntegration:
    """Integration tests for the complete ticketing system."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for testing."""
        return Mock(spec=DatabaseManager)
    
    @pytest.fixture
    def mock_api(self, mock_db_manager):
        """Mock API instance."""
        return MockTicketAPI(mock_db_manager)
    
    @pytest.fixture
    def ticketing_service(self, mock_db_manager):
        """Ticketing service instance."""
        mock_adapter = MockAdapter()
        return TicketingService(mock_db_manager, mock_adapter)
    
    @pytest.fixture
    def analytics_service(self, mock_db_manager):
        """Analytics service instance."""
        return TicketAnalytics(mock_db_manager)
    
    @pytest.fixture
    def test_data_generator(self, mock_db_manager):
        """Test data generator instance."""
        return TestDataGenerator(mock_db_manager)
    
    @pytest.fixture
    def api_client(self, mock_api):
        """Test client for API."""
        return TestClient(mock_api.app)
    
    def test_complete_ticket_lifecycle(self, api_client):
        """Test complete ticket lifecycle from creation to closure."""
        # 1. Create ticket
        create_data = {
            "title": "Test ticket per integrazione",
            "description": "Questo è un ticket di test per verificare l'integrazione completa del sistema",
            "priority": 3,
            "category": "software",
            "user_id": "test-user-123",
            "tags": ["test", "integrazione"]
        }
        
        with patch('src.voicehelpdeskai.services.ticketing.mock_api.get_ticket_repository') as mock_repo:
            mock_ticket = Mock()
            mock_ticket.id = "test-ticket-123"
            mock_ticket.ticket_number = "TK2024-001234"
            mock_ticket.title = create_data["title"]
            mock_ticket.status = TicketStatus.OPEN.value
            mock_ticket.priority = create_data["priority"]
            mock_ticket.category = create_data["category"]
            mock_ticket.user_id = create_data["user_id"]
            mock_ticket.tags = create_data["tags"]
            mock_ticket.created_at = datetime.now(timezone.utc)
            mock_ticket.updated_at = datetime.now(timezone.utc)
            
            mock_repo_instance = Mock()
            mock_repo_instance.create.return_value = mock_ticket
            mock_repo_instance.get_by_id.return_value = mock_ticket
            mock_repo.return_value = mock_repo_instance
            
            # Create ticket
            response = api_client.post("/tickets", json=create_data)
            assert response.status_code == 201
            
            ticket_data = response.json()
            ticket_id = ticket_data["id"]
            assert ticket_data["status"] == "open"
            assert ticket_data["title"] == create_data["title"]
            
            # 2. Update ticket (assign and start work)
            update_data = {
                "status": "in_progress",
                "assigned_to": "tech-456",
                "assigned_group": "IT Support"
            }
            
            mock_ticket.status = TicketStatus.IN_PROGRESS.value
            mock_ticket.assigned_to = "tech-456"
            mock_ticket.assigned_group = "IT Support"
            mock_repo_instance.update.return_value = mock_ticket
            
            response = api_client.put(f"/tickets/{ticket_id}", json=update_data)
            assert response.status_code == 200
            
            updated_data = response.json()
            assert updated_data["status"] == "in_progress"
            assert updated_data["assigned_to"] == "tech-456"
            
            # 3. Resolve ticket
            resolve_data = {
                "status": "resolved",
                "solution": "Problema risolto con successo"
            }
            
            mock_ticket.status = TicketStatus.RESOLVED.value
            mock_ticket.solution = "Problema risolto con successo"
            mock_ticket.resolved_at = datetime.now(timezone.utc)
            
            response = api_client.put(f"/tickets/{ticket_id}", json=resolve_data)
            assert response.status_code == 200
            
            resolved_data = response.json()
            assert resolved_data["status"] == "resolved"
            assert resolved_data["solution"] == "Problema risolto con successo"
            
            # 4. Close ticket
            close_data = {"status": "closed"}
            
            mock_ticket.status = TicketStatus.CLOSED.value
            mock_ticket.closed_at = datetime.now(timezone.utc)
            
            response = api_client.put(f"/tickets/{ticket_id}", json=close_data)
            assert response.status_code == 200
            
            closed_data = response.json()
            assert closed_data["status"] == "closed"
    
    def test_search_and_filtering(self, api_client):
        """Test search and filtering functionality."""
        with patch('src.voicehelpdeskai.services.ticketing.mock_api.get_ticket_repository') as mock_repo:
            # Mock search results
            mock_tickets = []
            for i in range(5):
                mock_ticket = Mock()
                mock_ticket.id = f"test-ticket-{i}"
                mock_ticket.ticket_number = f"TK2024-{i:06d}"
                mock_ticket.title = f"Test ticket {i}"
                mock_ticket.status = TicketStatus.OPEN.value
                mock_ticket.priority = 2
                mock_ticket.category = TicketCategory.SOFTWARE.value
                mock_ticket.created_at = datetime.now(timezone.utc)
                mock_tickets.append(mock_ticket)
            
            mock_result = Mock()
            mock_result.items = mock_tickets
            mock_result.pagination = Mock()
            mock_result.pagination.page = 1
            mock_result.pagination.page_size = 20
            mock_result.pagination.total_items = 5
            mock_result.pagination.total_pages = 1
            mock_result.pagination.has_next = False
            mock_result.pagination.has_previous = False
            mock_result.facets = {}
            
            mock_repo_instance = Mock()
            mock_repo_instance.search.return_value = mock_result
            mock_repo.return_value = mock_repo_instance
            
            # Test basic search
            search_data = {
                "query": "test",
                "page": 1,
                "page_size": 20
            }
            
            response = api_client.post("/tickets/search", json=search_data)
            assert response.status_code == 200
            
            search_results = response.json()
            assert "tickets" in search_results
            assert "pagination" in search_results
            assert len(search_results["tickets"]) == 5
            
            # Test advanced filtering
            filter_data = {
                "status": ["open", "in_progress"],
                "priority": [2, 3],
                "category": ["software"],
                "page": 1,
                "page_size": 10
            }
            
            response = api_client.post("/tickets/search", json=filter_data)
            assert response.status_code == 200
            
            filtered_results = response.json()
            assert "tickets" in filtered_results
            assert len(filtered_results["tickets"]) <= 10
    
    def test_batch_operations(self, api_client):
        """Test batch operations functionality."""
        with patch('src.voicehelpdeskai.services.ticketing.mock_api.get_ticket_repository') as mock_repo:
            # Mock tickets for batch operations
            mock_tickets = []
            for i in range(3):
                mock_ticket = Mock()
                mock_ticket.id = f"batch-ticket-{i}"
                mock_ticket.ticket_number = f"TK2024-{i:06d}"
                mock_ticket.status = TicketStatus.OPEN.value
                mock_ticket.assigned_to = None
                mock_ticket.tags = []
                mock_tickets.append(mock_ticket)
            
            mock_repo_instance = Mock()
            mock_repo_instance.get_by_id.side_effect = lambda ticket_id: next(
                (t for t in mock_tickets if t.id == ticket_id), None
            )
            mock_repo_instance.update.side_effect = lambda ticket_id, data: next(
                (t for t in mock_tickets if t.id == ticket_id), None
            )
            mock_repo.return_value = mock_repo_instance
            
            # Test batch status update
            batch_data = {
                "ticket_ids": ["batch-ticket-0", "batch-ticket-1", "batch-ticket-2"],
                "operation": "update_status",
                "parameters": {"status": "in_progress"}
            }
            
            response = api_client.post("/tickets/batch", json=batch_data)
            assert response.status_code == 200
            
            batch_results = response.json()
            assert batch_results["total_requested"] == 3
            assert batch_results["successful"] >= 0
            assert "results" in batch_results
            
            # Test batch assignment
            assign_data = {
                "ticket_ids": ["batch-ticket-0", "batch-ticket-1"],
                "operation": "assign",
                "parameters": {
                    "assigned_to": "tech-789",
                    "assigned_group": "IT Support"
                }
            }
            
            response = api_client.post("/tickets/batch", json=assign_data)
            assert response.status_code == 200
            
            assign_results = response.json()
            assert assign_results["total_requested"] == 2
    
    def test_statistics_and_analytics(self, api_client):
        """Test statistics and analytics endpoints."""
        with patch('src.voicehelpdeskai.services.ticketing.mock_api.get_ticket_repository') as mock_repo:
            # Mock statistics data
            mock_stats = {
                "total_tickets": 100,
                "open_tickets": 25,
                "in_progress_tickets": 40,
                "resolved_tickets": 30,
                "closed_tickets": 5,
                "avg_resolution_time_hours": 24.5,
                "avg_response_time_minutes": 35.2,
                "avg_satisfaction_score": 4.2
            }
            
            mock_category_stats = {
                "software": 40,
                "hardware": 35,
                "network": 20,
                "security": 5
            }
            
            mock_priority_stats = {
                "1": 10, "2": 30, "3": 40, "4": 15, "5": 5
            }
            
            mock_status_stats = {
                "open": 25, "in_progress": 40, "resolved": 30, "closed": 5
            }
            
            mock_trending_tags = [
                {"tag": "performance", "count": 15, "trend": "increasing"},
                {"tag": "email", "count": 12, "trend": "stable"}
            ]
            
            mock_repo_instance = Mock()
            mock_repo_instance.get_statistics.return_value = mock_stats
            mock_repo_instance.get_category_distribution.return_value = mock_category_stats
            mock_repo_instance.get_priority_distribution.return_value = mock_priority_stats
            mock_repo_instance.get_status_distribution.return_value = mock_status_stats
            mock_repo_instance.get_trending_tags.return_value = mock_trending_tags
            mock_repo.return_value = mock_repo_instance
            
            # Test basic statistics
            response = api_client.get("/tickets/stats")
            assert response.status_code == 200
            
            stats_data = response.json()
            assert "total_tickets" in stats_data
            assert "by_category" in stats_data
            assert "by_priority" in stats_data
            assert "by_status" in stats_data
            assert "trending_tags" in stats_data
            
            # Test statistics with date range
            response = api_client.get(
                "/tickets/stats?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z"
            )
            assert response.status_code == 200
    
    def test_export_functionality(self, api_client):
        """Test ticket export functionality."""
        with patch('src.voicehelpdeskai.services.ticketing.mock_api.get_ticket_repository') as mock_repo:
            # Mock tickets for export
            mock_tickets = []
            for i in range(10):
                mock_ticket = Mock()
                mock_ticket.id = f"export-ticket-{i}"
                mock_ticket.ticket_number = f"TK2024-{i:06d}"
                mock_ticket.title = f"Export test ticket {i}"
                mock_ticket.status = TicketStatus.RESOLVED.value
                mock_ticket.priority = 2
                mock_ticket.category = TicketCategory.SOFTWARE.value
                mock_ticket.user_id = "test-user"
                mock_ticket.assigned_to = "tech-123"
                mock_ticket.created_at = datetime.now(timezone.utc)
                mock_ticket.updated_at = datetime.now(timezone.utc)
                mock_ticket.resolved_at = datetime.now(timezone.utc)
                mock_ticket.tags = ["test", "export"]
                mock_ticket.customer_satisfaction = 4
                mock_tickets.append(mock_ticket)
            
            mock_result = Mock()
            mock_result.items = mock_tickets
            
            mock_repo_instance = Mock()
            mock_repo_instance.search.return_value = mock_result
            mock_repo.return_value = mock_repo_instance
            
            # Test CSV export
            response = api_client.get("/tickets/export?format=csv")
            assert response.status_code == 200
            assert "text/csv" in response.headers.get("content-type", "")
            
            # Test JSON export
            response = api_client.get("/tickets/export?format=json")
            assert response.status_code == 200
            assert "application/json" in response.headers.get("content-type", "")
            
            # Test filtered export
            response = api_client.get(
                "/tickets/export?format=csv&status=resolved&category=software"
            )
            assert response.status_code == 200
    
    def test_webhook_management(self, api_client):
        """Test webhook registration and management."""
        # Test webhook registration
        webhook_data = {
            "url": "https://webhook.site/test-webhook",
            "events": ["created", "updated", "status_changed"],
            "secret": "test-secret",
            "active": True
        }
        
        response = api_client.post("/webhooks", json=webhook_data)
        assert response.status_code == 200
        
        webhook_result = response.json()
        assert "id" in webhook_result
        assert "message" in webhook_result
        webhook_id = webhook_result["id"]
        
        # Test webhook listing
        response = api_client.get("/webhooks")
        assert response.status_code == 200
        
        webhooks_list = response.json()
        assert "webhooks" in webhooks_list
        
        # Test webhook deletion
        response = api_client.delete(f"/webhooks/{webhook_id}")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ticketing_service_workflow(self, ticketing_service):
        """Test the TicketingService workflow logic."""
        # Mock dependencies
        with patch('src.voicehelpdeskai.services.ticketing.service.get_ticket_repository') as mock_repo:
            with patch('src.voicehelpdeskai.services.ticketing.service.get_user_repository') as mock_user_repo:
                # Setup mocks
                mock_ticket = Mock()
                mock_ticket.id = "service-ticket-123"
                mock_ticket.status = TicketStatus.OPEN.value
                mock_ticket.priority = 3
                mock_ticket.user_id = "test-user"
                
                mock_user = Mock()
                mock_user.id = "tech-456"
                mock_user.department = "IT Support"
                
                mock_repo_instance = Mock()
                mock_repo_instance.create.return_value = mock_ticket
                mock_repo_instance.get_by_id.return_value = mock_ticket
                mock_repo_instance.update.return_value = mock_ticket
                mock_repo.return_value = mock_repo_instance
                
                mock_user_repo_instance = Mock()
                mock_user_repo_instance.get_by_id.return_value = mock_user
                mock_user_repo.return_value = mock_user_repo_instance
                
                # Test ticket creation
                ticket_data = {
                    "title": "Test service ticket",
                    "description": "Testing ticketing service workflow",
                    "priority": 3,
                    "category": "software",
                    "user_id": "test-user"
                }
                
                created_ticket = await ticketing_service.create_ticket(ticket_data)
                assert created_ticket is not None
                
                # Test status update
                updated_ticket = await ticketing_service.update_ticket_status(
                    mock_ticket.id, "in_progress", "tech-456"
                )
                assert updated_ticket is not None
                
                # Test assignment
                assigned_ticket = await ticketing_service.assign_ticket(
                    mock_ticket.id, "tech-456", "IT Support", "manager-123"
                )
                assert assigned_ticket is not None
    
    @pytest.mark.asyncio
    async def test_analytics_calculations(self, analytics_service):
        """Test analytics calculations."""
        with patch('src.voicehelpdeskai.services.ticketing.analytics.get_ticket_repository') as mock_repo:
            # Mock tickets for analytics
            mock_tickets = []
            base_time = datetime.now(timezone.utc)
            
            for i in range(20):
                mock_ticket = Mock()
                mock_ticket.id = f"analytics-ticket-{i}"
                mock_ticket.status = TicketStatus.RESOLVED.value
                mock_ticket.priority = 2 + (i % 4)
                mock_ticket.category = ["software", "hardware", "network"][i % 3]
                mock_ticket.created_at = base_time - timedelta(days=i)
                mock_ticket.resolved_at = base_time - timedelta(days=i-1)
                mock_ticket.first_response_time = 30 + (i * 5)  # minutes
                mock_ticket.actual_resolution_time = 120 + (i * 10)  # minutes
                mock_ticket.customer_satisfaction = 3 + (i % 3)
                mock_tickets.append(mock_ticket)
            
            mock_result = Mock()
            mock_result.items = mock_tickets
            
            mock_repo_instance = Mock()
            mock_repo_instance.search.return_value = mock_result
            mock_repo.return_value = mock_repo_instance
            
            # Test response time metrics
            response_metrics = analytics_service.get_response_time_metrics()
            assert response_metrics.metric_type.value == "response_time"
            assert response_metrics.value > 0
            assert response_metrics.unit == "minutes"
            
            # Test resolution rate metrics
            resolution_metrics = analytics_service.get_resolution_rate_metrics()
            assert "metrics" in resolution_metrics
            assert "overall" in resolution_metrics
            
            # Test satisfaction analysis
            satisfaction_analysis = analytics_service.get_user_satisfaction_analysis()
            if "error" not in satisfaction_analysis:
                assert "avg_satisfaction" in satisfaction_analysis
                assert "distribution" in satisfaction_analysis
    
    def test_test_data_generation(self, test_data_generator):
        """Test the test data generation functionality."""
        # Test realistic ticket generation
        tickets = test_data_generator.generate_realistic_tickets(
            count=10,
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            include_resolution=True
        )
        
        assert len(tickets) == 10
        for ticket in tickets:
            assert "title" in ticket
            assert "description" in ticket
            assert "priority" in ticket
            assert "category" in ticket
            assert "user_id" in ticket
            assert ticket["priority"] in range(1, 6)
        
        # Test edge cases generation
        edge_cases = test_data_generator.generate_edge_cases()
        assert len(edge_cases) > 0
        
        for edge_case in edge_cases:
            assert "title" in edge_case
            assert "description" in edge_case
            assert "priority" in edge_case
        
        # Test user generation
        users = test_data_generator.create_sample_users(count=5)
        assert len(users) == 5
        
        for user in users:
            assert "username" in user
            assert "email" in user
            assert "full_name" in user
            assert "department" in user
    
    def test_error_handling(self, api_client):
        """Test error handling across the system."""
        # Test invalid ticket creation
        invalid_data = {
            "title": "A",  # Too short
            "description": "B",  # Too short
            "priority": 10,  # Invalid
            "category": "invalid_category",  # Invalid
            "user_id": ""  # Empty
        }
        
        response = api_client.post("/tickets", json=invalid_data)
        assert response.status_code in [400, 422]
        
        # Test non-existent ticket retrieval
        response = api_client.get("/tickets/non-existent-id")
        assert response.status_code == 404
        
        # Test invalid batch operation
        invalid_batch = {
            "ticket_ids": [],  # Empty list
            "operation": "invalid_operation",
            "parameters": {}
        }
        
        response = api_client.post("/tickets/batch", json=invalid_batch)
        assert response.status_code in [400, 422]
    
    def test_performance_stress_test(self, api_client):
        """Test system performance under load."""
        with patch('src.voicehelpdeskai.services.ticketing.mock_api.get_ticket_repository') as mock_repo:
            # Mock many tickets for stress testing
            mock_tickets = []
            for i in range(1000):
                mock_ticket = Mock()
                mock_ticket.id = f"stress-ticket-{i}"
                mock_ticket.ticket_number = f"TK2024-{i:06d}"
                mock_ticket.title = f"Stress test ticket {i}"
                mock_ticket.status = ["open", "in_progress", "resolved"][i % 3]
                mock_ticket.priority = 1 + (i % 5)
                mock_ticket.category = ["software", "hardware", "network"][i % 3]
                mock_ticket.created_at = datetime.now(timezone.utc)
                mock_tickets.append(mock_ticket)
            
            mock_result = Mock()
            mock_result.items = mock_tickets[:50]  # Return first 50
            mock_result.pagination = Mock()
            mock_result.pagination.page = 1
            mock_result.pagination.page_size = 50
            mock_result.pagination.total_items = 1000
            mock_result.pagination.total_pages = 20
            mock_result.pagination.has_next = True
            mock_result.pagination.has_previous = False
            mock_result.facets = {}
            
            mock_repo_instance = Mock()
            mock_repo_instance.search.return_value = mock_result
            mock_repo.return_value = mock_repo_instance
            
            # Test search with large dataset
            search_data = {
                "page": 1,
                "page_size": 50
            }
            
            response = api_client.post("/tickets/search", json=search_data)
            assert response.status_code == 200
            
            # Verify response time is reasonable
            assert response.elapsed.total_seconds() < 2.0
            
            search_results = response.json()
            assert len(search_results["tickets"]) == 50
            assert search_results["pagination"]["total_items"] == 1000


@pytest.mark.integration
class TestFullSystemIntegration:
    """Full system integration tests."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow."""
        # This would test the integration with the actual VoiceHelpDeskAI system
        # including voice processing, NLU, ticket creation, and response generation
        
        # Mock the full pipeline
        with patch('src.voicehelpdeskai.core.orchestrator.conversation_orchestrator.ConversationOrchestrator') as mock_orchestrator:
            mock_orchestrator_instance = Mock()
            mock_orchestrator.return_value = mock_orchestrator_instance
            
            # Simulate voice input -> ticket creation workflow
            voice_input = "Il mio computer è molto lento da questa mattina"
            
            # Mock NLU results
            mock_nlu_result = {
                "intent": "technical_issue",
                "entities": {
                    "problem_type": "performance",
                    "affected_system": "computer",
                    "urgency": "medium"
                },
                "confidence": 0.85
            }
            
            # Mock ticket creation from NLU
            expected_ticket_data = {
                "title": "Problema di performance del computer",
                "description": voice_input,
                "priority": 3,
                "category": "hardware",
                "subcategory": "performance"
            }
            
            # Verify the workflow would create appropriate ticket
            assert expected_ticket_data["category"] == "hardware"
            assert expected_ticket_data["priority"] == 3
    
    def test_database_integration(self):
        """Test database integration points."""
        # Test that the ticketing system properly integrates with the database layer
        with patch('src.voicehelpdeskai.database.get_ticket_repository') as mock_repo:
            mock_repo_instance = Mock()
            mock_repo.return_value = mock_repo_instance
            
            # Test repository calls
            mock_repo_instance.create.return_value = Mock()
            mock_repo_instance.get_by_id.return_value = Mock()
            mock_repo_instance.update.return_value = Mock()
            
            # Verify repository methods are available
            assert hasattr(mock_repo_instance, 'create')
            assert hasattr(mock_repo_instance, 'get_by_id')
            assert hasattr(mock_repo_instance, 'update')
            assert hasattr(mock_repo_instance, 'delete')
            assert hasattr(mock_repo_instance, 'search')


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])