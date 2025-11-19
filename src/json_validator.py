import json
from typing import Any, Dict


def clean_json_text(text: str) -> str:
    """
    Nettoie la réponse IA :
    - supprime le markdown ```json ou ``` 
    - retire les balises parasites
    - supprime le texte avant/après le JSON
    """
    if not isinstance(text, str):
        text = str(text)

    # Supprimer les lignes ```xxx
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()

    # Si commence par "json" ou similaire -> retirer
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    return cleaned


def validate_json_correction(raw_text: str) -> Dict[str, Any]:
    """
    Valide un JSON venant de l'IA :
    - Nettoyage
    - Tentative de parsing
    - Validation du schéma attendu
    """

    if not raw_text or raw_text.strip() == "":
        raise ValueError("La réponse de l’IA est vide ou nulle (raw_text est vide).")

    cleaned = clean_json_text(raw_text)

    # Si encore vide après nettoyage
    if cleaned.strip() == "":
        raise ValueError("La réponse IA ne contient aucun JSON valide après nettoyage.")

    # Tentative de parsing JSON
    try:
        parsed = json.loads(cleaned)
    except Exception as e:
        raise ValueError(
            f"Erreur lors du parsing JSON : {e}\n"
            f"Texte reçu et nettoyé :\n{cleaned}"
        )

    # Vérification du schéma
    required_keys = {"file", "line", "action", "new_code"}
    if not all(k in parsed for k in required_keys):
        raise ValueError(
            "JSON invalide : il manque une ou plusieurs clés obligatoires.\n"
            f"Reçu : {parsed}"
        )

    # Vérification des types de base
    if parsed["action"] not in ["replace", "insert", "delete", "none"]:
        raise ValueError(
            f"Valeur 'action' invalide : {parsed['action']}. "
            "Actions valides : replace | insert | delete | none."
        )

    # Cas où aucune correction n'est nécessaire
    if parsed["action"] == "none":
        if not (parsed["file"] is None and parsed["line"] is None and parsed["new_code"] is None):
            raise ValueError(
                "Format incorrect pour action='none'. "
                "Attendu : file=null, line=null, new_code=null."
            )
        return parsed  # OK

    # Vérifications pour replace | insert | delete
    if parsed["file"] is None or not isinstance(parsed["file"], str):
        raise ValueError(f"Le champ 'file' doit être un texte valide : {parsed['file']}")

    if not isinstance(parsed["line"], int) or parsed["line"] <= 0:
        raise ValueError(f"Le champ 'line' doit être un entier positif : {parsed['line']}")

    if parsed["action"] in ["replace", "insert"] and not isinstance(parsed["new_code"], str):
        raise ValueError(
            f"Le champ 'new_code' doit être une chaîne pour replace/insert. Reçu : {parsed['new_code']}"
        )

    if parsed["action"] == "delete" and parsed["new_code"] not in ["", None]:
        raise ValueError(
            f"Pour delete, new_code doit être vide ('') ou null. Reçu : {parsed['new_code']}"
        )

    return parsed
