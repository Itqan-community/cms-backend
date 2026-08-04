## Contributing

Thank you for helping improve Quranic accessibility. This guide keeps contributions smooth, consistent, and aligned with our workflow.

## Finding Something to Work On

Planned work lives on the **[Fanar board](https://github.com/orgs/Itqan-community/projects/12)** — the execution view of our [1448 Q1 & Q2 roadmap](./docs/ROADMAP.md). Every item is a real issue with context, acceptance criteria, and links to the code it touches.

- **New here?** Filter by [`Good First Issue`](https://github.com/Itqan-community/cms-backend/issues?q=is%3Aissue+is%3Aopen+label%3A%22Good+First+Issue%22) — small, well-bounded, and unlikely to collide with in-flight work.
- **Want something substantial?** Filter by [`Help Wanted`](https://github.com/Itqan-community/cms-backend/issues?q=is%3Aissue+is%3Aopen+label%3A%22Help+Wanted%22).
- **Skip anything labelled `blocked`** — those wait on a decision or a prerequisite task, and the issue says which.
- Issues are grouped by `epic:` labels so you can follow one thread end to end rather than jumping between areas.

Comment on an issue before you start so two people don't build the same thing. If you stall partway, say so — that's useful information, not a failure.

## Branch Strategy
- **Protected branches**: `main`, `staging` (PRs only; no direct commits)
- **Active development**: `{feature_branch}` (direct commits allowed)
- **Flow**: `staging` (PR) → `main` (PR). Do not skip stages.
- **Features**: branch from `staging` as `feat/<short-description>`

## Workflow
1) Start from `staging` or a `feat/*` branch
2) Run `pre-commit install` if you have not already (one-time setup)
3) Make small, focused commits with clear messages
4) Test locally; fix linter/type errors
5) Push to `origin/staging` or open a PR from `feat/*` to `staging`
6) Request review; address feedback; keep PRs concise

**All PRs must pass linting checks to be merged.** Pre-commit hooks run automatically on each commit to catch issues early.

## Development Setup
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management (`uv sync` to install)
- [pre-commit](https://pre-commit.com/) for linting hooks (`pre-commit install` to activate)
- Docker (recommended) or native setup
- See `README.md` -> Quick Start

## Testing
- Use `pytest` (not `manage.py test`)
- Follow Arrange–Act–Assert (AAA)
- Name tests: `test_<function_name>_where<criteria>_should<expected_results>`

## API & Errors
- APIs: Django Ninja; document responses
- 400s: `apps.core.ninja_utils.errors.ItqanError`
- 403s: `rest_framework.exceptions.PermissionDenied`
- Document errors with `NinjaErrorResponse` when applicable

## Style & Quality
- Python 3.13, Django 5.2 compatible
- Type hint all functions
- Prefer `AwareDateTime` in Schemas
- Avoid unnecessary try/except; keep control flow clear
- Run `pre-commit run --all-files` to check linting before pushing

## CI/CD & Deployment
- GitHub Actions enforce branch flow and protections
- Deployments run only on successful PR merges to protected branches

## Licensing
By contributing, you license your work under the MIT License (see `LICENSE`).

## Getting Help & Contact
- **GitHub Issues**: Technical issues and bugs (include context, steps to reproduce, and expected behavior)
- **Discussions**: General questions and ideas
- **Discord**: https://discord.gg/24CskUbuuB
- **Email**: connect@itqan.dev

## Code of Conduct
Be respectful and constructive. Assume positive intent. Report unacceptable behavior to maintainers.

## Recognition
We deeply appreciate every contributor—maintainers, reviewers, issue reporters, testers, translators, and Quranic data publishers.

- Individuals and organizations are welcome to contribute
- Significant contributions will be highlighted in release notes
- All contributors will be acknowledged on the GitHub contributors page

## Important For AI/LLM Users

This is an open-source project that aims to help the Muslim community and provide a way to distribute Quranic content through safe, verified channels. For it to outlive any one of us, the people contributing need to genuinely understand how it works internally — that understanding is the thing we are actually building.

**Using AI to help you work is welcome and expected.** We all have subscriptions. What we are asking is that you stay the author of your contribution, not a middleman between the maintainer and a model.

### Most importantly: you need to know what your code does, and test it

Before you open a PR, make sure you:

- **understand** the code you're submitting, well enough to explain why it works
- **ran** it on your own machine and saw it behave correctly
- **tested** it — including the cases you expect to fail

Many hours have been lost verifying code that its own author never read or ran, and that cost lands on every maintainer. If you copy an issue into an agent, paste back whatever it produces, and open a PR you haven't read, you are taking more from this project than you are giving it.

If you're not planning to work that way on a given issue, please leave it for someone who will. And if you get stuck halfway, say so in the comments — a half-finished PR you understand is far more welcome than a complete one you don't.

Jazakum Allahu khairan for advancing Quranic accessibility!
