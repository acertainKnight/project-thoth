# ==============================================================================
# Letta Memory Service Management
# ==============================================================================

.PHONY: help start stop restart logs health status backup restore clean scale monitor

# Default target
help:
	@echo "Letta Memory Service Management"
	@echo "==============================="
	@echo ""
	@echo "Development Commands:"
	@echo "  start       - Start memory service"
	@echo "  stop        - Stop memory service"
	@echo "  restart     - Restart memory service"
	@echo "  logs        - View service logs"
	@echo "  health      - Check service health"
	@echo "  status      - Show service status"
	@echo ""
	@echo "Production Commands:"
	@echo "  start-prod  - Start with monitoring and proxy"
	@echo "  scale       - Scale Letta instances"
	@echo "  backup      - Backup memory data"
	@echo "  restore     - Restore from backup"
	@echo ""
	@echo "Maintenance Commands:"
	@echo "  clean       - Clean up volumes and containers"
	@echo "  monitor     - Open monitoring dashboard"
	@echo "  shell       - Connect to Letta container"

# Development Commands
start:
	@echo "Starting Letta Memory Service..."
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@make health

stop:
	@echo "Stopping Letta Memory Service..."
	docker-compose down

restart:
	@echo "Restarting Letta Memory Service..."
	docker-compose restart letta
	@sleep 5
	@make health

logs:
	docker-compose logs -f letta

health:
	@echo "Checking Letta Memory Service health..."
	@curl -s http://localhost:8283/health | jq '.' || echo "❌ Service not responding"
	@echo ""
	@docker-compose ps

status:
	@echo "Letta Memory Service Status:"
	@echo "============================="
	@docker-compose ps
	@echo ""
	@echo "Memory Statistics:"
	@curl -s http://localhost:8283/api/memory/stats | jq '.' || echo "Stats not available"

# Production Commands
start-prod:
	@echo "Starting Letta Memory Service with monitoring and proxy..."
	docker-compose --profile proxy --profile monitoring up -d
	@echo "Services starting..."
	@sleep 15
	@make health
	@echo ""
	@echo "Services available at:"
	@echo "  Memory API: http://localhost:8283"
	@echo "  Load Balancer: http://localhost:8284"
	@echo "  Monitoring: http://localhost:9090"

scale:
	@read -p "Enter number of Letta instances (current: 1): " replicas; \
	docker-compose up -d --scale letta=$$replicas
	@echo "Scaled to $$replicas instances"
	@make status

backup:
	@echo "Creating backup of Letta memory data..."
	@mkdir -p ./backups
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	docker exec letta-postgres pg_dump -U letta_user letta_memory_db > ./backups/memory_backup_$$timestamp.sql; \
	echo "Database backup saved to: ./backups/memory_backup_$$timestamp.sql"
	@docker exec letta-memory-server tar czf - /root/.letta > ./backups/letta_data_$$(date +%Y%m%d_%H%M%S).tar.gz
	@echo "Letta data backup completed"

restore:
	@echo "Available backups:"
	@ls -la ./backups/
	@read -p "Enter backup file name (memory_backup_YYYYMMDD_HHMMSS.sql): " backup_file; \
	if [ -f "./backups/$$backup_file" ]; then \
		docker exec -i letta-postgres psql -U letta_user letta_memory_db < ./backups/$$backup_file; \
		echo "Database restored from $$backup_file"; \
	else \
		echo "Backup file not found: $$backup_file"; \
	fi

# Maintenance Commands
clean:
	@echo "⚠️  This will remove all memory data. Are you sure? [y/N]"
	@read -r confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker-compose down -v; \
		docker system prune -f; \
		echo "Cleanup completed"; \
	else \
		echo "Cleanup cancelled"; \
	fi

monitor:
	@echo "Opening monitoring dashboard..."
	@which xdg-open > /dev/null && xdg-open http://localhost:9090 || \
	 which open > /dev/null && open http://localhost:9090 || \
	 echo "Open http://localhost:9090 in your browser"

shell:
	@echo "Connecting to Letta container..."
	docker exec -it letta-memory-server /bin/bash

# Performance testing
test-memory:
	@echo "Running memory performance tests..."
	@python ../scripts/test_memory_mcp_integration.py

benchmark:
	@echo "Running memory system benchmarks..."
	@for i in {1..10}; do \
		echo "Test $$i:"; \
		time curl -s http://localhost:8283/api/memory/stats > /dev/null; \
	done

# Kubernetes Commands (if deploying to K8s)
k8s-deploy:
	@echo "Deploying to Kubernetes..."
	kubectl apply -f ../kubernetes/letta-memory-service.yaml
	kubectl wait --for=condition=ready pod -l app=letta-memory -n thoth-memory --timeout=300s

k8s-status:
	@echo "Kubernetes deployment status:"
	kubectl get pods -n thoth-memory
	kubectl get svc -n thoth-memory

k8s-logs:
	kubectl logs -l app=letta-memory -n thoth-memory -f

k8s-clean:
	kubectl delete -f ../kubernetes/letta-memory-service.yaml

# Development helpers
dev-reset:
	@echo "Resetting development environment..."
	@make stop
	@docker volume prune -f
	@make start
	@echo "Development environment reset"

dev-logs-all:
	docker-compose logs -f

# Quick commands
up: start
down: stop
ps: status
exec: shell
