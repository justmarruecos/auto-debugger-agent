import json
import os

from dotenv import load_dotenv

# On charge les variables d'environnement depuis .env
load_dotenv()

# Optionnel : tu peux garder Groq si tu veux
try:
    from groq import Groq
except ImportError:
    Groq = None

# Mistral
try:
    from mistralai import Mistral
except ImportError:
    Mistral = None

def clean_ai_json(text: str) -> str:
    """
    Nettoie la réponse IA : supprime les blocs markdown json ... 
    et retourne un JSON brut utilisable par json.loads().
    """

    # 1. On enlève les json ou python
    if text.startswith(""):
        # enlève tous les ... sur plusieurs lignes
        cleaned = []
        for line in text.splitlines():
            if line.strip().startswith("```"):
                continue
            cleaned.append(line)
        text = "\n".join(cleaned)

    # 2. On strip les espaces de début/fin
    text = text.strip()

    # 3. Beaucoup de modèles ajoutent des labels style "json"
    if text.lower().startswith("json"):
        text = text[4:].strip()

    return text

def build_system_message() -> str:
    """
    Message SYSTEM défini à l'étape 4.
    """
    return (
        "Tu es un agent spécialisé dans la correction automatique de code Python. "
        "Ton rôle n’est pas de réécrire entièrement le code, mais d’identifier précisément "
        "la cause d’une erreur d’exécution et de proposer la correction minimale nécessaire.\n\n"
        "Règles importantes :\n"
        "1. Tu renvoies STRICTEMENT un JSON, sans aucun texte avant ou après.\n"
        "2. Format JSON obligatoire :\n"
        "{\n"
        '  "file": "nom_du_fichier.py",\n'
        "  \"line\": numéro_de_ligne,\n"
        '  "action": "replace" | "insert" | "delete" | "none",\n'
        '  "new_code": "nouvelle_ligne_de_code (ou chaîne vide si delete)"\n'
        "}\n"
        "3. Tu proposes la correction MINIMALE nécessaire.\n"
        "4. Si aucune correction n’est nécessaire, tu renvoies exactement :\n"
        "{\n"
        "  \"file\": null,\n"
        "  \"line\": null,\n"
        "  \"action\": \"none\",\n"
        "  \"new_code\": null\n"
        "}\n"
    )


def build_user_message(code: str, error: str) -> str:
    """
    Message USER défini à l'étape 4.
    """
    return f"""
Voici le code source à analyser :

{code}

Voici l’erreur obtenue lors de l’exécution :

{error}

Ta tâche :
Analyse ce code et ce message d’erreur.
Identifie la cause exacte du problème.
Propose uniquement la correction minimale nécessaire, en respectant STRICTEMENT le format JSON demandé.
"""


# ---------- VERSION GROQ (si tu veux garder) ----------

def ask_groq_for_correction(code: str, error: str) -> str:
    """
    Appelle une IA via Groq pour obtenir un JSON de correction.
    Nécessite la variable d'environnement GROQ_API_KEY.
    """
    if Groq is None:
        raise ImportError("Le package 'groq' n'est pas installé. Fais 'pip install groq' ou utilise Mistral.")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("Clé API Groq manquante. Définis GROQ_API_KEY dans le fichier .env ou les variables d’environnement.")

    client = Groq(api_key=api_key)

    system_message = build_system_message()
    user_message = build_user_message(code, error)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )

    ai_text = response.choices[0].message["content"]
    return ai_text


# ---------- VERSION MISTRAL ----------

def ask_mistral_for_correction(code: str, error: str) -> str:
    """
    Appelle Mistral pour obtenir un JSON correctif.
    """
    if Mistral is None:
        raise ImportError("Le package 'mistralai' n'est pas installé.")

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("Clé API Mistral manquante. Définis MISTRAL_API_KEY dans ton fichier .env.")

    client = Mistral(api_key=api_key)

    system_message = build_system_message()
    user_message = build_user_message(code, error)

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ],
        temperature=0,
    )

    # Nouvelle extraction correcte
    ai_message = response.choices[0].message

    # message.content est une LISTE de blocs (text chunks)
    if isinstance(ai_message.content, list):
        ai_text = "".join(
            block["text"] for block in ai_message.content
            if isinstance(block, dict) and "text" in block
        )
    else:
        ai_text = ai_message.content

    return clean_ai_json(ai_text)


# ---------- Fonction principale utilisée par ton projet ----------

def ask_ai_for_correction(code: str, error: str, provider: str = "mistral") -> str:
    """
    Wrapper générique pour choisir le fournisseur d'IA.
    provider = "mistral" ou "groq"
    """
    if provider == "mistral":
        print("[ai_agent] Appel à Mistral...")
        return ask_mistral_for_correction(code, error)
    elif provider == "groq":
        print("[ai_agent] Appel à Groq...")
        return ask_groq_for_correction(code, error)
    else:
        raise ValueError(f"Fournisseur IA inconnu : {provider}")