# Contributing to FIFA Nexus AI

Thank you for your interest in contributing to **FIFA Nexus AI**! We appreciate your help in building a resilient, event-driven operational intelligence platform for the FIFA World Cup 2026.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/ramakrishnanyadav/FIFA-NEXUS-AI.git
   cd FIFA-NEXUS-AI
   ```

2. **Environment Setup**:
   Copy `.env.example` to `.env` and configure your local settings:
   ```bash
   cp .env.example .env
   ```

3. **Install Dependencies**:
   ```bash
   py -3.11 -m venv venv
   source venv/bin/activate # or .\venv\Scripts\activate on Windows
   pip install -r backend/requirements.txt
   ```

4. **Linting and Formatting**:
   We use **Ruff** for linting and formatting. Run:
   ```bash
   ruff check backend/app
   ```

## Pull Request Guidelines

1. **Create a Branch**:
   Use descriptive names, e.g., `feature/add-rate-limits` or `bugfix/fix-db-leak`.
2. **Write Tests**:
   Ensure any bug fixes or features are accompanied by corresponding tests in `backend/tests/`.
3. **Run the Test Suite**:
   ```bash
   pytest backend/tests/
   ```
4. **Submit the PR**:
   Ensure all checks pass and complete the pull request template.
