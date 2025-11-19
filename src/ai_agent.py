import os
from pathlib import Path

from dotenv import load_dotenv

# Chargement des variables d'environnement (.env)
load_dotenv()

# Import Groq (optionnel)
try:
    from groq import Groq
except ImportError:
    Groq = None

# Import Mistral (optionnel)
try:
    from mistralai import Mistral
except ImportError:
    Mistral = None


# ---------- OUTILS GÉNÉRAUX ----------

BASE_DIR = Path(__file__).resolve().parent.parent  # racine du projet (dossier auto-debugger-agent)


def load_prompt(relative_path: str) -> str:
    """
    Charge un fichier de prompt texte à partir du dossier racine.
    Exemple : 'prompts/system_agent.txt'
    """
    full_path = BASE_DIR / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Fichier de prompt introuvable : {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def build_correction_messages(code: str, error: str) -> tuple[str, str]:
    """
    Construit le message system et user pour la CORRECTION
    à partir des fichiers de prompt.
    """
    system_prompt = load_prompt("prompts/system_agent.txt")
    user_template = load_prompt("prompts/user_agent.txt")

    user_prompt = (
        user_template
        .replace("<CODE>", code)
        .replace("<ERREUR>", error)
    )

    return system_prompt, user_prompt


def build_explanation_messages(code: str, error: str) -> tuple[str, str]:
    """
    Construit les messages system/user pour l'EXPLICATION de l'erreur.
    On réutilise le même system_prompt et un user_prompt différent.
    """
    system_prompt = load_prompt("prompts/system_agent.txt")
    explain_template = load_prompt("prompts/user_explain.txt")

    user_prompt = (
        explain_template
        .replace("<CODE>", code)
        .replace("<ERREUR>", error)
    )

    return system_prompt, user_prompt


def clean_ai_json(text: str) -> str:
    """
    Nettoie la réponse IA : supprime les blocs markdown ```json ... ```
    et retourne un JSON brut utilisable par json.loads().
    """
    if not isinstance(text, str):
        text = str(text)

    # 1) on enlève les lignes ```xxx
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            # on ignore la ligne qui contient ``` ou ```json
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines).strip()

    # 2) Si ça commence par "json" ou similaire, on enlève
    lowered = text.lower()
    if lowered.startswith("json"):
        text = text[4:].strip()

    return text


# ---------- FOURNISSEUR GROQ ----------

def _get_groq_client() -> "Groq":
    if Groq is None:
        raise ImportError("Le package 'groq' n'est pas installé. Fais 'pip install groq'.")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("Clé API Groq manquante. Définis GROQ_API_KEY dans le fichier .env.")
    return Groq(api_key=api_key)


def groq_chat(system_prompt: str, user_prompt: str, model: str = "llama-3.1-8b-instant") -> str:
    """
    Appelle le chat Groq générique et renvoie le texte de la réponse.
    """
    client = _get_groq_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    return response.choices[0].message.content


# ---------- FOURNISSEUR MISTRAL ----------

def _get_mistral_client() -> "Mistral":
    if Mistral is None:
        raise ImportError("Le package 'mistralai' n'est pas installé. Fais 'pip install mistralai'.")
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("Clé API Mistral manquante. Définis MISTRAL_API_KEY dans le fichier .env.")
    return Mistral(api_key=api_key)


def mistral_chat(system_prompt: str, user_prompt: str, model: str = "mistral-small-latest") -> str:
    """
    Appelle le chat Mistral générique et renvoie le texte de la réponse.
    """
    client = _get_mistral_client()

    response = client.chat.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    message = response.choices[0].message

    # message.content peut être une string ou une liste de blocs
    if isinstance(message.content, list):
        parts = []
        for block in message.content:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        ai_text = "".join(parts)
    else:
        ai_text = message.content

    return ai_text


# ---------- WRAPPERS HAUT NIVEAU ----------

def ask_ai_for_correction(code: str, error: str, provider: str = "mistral") -> str:
    """
    Demande à l'IA une proposition de correction sous forme de JSON.
    Retourne TOUJOURS un texte JSON nettoyé.
    """
    system_prompt, user_prompt = build_correction_messages(code, error)

    if provider == "mistral":
        print("[ai_agent] Appel à Mistral (CORRECTION)...")
        raw_text = mistral_chat(system_prompt, user_prompt)
    elif provider == "groq":
        print("[ai_agent] Appel à Groq (CORRECTION)...")
        raw_text = groq_chat(system_prompt, user_prompt)
    else:
        raise ValueError(f"Fournisseur IA inconnu : {provider}")

    cleaned = clean_ai_json(raw_text)
    return cleaned


def ask_ai_for_explanation(code: str, error: str, provider: str = "mistral") -> str:
    """
    Demande à l'IA une EXPLICATION en langage naturel de l'erreur,
    adaptée à un débutant.
    Retourne du TEXTE LIBRE (PAS du JSON).
    """
    system_prompt, user_prompt = build_explanation_messages(code, error)

    if provider == "mistral":
        print("[ai_agent] Appel à Mistral (EXPLICATION)...")
        text = mistral_chat(system_prompt, user_prompt)
    elif provider == "groq":
        print("[ai_agent] Appel à Groq (EXPLICATION)...")
        text = groq_chat(system_prompt, user_prompt)
    else:
        raise ValueError(f"Fournisseur IA inconnu : {provider}")

    # Ici on NE nettoie PAS en JSON, on veut une explication libre.
    return text
