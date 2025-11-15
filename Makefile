.PHONY: test test-quiet test-stop start

test: ## Run all tests with verbose output
	pytest -v --tb=short

test-quiet: ## Run tests quietly
	pytest -q

test-stop: ## Stop on first failure
	pytest -x -v --tb=short

start: ## Run the Telegram bot application
	python -m src.main
