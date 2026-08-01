# Security Policy

## Supported Versions

This project is under active development. Security fixes are applied to the latest version on the `main` branch only.

| Version         | Supported          |
| --------------- | ------------------ |
| `main` (latest) | :white_check_mark: |
| Older commits   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please **do not open a public GitHub issue**. Public issues are visible to everyone, including potential bad actors, before a fix is available.

Instead, please report it privately using one of the following methods:

### Preferred: GitHub Private Vulnerability Reporting
1. Go to the [Security tab](../../security) of this repository.
2. Click **"Report a vulnerability"**.
3. Fill in as much detail as possible (see "What to include" below).

This creates a private advisory that only the maintainer(s) can see until it's resolved.

### Alternative: Direct Email
If you're unable to use GitHub's private reporting feature, email:

**[macrointeligence@gmail.com]** 

Please include "SECURITY" in the subject line.

## What to Include in Your Report

To help us triage and fix the issue quickly, please include:

- A clear description of the vulnerability and its potential impact
- Steps to reproduce the issue (proof-of-concept code, requests, or screenshots if applicable)
- The affected component (e.g., backend API, frontend, Supabase configuration, authentication flow)
- Any suggested mitigation, if you have one
- Whether the vulnerability has already been publicly disclosed

## What to Expect

- **Acknowledgment:** We aim to acknowledge new reports within **3 business days**.
- **Initial assessment:** We aim to provide an initial assessment of severity and validity within **7 business days**.
- **Resolution timeline:** Depending on severity, we aim to release a fix within:
  - Critical: 7 days
  - High: 14 days
  - Medium/Low: 30 days
- **Credit:** With your permission, we're happy to credit you in the release notes or security advisory once the issue is resolved. Let us know in your report if you'd prefer to remain anonymous.

## Disclosure Policy

We follow a **coordinated disclosure** approach:
- Please give us a reasonable amount of time to investigate and patch the issue before any public disclosure.
- We will work with you to agree on a disclosure timeline once the report is triaged.
- Once a fix is released, we will publish a GitHub Security Advisory summarizing the issue (with credit, if desired).

## Scope

This policy covers the code in this repository, including:
- Backend API (FastAPI)
- Frontend application (Next.js)
- Supabase configuration and database access patterns defined in this repo

It does **not** cover:
- Third-party services this project depends on (e.g., Supabase's own infrastructure, Vercel, Render) — please report those directly to the respective provider
- Vulnerabilities requiring physical access to a user's device
- Social engineering attacks against maintainers or users

## Security Best Practices for Contributors

If you're contributing to this project:
- Never commit API keys, service role keys, `.env` files, or other secrets to the repository
- Use environment variables for all sensitive configuration
- Keep dependencies up to date and review Dependabot alerts promptly
- Follow the principle of least privilege when configuring Supabase Row Level Security (RLS) policies

---

Thank you for helping keep this project and its users safe.
