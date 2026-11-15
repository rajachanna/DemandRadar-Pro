# Security & Responsible Use

DemandRadar Pro is intended for an individual operator or small internal team, running on a trusted machine or behind approved access controls.

## Data sources and platform policy

The public GitHub issue search and Hacker News Algolia APIs are read-only and use curated searches; each platform's terms and rate limits still apply. A GitHub issue or Hacker News post is not inherently a client request, paid job, or consent to receive a solicitation. Never scrape private contacts or circumvent login restrictions. There is deliberately **no** LinkedIn, Fiverr, Upwork or email auto-messaging.

## Security boundaries

- Set a unique, random `DR_OPERATOR_KEY` with at least 24 characters. No key -> private endpoints return 503. Do not embed key in a frontend bundle or commit secrets.
- Configure HTTPS, reverse-proxy IP/identity allowlisting and server-side rate limits before internet exposure. An API key alone is not a full SaaS authentication system.
- Use `docker compose` on loopback or start CLI on `127.0.0.1`. Never put a public server behind weak operator credentials.
- Database lives in a writable directory. Back it up securely, protect at-rest content, rotate keys on incident, and restrict access to your staff.
- Public URLs entered manually are *not fetched*. Only hardcoded official GitHub API, HN Algolia and optional OpenAI/Telegram endpoints are used.
- AI drafting may include publicly available opportunity text. Do not input private information into a third-party model without authorization; review generated claims carefully.
- Optional Telegram only sends to a configured owner chat when they click the notification button. It does not contact a prospect.
- False positives, impersonation and payment scams exist. Verify identity, payment and platform rules before engaging.

## Reports

Avoid sending real passwords, API keys or other sensitive information in issues. Use GitHub security reporting mechanisms or private contact channels.
