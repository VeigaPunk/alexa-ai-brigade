# -*- coding: utf-8 -*-
"""End-to-end tests for the Alexa AI Brigade skill logic.

Runs the real lambda handler against a local fake LLM + directives server,
using synthetic Alexa request envelopes. Run:  python3 tests/test_skill.py
"""

import json
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lambda"))
sys.path.insert(0, HERE)

import lambda_function  # noqa: E402
from fake_ai_server import FakeAIServer  # noqa: E402

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  PASS  %s" % name)
    else:
        FAIL += 1
        print("  FAIL  %s  %s" % (name, detail))


def envelope(request, session_attributes=None, locale="pt-BR"):
    return {
        "version": "1.0",
        "session": {
            "new": session_attributes is None,
            "sessionId": "amzn1.echo-api.session." + str(uuid.uuid4()),
            "application": {"applicationId": "amzn1.ask.skill.TEST"},
            "attributes": session_attributes or {},
        },
        "context": {
            "System": {
                "application": {"applicationId": "amzn1.ask.skill.TEST"},
                "user": {"userId": "amzn1.ask.account.TEST"},
                "device": {"deviceId": "test", "supportedInterfaces": {}},
                "apiEndpoint": SERVER.url,
                "apiAccessToken": "test-token",
            }
        },
        "request": request,
    }


def launch(locale="pt-BR"):
    return envelope({"type": "LaunchRequest", "requestId": "req-launch",
                     "locale": locale})


def query(text, session_attributes=None, locale="pt-BR",
           intent="AskQueryIntent"):
    return envelope({
        "type": "IntentRequest",
        "requestId": "req-" + str(uuid.uuid4())[:8],
        "locale": locale,
        "intent": {
            "name": intent,
            "confirmationStatus": "NONE",
            "slots": {
                "query": {"name": "query", "value": text,
                          "confirmationStatus": "NONE"}
            },
        },
    }, session_attributes)


def stop(locale="pt-BR"):
    return envelope({"type": "IntentRequest", "requestId": "req-stop",
                    "locale": locale,
                    "intent": {"name": "AMAZON.StopIntent",
                               "slots": {}}})


def fallback(locale="pt-BR"):
    return envelope({"type": "IntentRequest", "requestId": "req-fb",
                    "locale": locale,
                    "intent": {"name": "AMAZON.FallbackIntent",
                               "slots": {}}})


def speech_text(response):
    return response["response"]["outputSpeech"]["ssml"]


def run_tests():
    global SERVER
    SERVER = FakeAIServer()
    os.environ["AI_PROVIDER"] = "custom"
    os.environ["CUSTOM_BASE_URL"] = SERVER.url
    os.environ["CUSTOM_API_KEY"] = "test-key"
    os.environ["CUSTOM_MODEL"] = "fake-model"
    os.environ["AI_TIMEOUT"] = "2.0"
    lambda_function.os.environ = os.environ

    print("== 1. LaunchRequest (pt-BR) ==")
    r = lambda_function.lambda_handler(launch(), None)
    check("session stays open", r["response"]["shouldEndSession"] is False)
    check("greeting spoken", "Pronto" in speech_text(r), speech_text(r))
    check("has reprompt", "reprompt" in r["response"])

    print("== 2. Query -> LLM answer, progressive response sent ==")
    SERVER.server.requests.clear()
    r = lambda_function.lambda_handler(query("qual a previsao do tempo"), None)
    check("answer contains fake LLM text", "Resposta de teste" in speech_text(r),
          speech_text(r))
    check("history stored", len(r["sessionAttributes"]["history"]) == 2,
          str(r["sessionAttributes"]))
    check("progressive directive sent",
          len(SERVER.requests_for("/v1/directives")) == 1)
    check("directive used token",
          "Bearer test-token" in SERVER.requests_for("/v1/directives")[0]
          ["headers"].get("Authorization", ""))
    check("session still open", r["response"]["shouldEndSession"] is False)

    print("== 2b. Carrier phrase semantics: prefix restored ==")
    SERVER.server.requests.clear()
    r = lambda_function.lambda_handler(
        query("a fotossintese", intent="WhatIsIntent"), None)
    llm_calls = SERVER.requests_for("/chat/completions")
    sent = llm_calls[-1]["body"]["messages"][-1]["content"]
    check("carrier restored for AI", sent == "o que é a fotossintese", sent)
    r = lambda_function.lambda_handler(
        query("is the sky blue", locale="en-US", intent="WhyIntent"), None)
    llm_calls = SERVER.requests_for("/chat/completions")
    sent = llm_calls[-1]["body"]["messages"][-1]["content"]
    check("carrier restored en-US", sent == "why is the sky blue", sent)

    print("== 3. Second turn reuses conversation history ==")
    r_pre = lambda_function.lambda_handler(query("qual a previsao do tempo"), None)
    r2 = lambda_function.lambda_handler(
        query("e amanha?", r_pre["sessionAttributes"]), None)
    llm_calls = SERVER.requests_for("/chat/completions")
    last_messages = llm_calls[-1]["body"]["messages"]
    check("history passed to LLM",
          any(m["content"] == "qual a previsao do tempo" for m in last_messages),
          json.dumps(last_messages, ensure_ascii=False))
    check("second user turn appended",
          any(m["content"] == "e amanha?" for m in last_messages))
    check("system prompt present",
          last_messages[0]["role"] == "system"
          and "voice assistant" in last_messages[0]["content"])
    check("history grows", len(r2["sessionAttributes"]["history"]) == 4)

    print("== 4. SSML escaping ==")
    SERVER.server.next_answer = 'Oi <b>negrito</b> & "aspas"'
    r = lambda_function.lambda_handler(query("teste"), None)
    s = speech_text(r)
    check("XML escaped", "&" + "lt;b" + "&" + "gt;" in s
          and "&" + "amp;" in s and "&" + "quot;" in s
          and "<b>" not in s, s)
    check("wrapped in speak tags", s.startswith("<speak>") and s.endswith("</speak>"))

    print("== 5. LLM too slow -> graceful fallback within budget ==")
    SERVER.server.sleep_seconds = 5  # exceeds AI_TIMEOUT of 2 s
    t0 = time.time()
    r = lambda_function.lambda_handler(query("pergunta lenta"), None)
    elapsed = time.time() - t0
    check("fallback message", "demorou" in speech_text(r), speech_text(r))
    check("responded within Alexa 8s budget", elapsed < 7.5, "%.2fs" % elapsed)
    check("session stays open on slow answer",
          r["response"]["shouldEndSession"] is False)
    SERVER.server.sleep_seconds = 0

    print("== 5b. Production-like budget: slow directives + slow AI ==")
    os.environ["AI_TIMEOUT"] = "5.0"
    SERVER.server.directives_sleep = 1.0   # directives endpoint is slow too
    SERVER.server.sleep_seconds = 8       # AI way over budget
    t0 = time.time()
    r = lambda_function.lambda_handler(query("pergunta muito lenta"), None)
    elapsed = time.time() - t0
    check("graceful fallback", "demorou" in speech_text(r), speech_text(r))
    check("total under 7.5s with 1s directive delay", elapsed < 7.5,
          "%.2fs" % elapsed)
    SERVER.server.directives_sleep = 0.0
    SERVER.server.sleep_seconds = 0
    os.environ["AI_TIMEOUT"] = "2.0"

    print("== 5c. Slow-trickling body still respects the deadline ==")
    os.environ["AI_TIMEOUT"] = "2.0"
    SERVER.server.trickle_seconds = 6  # body dribbles over ~6 s
    t0 = time.time()
    r = lambda_function.lambda_handler(query("corpo lento"), None)
    elapsed = time.time() - t0
    check("trickle fallback message", "demorou" in speech_text(r))
    check("trickle total under deadline + margin", elapsed < 3.5,
          "%.2fs" % elapsed)
    SERVER.server.trickle_seconds = 0

    print("== 6. Missing API key -> config message ==")
    os.environ["CUSTOM_API_KEY"] = ""
    r = lambda_function.lambda_handler(query("sem chave"), None)
    check("config error spoken", "chave" in speech_text(r), speech_text(r))
    os.environ["CUSTOM_API_KEY"] = "test-key"

    print("== 6b. Missing model -> config message ==")
    os.environ["CUSTOM_MODEL"] = ""
    r = lambda_function.lambda_handler(query("sem modelo"), None)
    check("model error spoken", "modelo" in speech_text(r), speech_text(r))
    os.environ["CUSTOM_MODEL"] = "fake-model"

    print("== 6c. New provider presets ==")
    for prov, key, base, want_model in [
        ("opencode", "OPENCODE_API_KEY", "https://opencode.ai/zen/v1", None),
        ("hyper", "HYPER_API_KEY", "https://hyper.charm.land/v1",
         "deepseek-v4.1-flash"),
    ]:
        os.environ["AI_PROVIDER"] = prov
        os.environ[key] = "k-" + prov
        base_url, api_key, model = lambda_function.provider_config()
        check("%s preset" % prov,
              base_url == base and api_key == "k-" + prov
              and (want_model is None or model == want_model),
              str((base_url, api_key, model)))
        del os.environ[key]
    os.environ["AI_PROVIDER"] = "custom"

    print("== 7. Stop / Fallback / Help / en-US locale ==")
    r = lambda_function.lambda_handler(stop(), None)
    check("stop ends session", r["response"]["shouldEndSession"] is True)
    r = lambda_function.lambda_handler(fallback(), None)
    check("fallback suggests carrier phrases", "o que é" in speech_text(r))
    r = lambda_function.lambda_handler(envelope({
        "type": "IntentRequest", "requestId": "req-help", "locale": "pt-BR",
        "intent": {"name": "AMAZON.HelpIntent", "slots": {}}}, None), None)
    check("help spoken", "conversa" in speech_text(r))
    SERVER.server.next_answer = "Resposta de teste do assistente."
    r = lambda_function.lambda_handler(query("hello there", locale="en-US"), None)
    check("en-US strings", "took longer" not in speech_text(r)
          and "Resposta de teste" in speech_text(r))
    r = lambda_function.lambda_handler(launch(locale="en-US"), None)
    check("en-US greeting", "Ready" in speech_text(r))

    print("== 8. SessionEndedRequest ==")
    r = lambda_function.lambda_handler(envelope(
        {"type": "SessionEndedRequest", "requestId": "req-end",
         "reason": "USER_INITIATED", "locale": "pt-BR"}), None)
    check("session ended cleanly", r["response"] == {})

    SERVER.stop()
    print("\n%d passed, %d failed" % (PASS, FAIL))
    return FAIL


if __name__ == "__main__":
    sys.exit(1 if run_tests() else 0)
