# -*- coding: utf-8 -*-
"""Regenerates the interaction models (skill-package/models/*.json).

Sample utterances use one intent per carrier phrase so that the backend
can restore the carrier Alexa strips from the slot value. Verifies the
carrier prefixes in lambda_function.py stay consistent with the samples.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)  # the alexa-ai-brigade directory
ROOT = PKG
sys.path.insert(0, os.path.join(PKG, "lambda"))

import lambda_function  # noqa: E402

SAMPLES = {
    "pt-BR": {
        "AskQueryIntent": "pergunte {query}",
        "WhatIsIntent": "o que é {query}",
        "WhatAreIntent": "o que são {query}",
        "WhoIsIntent": "quem é {query}",
        "WhoWasIntent": "quem foi {query}",
        "WhenIntent": "quando {query}",
        "WhereIntent": "onde {query}",
        "WhyIntent": "por que {query}",
        "HowIntent": "como {query}",
        "WhichIntent": "qual {query}",
        "WhichPluralIntent": "quais {query}",
        "HowMuchIntent": "quanto {query}",
        "HowMuchFIntent": "quanta {query}",
        "ExplainIntent": "me explique {query}",
        "TellMeIntent": "me diga {query}",
        "TalkAboutIntent": "fale sobre {query}",
        "WantToKnowIntent": "quero saber {query}",
        "SearchIntent": "pesquise {query}",
        "AboutIntent": "sobre {query}",
        "IsItTrueIntent": "é verdade que {query}",
    },
    "en-US": {
        "AskQueryIntent": "ask {query}",
        "WhatIsIntent": "what is {query}",
        "WhatAreIntent": "what are {query}",
        "WhoIsIntent": "who is {query}",
        "WhoWasIntent": "who was {query}",
        "WhenIntent": "when {query}",
        "WhereIntent": "where {query}",
        "WhyIntent": "why {query}",
        "HowIntent": "how {query}",
        "WhichIntent": "which {query}",
        "TellMeAboutIntent": "tell me about {query}",
        "TellMeIntent": "tell me {query}",
        "SearchForIntent": "search for {query}",
        "FindOutIntent": "find out {query}",
        "WantToKnowIntent": "i want to know {query}",
        "CanYouIntent": "can you {query}",
        "DoYouKnowIntent": "do you know {query}",
        "IsItTrueIntent": "is it true that {query}",
    },
}

INVOCATION = {"pt-BR": "meu assistente", "en-US": "my assistant"}


def verify_consistency():
    problems = []
    for locale, samples in SAMPLES.items():
        prefixes = lambda_function.CARRIER_PREFIXES[locale]
        for intent, sample in samples.items():
            if intent not in prefixes:
                problems.append("%s: %s missing in lambda prefixes" % (locale, intent))
                continue
            prefix = prefixes[intent]
            expected = (prefix + "{query}").strip() if prefix else None
            # non-neutral carriers must match their prefix exactly
            if prefix and sample != expected:
                problems.append(
                    "%s: %s sample %r != prefix-based %r"
                    % (locale, intent, sample, expected)
                )
        for intent in prefixes:
            if intent not in samples:
                problems.append("%s: %s missing in model samples" % (locale, intent))
    if problems:
        raise SystemExit("inconsistencies:\n" + "\n".join(problems))


def build(locale):
    samples = SAMPLES[locale]
    intents = [
        {
            "name": name,
            "slots": [{"name": "query", "type": "AMAZON.SearchQuery"}],
            "samples": [sample],
        }
        for name, sample in samples.items()
    ]
    intents.extend([
        {"name": "AMAZON.FallbackIntent", "samples": []},
        {"name": "AMAZON.HelpIntent", "samples": []},
        {"name": "AMAZON.StopIntent", "samples": []},
        {"name": "AMAZON.CancelIntent", "samples": []},
        {"name": "AMAZON.NavigateHomeIntent", "samples": []},
    ])
    return {"interactionModel": {"languageModel": {
        "invocationName": INVOCATION[locale],
        "intents": intents,
        "types": []}}}


def main():
    verify_consistency()
    out_dir = os.path.join(PKG, "skill-package", "interactionModels", "custom")
    for locale in SAMPLES:
        path = os.path.join(out_dir, "%s.json" % locale)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(build(locale), f, ensure_ascii=False, indent=2)
        print("wrote", path)


if __name__ == "__main__":
    main()
