# Alexa AI Brigade — your Echo, your AI

A private Amazon Alexa custom skill that routes your spoken questions to the
AI of your choice. Alexa keeps what she is good at — the "Alexa" wake word,
the Echo's far-field microphones, speech recognition, and the spoken reply —
while the actual answers come from **your AI** (Perplexity Sonar, OpenAI,
xAI Grok, or any OpenAI-compatible API) instead of Alexa's own brain.

To be precise about what this is: your Echo captures your voice, Alexa's
speech recognition transcribes it to text, your AI model writes the answer,
and Alexa's voice reads it aloud. It is **not** ChatGPT-style live voice
mode: it is a spoken, multi-turn question-and-answer conversation.

Works on **any Echo device** — nothing about this depends on the Echo model,
including both of yours:

- Echo Dot 3rd gen (2019–2020 refresh, `crumpet`, C78MP8)
- Echo 3rd gen (2019, `pascal`, R9P2A5 — verify the model sticker on the
  bottom; if it differs, this route still works, since it is model-agnostic)

No hardware modification, no jailbreak, no brick risk. Free hosting on
Amazon's "Alexa-hosted skill" infrastructure. In development/test mode the
skill is usable only on your own Amazon account.

**Note on your Home Assistant answer:** you said you're willing to set it
up — good news, you don't need it for this route. Home Assistant only
becomes relevant for the rooted local-satellite route described at the
bottom, which your two devices can't use today.

---

## What you get, and the honest limits

**You get:** a conversational voice assistant on every Echo in the house.
Say "Alexa, meu assistente" (pt-BR) or "Alexa, my assistant" (en-US), then
ask questions starting with common phrases (see usage below). It remembers
the conversation while the session is open, so you can ask follow-ups, and
it speaks its reply through the Echo's speaker.

**Honest limits (Alexa platform constraints, per [Amazon's docs](https://developer.amazon.com/en-US/docs/alexa/custom-skills/progressive-response-api-reference.html)):**

- **8-second response budget.** A custom skill must return its full
  response within 8 seconds. The skill sends an interim "hmm, let me
  think" while your AI works, but a slow model will time out. Use a fast
  model and keep `AI_TIMEOUT` at or below 5.5.
- **Turn-based, not barge-in.** You speak, it thinks, it answers, then
  waits for your next turn. You cannot interrupt it mid-sentence.
- **Carrier phrases.** This interaction model uses `AMAZON.SearchQuery`,
  which [Amazon requires](https://developer.amazon.com/en-US/docs/alexa/custom-skills/slot-type-reference.html)
  to be preceded by a carrier phrase. The model includes ~19-20 natural
  starters per language ("o que é…", "me explique…", "quero saber…",
  "quem é…", "quando…", "pesquise…" and so on), and the backend restores
  the carrier so your AI receives the full question exactly as spoken.
  Sentences that don't match any starter fall through to a fallback that
  asks you to retry with one.
- **Alexa does the listening and speaking.** Your AI receives text and
  returns text. This route does not (and cannot) reuse the native voice
  modes of consumer subscriptions like ChatGPT Plus or Perplexity Pro —
  those live inside each provider's own app.

---

## Setup (about 30 minutes, no coding)

### 1. Create the skill

1. Create a free developer account at
   [developer.amazon.com](https://developer.amazon.com) (your existing
   Amazon login works).
2. Go to the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) →
   **Create Skill**.
3. Skill name: `AI Brigade`. Primary locale: **Portuguese (Brazil)** (or
   English (US) — models for both are included).
4. Type of experience: **Other** → Model: **Custom** → Hosting services:
   **Alexa-hosted (Python)** → Template: **Start from scratch**. This
   gives you free AWS Lambda hosting managed by Amazon ([About Alexa-hosted
   skills](https://developer.amazon.com/en-US/docs/alexa/hosted-skills/build-a-skill-end-to-end-using-an-alexa-hosted-skill.html)).
5. Fastest path — **Import Skill** (needs a **public** repo URL): on
   the template screen choose **Import Skill** and paste this
   repository's GitHub URL. The repo follows the import contract
   (`skill.json` + `interactionModels/custom/` + `lambda/`), so the
   console pre-fills both the interaction model and the code. This repo
   is private by default; ask and it can be flipped public (it contains
   no secrets — keys are pasted only in the console), or use the manual
   path below with either visibility.

   Manual path — in the **Build** tab → **JSON Editor**, replace
   everything with the contents of
   `interactionModels/custom/pt-BR.json` (or `en-US.json`), then
   **Save** and **Build model**. The models use `AMAZON.SearchQuery`
   with carrier phrases as
   [required by Amazon](https://developer.amazon.com/en-US/docs/alexa/custom-skills/slot-type-reference.html).

### 2. Paste the backend and configure your key

1. In the skill's **Code** tab, replace the contents of `lambda_function.py`
   with the version in this package (`lambda/lambda_function.py`).
   Single file, Python standard library only — no dependencies to install.
2. At the top of that file is a `CONFIG` block. Fill in your provider and
   API key there, for example:

   ```python
   CONFIG = {
       "AI_PROVIDER": "perplexity",
       "PERPLEXITY_API_KEY": "pplx-...your key...",
       ...
   }
   ```

   If your hosting shows an environment-variables editor (your own Lambda
   does; the Alexa-hosted Code tab may), env vars override the CONFIG
   block — either path works.
3. **Save** and **Deploy** (top of the Code tab).

### 3. Get an API key

- **OpenCode (Zen or Go):** sign in at
  [opencode.ai/auth](https://opencode.ai/auth) and copy your API key.
  Set `AI_PROVIDER` to `opencode`, paste the key in `OPENCODE_API_KEY`,
  and pick a model ID in `OPENCODE_MODEL` from the live list at
  `https://opencode.ai/inference/v1/models` — it includes fast, cheap
  options (e.g. `deepseek-v4.1-flash-free`, `glm-5.3-flash-free`) and
  stronger ones. Pay-as-you-go (Zen/Console) keys work against the
  default base URL, the officially documented
  `https://opencode.ai/inference/openai/v1`
  ([OpenCode Zen docs](https://opencode.ai/docs/zen/)); the community
  path `https://opencode.ai/zen/v1` is also live. **Go subscription
  keys are not officially documented for direct API use** — test yours;
  if the default base rejects it, some gateway integrations document
  `https://opencode.ai/zen/go` (unverified path, set it via
  `OPENCODE_BASE_URL`).
- **Charm Hyper:** get a key (`sk-hyper-...`) at
  [hyper.charm.land](https://hyper.charm.land). Set `AI_PROVIDER` to
  `hyper` and paste the key in `HYPER_API_KEY`. The default model
  `deepseek-v4.1-flash` is fast and cheap — good for voice. Both
  endpoints were live-verified in October 2026 (their model catalogs
  respond publicly and the chat endpoint requires the key).
- **Perplexity (Sonar):** keys at
  [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api). The
  Sonar API is OpenAI-compatible. Your **Pro subscription does not include
  API usage** — [Perplexity's help center](https://www.perplexity.ai/help-center/en/articles/10354847-api-payment-and-billing)
  states API credits are purchased separately, pay-as-you-go. Check your
  [API billing page](https://www.perplexity.ai/settings/api) to see what
  applies to your account.
- **OpenAI:** [platform.openai.com/api-keys](https://platform.openai.com/api-keys),
  separate pay-per-use billing from a ChatGPT subscription.
  `gpt-4o-mini` is a common choice for voice-sized answers.
- **xAI (Grok):** [console.x.ai](https://console.x.ai), OpenAI-compatible
  at `https://api.x.ai/v1`. Note that a Grok consumer subscription is not
  the same thing as an xAI developer API account — you need the latter.
  Set both `XAI_API_KEY` and `XAI_MODEL` (pick a current fast model).

**Model choice for the 8-second window:** prefer fast, small models —
`deepseek-v4.1-flash` (Hyper, the default), the free flash models on
OpenCode, `sonar` (Perplexity) or a small/fast OpenAI model. `sonar-pro`
is more capable but does live web search and is more likely to exceed the
response budget on heavy queries.

### 4. Test and use

1. In the skill's **Test** tab, enable **Development** testing, then type
   `meu assistente` in the simulator to confirm the skill responds.
2. On any Echo on your account, say:
   - **"Alexa, meu assistente"** → it opens and says "Pronto. Pode falar."
   - Then ask with a starter phrase: *"o que é fotossíntese?"* → answer →
     *"e me explique por que ela é importante"* → it remembers the context.
   - One-shot also works: **"Alexa, pergunte ao meu assistente o que é a
     internet das coisas"**.
   - Say **"encerrar"** to end the conversation.
3. Both your Echo Dot 3rd gen and Echo 3rd gen pick it up immediately —
   dev-mode skills are live on every device registered to your Amazon
   account.

### 5. Run the automated tests (optional)

```bash
cd alexa-ai-brigade
python3 tests/test_skill.py
```

35 local mock assertions: request routing, carrier-phrase restoration,
conversation memory, progressive responses, SSML escaping, timeout
fallback inside the 8-second budget (including a delayed directives
endpoint and a slowly-trickling response body), both locales. These
verify the skill logic against a simulated Alexa and a fake AI provider —
they are not a test against your physical Echo or a real AI provider, and
the provider adapters have not been exercised against the live APIs. The
remaining steps (account creation, console paste, key config) are done by
you in the console.

---

## Switching brains

Change `AI_PROVIDER` (and the corresponding key/model) in the CONFIG
block, then redeploy. The bridge speaks the standard OpenAI
`/chat/completions` protocol, so it also works with Groq, Together,
OpenRouter and other hosted OpenAI-compatible endpoints. A home server
(like Ollama on your LAN) would only work if you expose it over public
HTTPS, which is not recommended — stick to hosted endpoints.

## Troubleshooting

- **"There was a problem with the requested skill's response"** — the model
  exceeded the 8-second window. Switch to a faster model, lower
  `AI_MAX_TOKENS`, or lower `AI_TIMEOUT` (keep it at or below 5.5).
- **"Ainda não configurei a chave de API"** — the key is missing for the
  chosen `AI_PROVIDER`.
- **Model build rejects `AMAZON.SearchQuery`** — some console/locale
  combinations restrict built-in slot types. Use the en-US model in that
  case.
- **Alexa keeps saying she doesn't know / skill doesn't open** — make sure
  the Test tab is in Development mode and the device is on the same
  Amazon account; also confirm the model build succeeded (Build tab).
- **Your question wasn't captured** — start it with one of the carrier
  phrases; unmatched phrases fall to the fallback intent.

## Privacy and cost notes

- In development mode the skill is private to your account; don't publish
  it to the skill store (that would make your endpoint publicly invocable).
- Your spoken queries are transcribed by Amazon's cloud ASR (as with any
  Alexa utterance), then sent to your chosen AI provider with your key.
- Cost depends entirely on your provider and usage; check each provider's
  pricing page — voice-sized Q&A is among the cheapest kinds of API usage
  (short prompts, capped response length).

---

## The jailbreak research (what "jailbreak" means for your two devices)

Reverse-engineering status as of October 2026, from published community
research — documentation-based; your physical units were not inspected:

| Device | Codename | Rootable today? |
|---|---|---|
| Echo Dot 3rd gen (2018, D9N29T) | `donut` | **Yes** — unlock/root/TWRP published ([XDA thread](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-dot-3rd-gen-2018-donut.4801400/)) |
| **Echo Dot 3rd gen refresh (yours, C78MP8)** | `crumpet` | No publicly reproducible supported unlock found in the reviewed sources; research is active ([crumpet feasibility study](https://github.com/Manantra/echo-dot-crumpet-research)) |
| **Echo 3rd gen (yours, R9P2A5)** | `pascal` | No publicly reproducible supported unlock found in the reviewed sources; listed as a candidate on the same MT8516 SoC platform ([LibreEcho status table](http://dev.libreecho.org/)) |

The best current jailbreak-and-repurpose project is
[echo-dot-assist](https://github.com/Gamer92000/echo-dot-assist): it roots
supported Echos and replaces the Alexa client with `hassmic`, a daemon that
turns the Echo into a fully local Home Assistant voice satellite — keeping
Amazon's mic array and wake-word engine, cutting the cloud. It supports
`donut`, `biscuit` (Dot 2) and `radar` (Echo 2) — but explicitly **not**
`crumpet`, and `pascal` isn't listed.

Practical implications for you:

- Rooting requires physical access (test pads, soldering), exact vulnerable
  firmware, carries brick risk, and the device must never reach Amazon
  again. For `crumpet` and `pascal`, no publicly reproducible supported
  unlock was found in the reviewed sources, so the hardware route is
  closed for now.
- If an exploit ever lands for either codename, a local-satellite port
  with working audio support would still be needed for that hardware —
  the [Home Assistant community thread](https://community.home-assistant.io/t/echo-dot-3rd-gen-2018-as-a-fully-local-assist-satellite-keeping-amazons-mic-array-and-wake-word-engine/1025971)
  tracks that work.
- This Alexa-skill bridge is a practical way to put your own AI behind
  the wake word on your two devices with stock firmware — which is what
  this package delivers.

## Package contents

```
skill.json                    skill manifest (Alexa import contract)
interactionModels/custom/     interaction models (pt-BR, en-US)
lambda/lambda_function.py     the skill backend (single file, stdlib only,
                              CONFIG block at the top)
lambda/requirements.txt       empty — no dependencies needed
tools/
  build_models.py             regenerates the interaction models and checks
                              carrier/prefix consistency with the backend
tests/
  test_skill.py               35 local mock assertions (simulated Alexa + fake AI)
  fake_ai_server.py           local stand-in for the AI + directives APIs
README.md                     this guide
```

The provider presets in the backend: `perplexity`, `openai`, `xai`,
`opencode`, `hyper`, and `custom` (any OpenAI-compatible endpoint).
