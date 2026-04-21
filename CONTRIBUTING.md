```markdown
# Contributing to vigil-tui

First off, thank you for considering contributing to `vigil-tui`! This tool is built with a minimalist, "terminal-first" philosophy. Your help makes this project better for everyone.

## How Can I Contribute?

### Reporting Bugs
Before creating bug reports, please check the existing issues. When creating a bug report, please use the provided **Bug Report template** and include details like your OS, Python version, and Terminal emulator.

### Suggesting Enhancements
Enhancement suggestions are tracked as GitHub issues. Explain the feature and why it fits the minimalist vision of this project.

## Local Development Setup

1. **Fork** the repository on GitHub.

2. **Clone** your fork locally:
```bash
git clone https://github.com/YOUR_USERNAME/vigil-tui.git
cd vigil-tui
```

3. **Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

4. **Install in editable mode:**
```bash
pip install -e .
```

## Coding Standards

* **Textual Framework:** Adhere to `Textual` best practices (use BINDINGS, proper state management).
* **Minimalism:** Keep the code lightweight and resource-efficient.
* **Naming:** Use `snake_case` for variables and functions.
* **Comments:** Add brief English comments for complex logic.

## Pull Request Process

1. Create a new branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and test them locally.

3. Push to your fork and submit a **Pull Request**.

I will review your PR as soon as possible. By contributing, you agree that your contributions will be licensed under the project's MIT License. Thank you!
