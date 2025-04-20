#!/bin/bash
# Run linting if ruff is available
if command -v ruff &> /dev/null; then
    echo "Running ruff linting..."
    ruff check --fix .
else
    echo "Ruff is not installed. Install with: pip install ruff==0.2.1"
fi