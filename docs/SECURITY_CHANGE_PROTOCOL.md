# AI Router Security Change Protocol

The Router is an untrusted execution component. Changes must preserve the
backend grant boundary and may not create a second authorization, billing, or
AI-routing authority.

Every change affecting prompts, tools, model routing, retrieval, files,
execution, provider calls, spend, or identity must document the trust boundary,
allowed resources, denied resources, token/cost/time limits, replay behavior,
audit event, and negative regression test. Uploaded and retrieved content is
data, never instructions. Production changes require `ALLOW_DEMO_AUTH=false`,
execution grants, Redis/shared replay protection, private storage, and real
provider credentials. Critical findings block release.
