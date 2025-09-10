WORKER_PORT ?= 8000

init-network:
	docker network inspect mcp_rentcast_network >/dev/null 2>&1 || \
        docker network create --driver bridge mcp_rentcast_network
		
remove-network:
	docker network rm mcp_rentcast_network || true

# start all infrastructures.
start-infra: init-network
	@echo "Infrastructure setup complete"

# stop all infrastructures
stop-infra:
	@echo "Infrastructure stopped"

start: start-infra
	docker compose up -d --build

stop:
	docker compose down -t 60

start-server: start-infra
	@echo "Starting MCP Rentcast server on port $(WORKER_PORT)"
	PYTHONPATH=. python app/task_executor/mcps/rentcast/main.py

start-typescript:
	@echo "Starting TypeScript MCP server"
	npm start

test:
	PYTHONPATH=. pytest app/tests/ -v

build-typescript:
	npm run build

install-deps:
	pip install -r requirements.txt
	npm install

clean:
	docker compose down -t 0
	docker system prune -f
