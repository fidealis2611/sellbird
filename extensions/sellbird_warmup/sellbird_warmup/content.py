"""Warmup message text: varied, ordinary, short. No LLM, no links, no tracking."""
from __future__ import annotations

import random

_OPEN = {
    "fr": ["Bonjour", "Salut", "Bonsoir"], "en": ["Hi", "Hello", "Hey"],
    "es": ["Hola", "Buenas"], "it": ["Ciao", "Buongiorno"], "de": ["Hallo", "Guten Tag"],
}
_BODY = {
    "fr": ["Je reviens vers vous au sujet de notre point de la semaine. Pouvez-vous confirmer le créneau ?",
           "Merci pour votre retour. J'ai bien noté les éléments, je vous envoie la suite demain.",
           "Petit message pour savoir si le document est bien arrivé de votre côté.",
           "Je n'ai pas de nouvelle depuis jeudi, tout va bien de votre côté ?"],
    "en": ["Following up on our call this week. Could you confirm the time that works for you?",
           "Thanks for getting back to me. I noted everything and will send the rest tomorrow.",
           "Quick note to check that the document reached you.",
           "I have not heard from you since Thursday, is everything fine on your side?"],
    "es": ["Le escribo para confirmar nuestra reunión de esta semana. ¿Le va bien el horario?",
           "Gracias por su respuesta. Le envío el resto mañana."],
    "it": ["Ti scrivo per confermare l'incontro di questa settimana. Va bene l'orario?",
           "Grazie per la risposta. Ti mando il resto domani."],
    "de": ["Ich melde mich wegen unseres Termins diese Woche. Passt Ihnen die Uhrzeit?",
           "Danke für Ihre Antwort. Den Rest sende ich morgen."],
}
_SUBJ = {
    "fr": ["point de la semaine", "suite à notre échange", "document", "confirmation"],
    "en": ["weekly check-in", "following up", "the document", "confirmation"],
    "es": ["reunión de la semana", "confirmación"], "it": ["incontro della settimana", "conferma"],
    "de": ["Termin diese Woche", "Bestätigung"],
}
_REPLY = {
    "fr": ["Bien reçu, merci.", "Parfait, c'est noté.", "Merci, je regarde et je reviens vers vous."],
    "en": ["Got it, thanks.", "Perfect, noted.", "Thanks, I will look and get back to you."],
    "es": ["Recibido, gracias.", "Perfecto, anotado."], "it": ["Ricevuto, grazie.", "Perfetto, annotato."],
    "de": ["Erhalten, danke.", "Perfekt, notiert."],
}


def _lang(lang: str) -> str:
    return lang if lang in _BODY else "en"


def compose(lang: str, sender_name: str, rng: random.Random) -> tuple[str, str]:
    l = _lang(lang)
    subject = rng.choice(_SUBJ[l])
    body = f"{rng.choice(_OPEN[l])},\n\n{rng.choice(_BODY[l])}\n\n{sender_name}"
    return subject, body


def reply_text(lang: str, sender_name: str, rng: random.Random) -> str:
    l = _lang(lang)
    return f"{rng.choice(_REPLY[l])}\n\n{sender_name}"
