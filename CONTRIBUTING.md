## 🤝 Contributing

Thank you for helping improve Quranic accessibility. This guide keeps contributions smooth, consistent, and aligned with our workflow.

## 🧭 Branch Strategy
- **Protected branches**: `main`, `staging` (PRs only; no direct commits)
- **Active development**: `{feature_branch}` (direct commits allowed)
- **Flow**: `staging` (PR) → `main` (PR). Do not skip stages.
- **Features**: branch from `staging` as `feat/<short-description>`

## 🛠️ Workflow
1) Start from `staging` or a `feat/*` branch
2) Make small, focused commits with clear messages
3) Test locally; fix linter/type errors
4) Push to `origin/staging` or open a PR from `feat/*` to `staging`
5) Request review; address feedback; keep PRs concise

## 🧰 Development Setup
- Python 3.13+
- Docker (recommended) or native setup
- See `README.md` → Quick Start

## 🧪 Testing
- Use `pytest` (not `manage.py test`)
- Follow Arrange–Act–Assert (AAA)
- Name tests: `test_<function_name>_where<criteria>_should<expected_results>`

## 📦 API & Errors
- APIs: Django Ninja; document responses
- 400s: `apps.core.ninja_utils.errors.ItqanError`
- 403s: `rest_framework.exceptions.PermissionDenied`
- Document errors with `NinjaErrorResponse` when applicable

## 🧹 Style & Quality
- Python 3.13, Django 5.2 compatible
- Type hint all functions
- Prefer `AwareDateTime` in Schemas
- Avoid unnecessary try/except; keep control flow clear

## 🚦 CI/CD & Deployment
- GitHub Actions enforce branch flow and protections
- Deployments run only on successful PR merges to protected branches

## ⚖️ Licensing
By contributing, you license your work under the MIT License (see `LICENSE`).

## 🆘 Getting Help & Contact
- **GitHub Issues**: Technical issues and bugs (include context, steps to reproduce, and expected behavior)
- **Discussions**: General questions and ideas
- **Discord**: https://discord.gg/24CskUbuuB
- **Email**: connect@itqan.dev

## 📜 Code of Conduct
Be respectful and constructive. Assume positive intent. Report unacceptable behavior to maintainers.

## 🙏 Recognition
We deeply appreciate every contributor—maintainers, reviewers, issue reporters, testers, translators, and Quranic data publishers.

- Individuals and organizations are welcome to contribute
- Significant contributions will be highlighted in release notes
- All contributors will be acknowledged on the GitHub contributors page

Jazakum Allahu khairan for advancing Quranic accessibility!
