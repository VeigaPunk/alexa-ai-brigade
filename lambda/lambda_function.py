# -*- coding: utf-8 -*-
"""
Alexa AI Brigade — private custom skill backend.

Bridges an Amazon Echo (any model) to the AI provider of your choice
(Perplexity Sonar, OpenAI, xAI Grok, or any OpenAI-compatible endpoint).

Pure Python standard library — no dependencies to install, works in an
Alexa-hosted skill with zero packaging.

Configuration: fill in the CONFIG dict below (easiest in the Alexa
console Code tab). If your hosting supports environment variables (e.g.
your own Lambda), env vars override the CONFIG dict.
"""

import html
import json
import os
import threading
import urllib.request

# --------------------------------------------------------------------------
# Configuration — edit this block in the Alexa console "Code" tab
# --------------------------------------------------------------------------

CONFIG = {
    # openai | perplexity | xai | custom
    "AI_PROVIDER": "perplexity",

    # Perplexity (Sonar) — https://www.perplexity.ai/settings/api
    "PERPLEXITY_API_KEY": "",
    "PERPLEXITY_MODEL": "sonar",  # sonar = faster; sonar-pro = better, slower

    # OpenAI — https://platform.openai.com/api-keys
    "OPENAI_API_KEY": "",
    "OPENAI_MODEL": "gpt-4o-mini",

    # xAI (Grok) — https://console.x.ai — set both key and a current model
    "XAI_API_KEY": "",
    "XAI_MODEL": "",

    # OpenCode — https://opencode.ai/auth (Zen/Console pay-as-you-go keys)
    # Go subscription keys are NOT officially documented for direct API use;
    # if your key is a Go key, test it — and if it fails, try
    # OPENCODE_BASE_URL = "https://opencode.ai/zen/go" (unverified path).
    "OPENCODE_API_KEY": "",
    "OPENCODE_MODEL": "",  # pick from https://opencode.ai/inference/v1/models
    "OPENCODE_BASE_URL": "",

    # Charm Hyper — https://hyper.charm.land
    "HYPER_API_KEY": "",
    "HYPER_MODEL": "deepseek-v4.1-flash",

    # Any OpenAI-compatible endpoint (Groq, OpenRouter, ...)
    "CUSTOM_BASE_URL": "",
    "CUSTOM_API_KEY": "",
    "CUSTOM_MODEL": "",

    # Overall wall-clock seconds the model call may take. Alexa requires
    # the full response within 8 s; the skill also spends up to ~1 s on
    # the interim "thinking" speech, so keep this at or below 5.5.
    "AI_TIMEOUT": "5.0",

    # Response length cap (tokens). Lower = faster.
    "AI_MAX_TOKENS": "400",

    # Optional extra standing instructions for the model (merged into
    # the system prompt).
    "AI_SYSTEM_PROMPT": "",
}

# --------------------------------------------------------------------------
# Carrier phrases and their intents
#
# Amazon requires each AMAZON.SearchQuery sample to include a carrier
# phrase, and Alexa strips the carrier from the captured slot value.
# The interaction model therefore uses one intent per carrier phrase,
# and the handler restores the carrier below so the AI sees the full
# question exactly as spoken.
# --------------------------------------------------------------------------

CARRIER_PREFIXES = {
    "pt-BR": {
        "AskQueryIntent": "",
        "WhatIsIntent": "o que é ",
        "WhatAreIntent": "o que são ",
        "WhoIsIntent": "quem é ",
        "WhoWasIntent": "quem foi ",
        "WhenIntent": "quando ",
        "WhereIntent": "onde ",
        "WhyIntent": "por que ",
        "HowIntent": "como ",
        "WhichIntent": "qual ",
        "WhichPluralIntent": "quais ",
        "HowMuchIntent": "quanto ",
        "HowMuchFIntent": "quanta ",
        "ExplainIntent": "me explique ",
        "TellMeIntent": "me diga ",
        "TalkAboutIntent": "fale sobre ",
        "WantToKnowIntent": "quero saber ",
        "SearchIntent": "pesquise ",
        "AboutIntent": "sobre ",
        "IsItTrueIntent": "é verdade que ",
    },
    "en-US": {
        "AskQueryIntent": "",
        "WhatIsIntent": "what is ",
        "WhatAreIntent": "what are ",
        "WhoIsIntent": "who is ",
        "WhoWasIntent": "who was ",
        "WhenIntent": "when ",
        "WhereIntent": "where ",
        "WhyIntent": "why ",
        "HowIntent": "how ",
        "WhichIntent": "which ",
        "TellMeAboutIntent": "tell me about ",
        "TellMeIntent": "tell me ",
        "SearchForIntent": "search for ",
        "FindOutIntent": "find out ",
        "WantToKnowIntent": "i want to know ",
        "CanYouIntent": "can you ",
        "DoYouKnowIntent": "do you know ",
        "IsItTrueIntent": "is it true that ",
    },
}

QUERY_INTENTS = {name for locale in CARRIER_PREFIXES.values()
                for name in locale}

# --------------------------------------------------------------------------
# Locale strings
# --------------------------------------------------------------------------

STRINGS = {
    "pt-BR": {
        "greet": "Pronto. Pode falar. Comece com frases como o que é, me explique ou quero saber.",
        "reprompt": "Pode falar.",
        "thinking": "Hmm, deixa eu pensar.",
        "empty": "Não entendi. Tente começar com o que é, me explique, ou quero saber.",
        "slow": "Isso demorou mais do que o esperado. Tente perguntar de novo, de forma mais curta.",
        "provider": "Houve um problema com o provedor de IA. Verifique a chave e o modelo escolhido.",
        "nokey": "Ainda não configurei a chave de API do assistente. Veja o guia de instalação.",
        "nomodel": "Ainda não escolhi um modelo para o assistente. Veja o guia de instalação.",
        "help": "Você conversa comigo normalmente. Comece com frases como o que é, me explique ou quero saber, e eu respondo com a sua IA. Diga encerrar quando quiser parar.",
        "bye": "Até mais.",
    },
    "en-US": {
        "greet": "Ready. Go ahead. Start with phrases like what is, tell me about, or search for.",
        "reprompt": "Go ahead.",
        "thinking": "Hmm, let me think.",
        "empty": "I didn't catch that. Try starting with what is, tell me about, or search for.",
        "slow": "That took longer than expected. Try asking again, a bit shorter.",
        "provider": "There was a problem with the AI provider. Check the key and the chosen model.",
        "nokey": "The assistant API key is not configured yet. Check the setup guide.",
        "nomodel": "No model was chosen for the assistant yet. Check the setup guide.",
        "help": "Just talk to me naturally. Start with phrases like what is, tell me about, or search for, and I'll answer with your AI. Say stop when you're done.",
        "bye": "Bye for now.",
    },
}

SYSTEM_PROMPT = (
    "You are a voice assistant embedded in a smart speaker. "
    "Always reply in the same language the user is speaking. "
    "Keep answers short and spoken-word friendly: at most 4 sentences, "
    "plain text only, no markdown, no lists, no emojis, no URLs. "
    "Be warm, direct and useful. You may remember earlier turns of this "
    "conversation."
)

HISTORY_LIMIT = 16  # messages kept in the session (user + assistant)


def strings_for(locale):
    return STRINGS.get(locale, STRINGS["en-US"])


def setting(name):
    """Environment variable wins over the CONFIG dict."""
    return os.environ.get(name) or CONFIG.get(name) or ""


# --------------------------------------------------------------------------
# Response helpers
# --------------------------------------------------------------------------

def ssml(text):
    return "<speak>" + html.escape(text or "") + "</speak>"


def build_response(speech_text, reprompt_text, should_end, attributes):
    """Build an Alexa response envelope (custom skill JSON schema)."""
    response = {
        "outputSpeech": {"type": "SSML", "ssml": ssml(speech_text)},
        "shouldEndSession": should_end,
    }
    if reprompt_text is not None:
        response["reprompt"] = {
            "outputSpeech": {"type": "SSML", "ssml": ssml(reprompt_text)}
        }
    return {
        "version": "1.0",
        "sessionAttributes": attributes or {},
        "response": response,
    }


def send_progressive(event, text):
    """Best-effort interim speech (VoicePlayer.Speak directive).

    Sent synchronously with a short cap so it cannot eat the response
    budget. It does NOT extend Alexa's overall 8 second window.
    """
    try:
        system = event["context"]["System"]
        url = system["apiEndpoint"].rstrip("/") + "/v1/directives"
        payload = {
            "header": {"requestId": event["request"]["requestId"]},
            "directive": {"type": "VoicePlayer.Speak", "speech": ssml(text)},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + system["apiAccessToken"],
            },
        )
        urllib.request.urlopen(req, timeout=1.0)
    except Exception:
        pass


# --------------------------------------------------------------------------
# AI bridge (OpenAI-compatible chat completions, stdlib only)
# --------------------------------------------------------------------------

def provider_config():
    provider = setting("AI_PROVIDER").lower() or "openai"
    if provider == "openai":
        return (
            setting("OPENAI_BASE_URL") or "https://api.openai.com/v1",
            setting("OPENAI_API_KEY"),
            setting("OPENAI_MODEL") or "gpt-4o-mini",
        )
    if provider == "perplexity":
        return (
            "https://api.perplexity.ai",
            setting("PERPLEXITY_API_KEY"),
            setting("PERPLEXITY_MODEL") or "sonar",
        )
    if provider == "xai":
        return (
            "https://api.x.ai/v1",
            setting("XAI_API_KEY"),
            setting("XAI_MODEL"),
        )
    if provider == "opencode":
        return (
            setting("OPENCODE_BASE_URL")
            or "https://opencode.ai/inference/openai/v1",
            setting("OPENCODE_API_KEY"),
            setting("OPENCODE_MODEL"),
        )
    if provider == "hyper":
        return (
            "https://hyper.charm.land/v1",
            setting("HYPER_API_KEY"),
            setting("HYPER_MODEL") or "deepseek-v4.1-flash",
        )
    # custom: any OpenAI-compatible endpoint
    return (
        setting("CUSTOM_BASE_URL"),
        setting("CUSTOM_API_KEY"),
        setting("CUSTOM_MODEL"),
    )


class AIError(Exception):
    def __init__(self, code):
        self.code = code


def _open_and_read(req, socket_timeout):
    with urllib.request.urlopen(req, timeout=socket_timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat_completion(history):
    """Call the configured provider with an overall wall-clock deadline.

    history = [{role, content}, ...]. A worker thread performs the
    request; if it exceeds AI_TIMEOUT (a true deadline, not just a
    socket timeout), the call is abandoned and a timeout error raised.
    """
    base_url, api_key, model = provider_config()
    if not api_key:
        raise AIError("no_api_key")
    if not model:
        raise AIError("no_model")

    system_text = SYSTEM_PROMPT
    extra = setting("AI_SYSTEM_PROMPT")
    if extra:
        system_text = system_text + " " + extra  # single system message

    messages = [{"role": "system", "content": system_text}]
    messages.extend(history)

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": int(setting("AI_MAX_TOKENS") or "400"),
        "temperature": 0.6,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )

    deadline = float(setting("AI_TIMEOUT") or "5.0")
    socket_timeout = min(deadline, 5.0)

    result = {}

    def worker():
        try:
            result["data"] = _open_and_read(req, socket_timeout)
        except Exception as exc:  # network, HTTP, JSON errors
            result["exc"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(deadline)

    if thread.is_alive():
        raise AIError("timeout")
    if "exc" in result:
        raise AIError("provider_error")
    if "data" not in result:
        raise AIError("timeout")
    data = result["data"]
    return data["choices"][0]["message"]["content"].strip()


def trim_history(history):
    """Keep the most recent HISTORY_LIMIT messages."""
    if len(history) > HISTORY_LIMIT:
        history = history[-HISTORY_LIMIT:]
    return history


# --------------------------------------------------------------------------
# Intent handlers
# --------------------------------------------------------------------------

def get_slot_value(event, slot_name):
    try:
        slot = event["request"]["intent"]["slots"][slot_name]
        if slot.get("value"):
            return slot["value"]
    except (KeyError, TypeError):
        pass
    return None


def handle_launch(event, s):
    attrs = event.get("session", {}).get("attributes") or {}
    return build_response(s["greet"], s["reprompt"], False, attrs)


def handle_query(event, s, locale):
    attrs = dict(event.get("session", {}).get("attributes") or {})
    history = list(attrs.get("history") or [])
    intent_name = event["request"]["intent"]["name"]
    slot_value = get_slot_value(event, "query")

    if not slot_value:
        return build_response(s["empty"], s["reprompt"], False, attrs)

    # Restore the carrier phrase Alexa stripped, so the AI sees the full
    # question exactly as spoken ("why is the sky blue", not "is the sky blue").
    prefix = CARRIER_PREFIXES.get(locale, CARRIER_PREFIXES["en-US"]).get(
        intent_name, "")
    query = (prefix + slot_value).strip()

    send_progressive(event, s["thinking"])

    history.append({"role": "user", "content": query})
    try:
        answer = chat_completion(history)
    except AIError as exc:
        if exc.code == "no_api_key":
            return build_response(s["nokey"], s["reprompt"], False, attrs)
        if exc.code == "no_model":
            return build_response(s["nomodel"], s["reprompt"], False, attrs)
        if exc.code == "provider_error":
            return build_response(s["provider"], s["reprompt"], False, attrs)
        return build_response(s["slow"], s["reprompt"], False, attrs)
    except Exception:
        return build_response(s["slow"], s["reprompt"], False, attrs)

    history.append({"role": "assistant", "content": answer})
    history = trim_history(history)
    attrs["history"] = history

    return build_response(answer, s["reprompt"], False, attrs)


def handle_stop(event, s):
    attrs = event.get("session", {}).get("attributes") or {}
    return build_response(s["bye"], None, True, attrs)


def handle_help(event, s):
    attrs = event.get("session", {}).get("attributes") or {}
    return build_response(s["help"], s["reprompt"], False, attrs)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def lambda_handler(event, context):
    request = event["request"]
    request_type = request["type"]
    locale = request.get("locale", "en-US")
    s = strings_for(locale)

    if request_type == "LaunchRequest":
        return handle_launch(event, s)

    if request_type == "SessionEndedRequest":
        return {"version": "1.0", "response": {}, "sessionAttributes": {}}

    if request_type == "IntentRequest":
        intent_name = request["intent"]["name"]
        if intent_name in QUERY_INTENTS:
            return handle_query(event, s, locale)
        if intent_name in (
            "AMAZON.StopIntent",
            "AMAZON.CancelIntent",
            "AMAZON.NavigateHomeIntent",
        ):
            return handle_stop(event, s)
        if intent_name == "AMAZON.HelpIntent":
            return handle_help(event, s)
        if intent_name == "AMAZON.FallbackIntent":
            return build_response(
                s["empty"], s["reprompt"], False,
                event.get("session", {}).get("attributes") or {},
            )

    # Unknown request types (CanFulfillIntentRequest etc.)
    return {
        "version": "1.0",
        "response": {},
        "sessionAttributes": event.get("session", {}).get("attributes") or {},
    }
