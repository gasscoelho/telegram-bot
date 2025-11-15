import random
from enum import Enum


class Messages(Enum):
    """UI messages for Duolingo bot."""

    DUOLINGO_WELCOME = "🦉 Duolingo Bot\n\nWhat would you like to do?"
    NOTIFYING_LOADING = "⏳ Notifying your friends..."
    NOTIFICATION_SUCCESS = "🔔 Notification sent successfully!\n\nYour friends have been notified. Keep up the great work! 🎉"
    NOTIFICATION_FAILED = "❌ Failed to notify friends. Please try again later."


def get_random_reminder_message() -> str:
    """Get a random Portuguese reminder message to send to friends."""
    messages = [
        "Sobrevivi ao Duolingo de hoje! E você, já fez a sua lição ou vai deixar a coruja nervosa?",
        "A lição de hoje foi difícil, mas a ofensiva tá viva! 🧠🔥 Já garantiu a sua também?",
        "Duolingo feito com sucesso ✅ A coruja sorriu. E aí, vai deixar ela decepcionada hoje?",
        "Quase perdi a ofensiva, mas dei o gás no final! 🏃‍♂️🔥 Já fez a sua parte ou vai arriscar?",
        "🦉 Missão do dia cumprida! Agora é sua vez... Não me decepciona 😏",
        "Mais um dia de aprendizado, mais um dia salvo da fúria da coruja. 🕊️ E você, já estudou hoje?",
        "Se eu consegui fazer Duolingo hoje, você também consegue! 💪 Bora manter essa ofensiva viva!",
        "Já fiz minha parte no Duolingo. Agora é com vocês! 👀 Não vão quebrar a sequência hein!",
        "🧩 Duolingo do dia concluído! E você, já alimentou sua corujinha hoje?",
        "A lição de hoje quase me quebrou… mas a ofensiva tá salva 😮‍💨 Já garantiu a sua?",
    ]
    return random.choice(messages)
