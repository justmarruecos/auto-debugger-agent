import os
import json
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


def build_messages(code: str, error: str) -> tuple[str, str]:
    """
    Construit le message system et user à partir des fichiers de prompt.
    On injecte le code et l'erreur dans le message user.
    """
    system_prompt = load_prompt("prompts/system_agent.txt")
    user_template = load_prompt("prompts/user_agent.txt")

    user_prompt = (
        user_template
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

def ask_groq_for_correction(system_prompt: str, user_prompt: str) -> str:
    """
    Appelle une IA via Groq pour obtenir un JSON de correction.
    Nécessite la variable d'environnement GROQ_API_KEY.
    """
    if Groq is None:
        raise ImportError("Le package 'groq' n'est pas installé. Fais 'pip install groq'.")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("Clé API Groq manquante. Définis GROQ_API_KEY dans le fichier .env.")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # tu peux changer de modèle si besoin
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    ai_text = response.choices[0].message.content
    return ai_text


# ---------- FOURNISSEUR MISTRAL ----------

def ask_mistral_for_correction(system_prompt: str, user_prompt: str) -> str:
    """
    Appelle une IA via Mistral pour obtenir un JSON de correction.
    Nécessite la variable d'environnement MISTRAL_API_KEY.
    """
    if Mistral is None:
        raise ImportError("Le package 'mistralai' n'est pas installé. Fais 'pip install mistralai'.")

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("Clé API Mistral manquante. Définis MISTRAL_API_KEY dans le fichier .env.")

    client = Mistral(api_key=api_key)

    response = client.chat.complete(
        model="mistral-small-latest",  # ou autre modèle si dispo
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


# ---------- WRAPPER GÉNÉRIQUE ----------

def ask_ai_for_correction(code: str, error: str, provider: str = "mistral") -> str:
    """
    Wrapper générique pour choisir le fournisseur d'IA.
    provider = "mistral" ou "groq".
    Retourne TOUJOURS un JSON texte nettoyé.
    """
    system_prompt, user_prompt = build_messages(code, error)

    if provider == "mistral":
        print("[ai_agent] Appel à Mistral...")
        raw_text = ask_mistral_for_correction(system_prompt, user_prompt)
    elif provider == "groq":
        print("[ai_agent] Appel à Groq...")
        raw_text = ask_groq_for_correction(system_prompt, user_prompt)
    else:
        raise ValueError(f"Fournisseur IA inconnu : {provider}")

    cleaned = clean_ai_json(raw_text)
    return cleaned
