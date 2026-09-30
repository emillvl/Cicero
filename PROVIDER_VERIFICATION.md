# Provider and usage evidence

Checked September 10, 2026. This is documentation and offline adapter verification, not authenticated verification with a real account. No private provider keys were retrieved or used.

## Model selection

Models come from each selected provider's catalog, or from an exact ID entered by the user if the catalog is unavailable. The application ships no model names, fixed model recommendations or per-model operating profiles. New selections use common conservative operating budgets, which advanced settings can override. Catalog availability does not establish inference access, prompt compatibility, pricing or maximum token capacity.

The configured provider addresses remain the existing official Google, Anthropic, OpenAI, DeepSeek, Model Studio and Z.AI connections. NVIDIA is absent from new-run selection; its hostname remains recognizable for old checkpoints. Regional Model Studio setup and custom-server credential isolation are retained.

## Reported token usage

The app reads response usage before validating translation or review content. Rejected/truncated text therefore does not discard its reported counts. Each request attempt is saved before sending; a response with no usable counts remains unknown. No text-length estimate is substituted for API-reported usage.

- OpenAI-compatible responses expose prompt, completion and total tokens. Cache and reasoning breakdowns belong within those totals and are not added again. [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- Anthropic's total input includes ordinary input, cache-read input and cache-creation input. The adapter adds these input categories once and then adds output. [Anthropic Messages reference](https://platform.claude.com/docs/en/api/typescript/messages)
- DeepSeek reports cache hits and misses within prompt tokens. The hit count is retained separately without adding it to the prompt total. [DeepSeek Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion/)
- Z.AI documents cached input under prompt-token details. [Z.AI caching guide](https://docs.z.ai/guides/capabilities/cache)
- Model Studio documents compatible prompt/completion usage and cache details. [Model Studio compatible Chat API](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-api-via-openai-chat-completions)
- Google remains on its existing compatible endpoint. The tracker reads compatible usage if supplied; missing fields remain unknown. [Google compatibility guide](https://ai.google.dev/gemini-api/docs/openai)

Counts represent usage by this run, not remaining free tokens. Startup samples and explicit retries are included; catalog and balance GET requests are excluded. No free/paid status is inferred from an API key. Counts from before this feature cannot be reconstructed from saved text.

## Direct account balance

Only one supported balance adapter was established using the existing inference credential:

| Connection | End-of-session behavior |
| --- | --- |
| Official DeepSeek server | GET https://api.deepseek.com/user/balance using the existing Bearer credential. Show the returned available total, granted balance and topped-up balance in each returned currency. Also show when the provider reports insufficient funds. |
| Google, OpenAI, Anthropic, Z.AI, Model Studio, legacy NVIDIA and custom servers | Show balance / remaining free quota unavailable through this connection. Do not try guessed or undocumented endpoints, infer a balance from rate limits, or request extra billing credentials. |

DeepSeek documents both its balance fields and the insufficient-balance flag. These are account-wide monetary balances; granted funds are not a universal free-token allowance. [DeepSeek balance API](https://api-docs.deepseek.com/api/get-user-balance/)

The unavailable status is an implementation limit, not a claim that these companies have no billing APIs. Google's guide directs quota and billing monitoring to AI Studio. OpenAI and Anthropic document organization usage/cost interfaces with administrative access; those historical reports are different from a remaining balance. Alibaba Cloud has a separate account-billing operation. These integrations are not added to the translator. [Google billing](https://ai.google.dev/gemini-api/docs/billing), [OpenAI organization usage](https://developers.openai.com/api/reference/ruby/resources/admin/subresources/organization/subresources/usage/methods/completions), [Anthropic usage/cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api), [Alibaba Cloud account balance](https://www.alibabacloud.com/help/en/user-center/developer-reference/api-bssopenapi-2017-12-14-queryaccountbalance)

Balance lookup happens once per selected account at completion or interruption, has a short timeout, and cannot invalidate translation results. No balance lookup is made for a completed resume without keys. No monetary cost estimate, manual rate entry, currency conversion, dashboard scraping or account-top-up action is implemented.

## Startup checks

Choosing yes runs seven small samples through all five assigned roles and their actual prompts: Translator once, Blind Critic once, Alignment Inspector twice, Fixer once and Final Auditor twice. Good/bad source comparisons test explicit verdicts; the Blind Critic can return either well-formed verdict. Sharing one model still exercises every role prompt.

Choosing skip omits samples and retains normal translation reviews. Choosing no stops inference. Sample failures offer explicit retry of only the failed sample. Short samples do not prove book-length capacity or sustained service reliability.
