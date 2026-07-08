# Security Policy

## Supported Versions

The following versions of **FIFA Nexus AI** are supported for security updates:

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you identify a security vulnerability in this project, please **do not report it publicly via a GitHub issue**. Instead, report it responsibly:

1. Send an email to **security@fifanexus.ai** with the details of your finding.
2. Include a detailed description of the vulnerability, steps to reproduce, and any proof-of-concept code.
3. We will acknowledge your report within 48 hours and work with you to resolve it.

## Safety & Security Safeguards

FIFA Nexus AI implements strict security gates to protect physical stadium environments:
1. **Zero-LLM Safety Validator**: Dispatches to security incidents must go through the deterministic policy rules compiler. Generative AI suggestions are fully blocked if they dispatch unarmed personnel to security incidents.
2. **Fail-Closed API Authentication**: All write endpoints require the `X-API-Key` header. If the server does not have `API_KEY` configured in `.env`, all write requests fail closed with a `401 Unauthorized` response to prevent unauthenticated access.
3. **Rate Limiting**: Protects endpoints from Denial-of-Service (DoS) and brute force attacks.
