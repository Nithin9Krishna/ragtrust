# LinkedIn launch post

Ready to copy following the October 8, 2026 public launch verification. This post has not been published to LinkedIn. Attach [the launch graphic](assets/ragtrust-linkedin.png) when sharing.

## Ready-to-copy post

How do you test a RAG app when you only have a handful of trusted examples?

I've been building RAGTrust to make that workflow easier to inspect: start with golden Q&A and source evidence, create evaluation cases, review the checks, and export a versioned dataset.

The public demo gives each browser session a temporary workspace. You can:

- Load the included IT-security sample or upload non-confidential demo data.
- Follow planning, generation, validation, bounded repairs, and human review.
- Download JSONL/CSV datasets with case assessments and quality reports.
- Compare your RAG's recorded answers, or connect a compatible public HTTPS endpoint, against a released dataset.

One important limit: the public workspace uses deterministic fixtures, not live AI generation. Its endpoint comparison reports latency, errors, lexical overlap, and abstention phrase matching. Those scores are not proof of factual accuracy or faithfulness. The source also includes an optional Microsoft Foundry integration for running the agent workflow in your own environment.

Try it: https://ragtrust-sainithin-public-2026.azurewebsites.net/
Source: https://github.com/Nithin9Krishna/ragtrust

If you build RAG systems, try a small example, download your exports, and tell me which failure case or evaluation signal you'd want next. Feedback and GitHub issues are welcome.

#RAG #LLMEvaluation #OpenSource #MicrosoftFoundry
