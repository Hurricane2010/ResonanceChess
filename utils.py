import requests, random

LICHESS_API_URL = "https://lichess.org/api/cloud-eval"

_eval_cache = {}


# -------------------------------
# Lichess Cloud Evaluator (cached)
# -------------------------------
def lichess_evaluate(fen):
    """Queries Lichess Cloud Evaluation API for a FEN position, with caching."""
    if fen in _eval_cache:
        return _eval_cache[fen]
    try:
        r = requests.get(LICHESS_API_URL, params={"fen": fen}, timeout=4)
        if r.status_code == 200:
            data = r.json()
            if "pvs" in data and data["pvs"]:
                cp = data["pvs"][0].get("cp", 0)
                _eval_cache[fen] = cp or 0
                return cp or 0
    except Exception:
        pass
    _eval_cache[fen] = 0
    return 0


# -------------------------------
# Ollama Text Generation (modern API)
# -------------------------------
def ollama_say(system_prompt, user_prompt, model="llama3"):
    """
    Generates short, emotional dialogue lines via the local Ollama API.
    Gracefully falls back to canned responses if Ollama isn't reachable.
    """
    try:
        # Call Ollama's REST API
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": f"{system_prompt.strip()}\n\n{user_prompt.strip()}",
                "stream": False
            },
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            resp = data.get("response", "").strip()
            if resp:
                return resp
    except Exception:
        pass

    # Fallback if Ollama not available or returns invalid response
    return random.choice([
        "They nod silently, unsure but willing.",
        "A faint spark glimmers in their eyes.",
        "Your words stir something deep within.",
        "No response — only quiet determination.",
        "The piece stands still, reflecting on your command."
    ])


# -------------------------------
# Stat-Aware System Prompt Helper
# -------------------------------
def generate_piece_prompt(piece_name, square, stats, player_text):
    """
    Builds a context-aware system prompt describing the piece's mental state
    so Ollama can respond with fitting tone and emotion.
    """
    # Describe emotions semantically
    morale_desc = _describe_stat(stats.get("morale", 50), "morale",
                                 ["crushed", "wavering", "steady", "burning"])
    trust_desc = _describe_stat(stats.get("trust", 50), "trust",
                                ["doubtful", "cautious", "confident", "devoted"])
    loyalty_desc = _describe_stat(stats.get("loyalty", 50), "loyalty",
                                  ["disloyal", "self-interested", "faithful", "unwavering"])
    motivation_desc = _describe_stat(stats.get("motivation", 50), "motivation",
                                     ["drained", "weary", "focused", "driven"])
    empathy_desc = _describe_stat(stats.get("empathy", 50), "empathy",
                                  ["cold", "reserved", "understanding", "deeply compassionate"])

    personality = (
        f"You are the {piece_name} stationed on {square.upper()}, a sentient chess piece "
        f"in a battlefield where leadership and emotion matter. "
        f"Your current state: morale {morale_desc}, trust {trust_desc}, "
        f"loyalty {loyalty_desc}, motivation {motivation_desc}, empathy {empathy_desc}. "
        f"Speak briefly and with emotion (under 20 words). Use absolutly no emojis or repetition."
    )

    user_line = f"Commander says: \"{player_text}\""
    return personality, user_line


def _describe_stat(value, label, adjectives):
    """
    Converts a numeric value into a contextual adjective.
    adjectives: [low, mid-low, mid-high, high]
    """
    if value < 35:
        return adjectives[0]
    elif value < 55:
        return adjectives[1]
    elif value < 80:
        return adjectives[2]
    else:
        return adjectives[3]
