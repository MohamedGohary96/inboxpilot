.PHONY: install dev-backend dev-frontend build package clean

install:
	pip install -e backend/

dev-backend:
	cd backend && uvicorn todo_mail.app:app --host 127.0.0.1 --port 8765 --reload

dev-frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build
	rm -rf backend/todo_mail/dist
	cp -r frontend/dist backend/todo_mail/dist
	@echo "Frontend bundled → backend/todo_mail/dist/"

package: build
	pip install build --quiet
	cd backend && python3 -m build --wheel
	@echo "Wheel → backend/dist/"

clean:
	rm -rf backend/todo_mail/dist backend/dist backend/*.egg-info frontend/dist
