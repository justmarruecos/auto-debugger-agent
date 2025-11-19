import json
import re
from typing import Any, Dict, Optional


class JsonValidationError(Exception):
    """
    Erreur spécifique pour les problèmes de JSON renvoyé par l'IA.
    Utile si on veut distinguer clairement les erreurs de parsing/validation.
    """
    pass


def _clean_json_text(text: str) -> str:
    """
    Nettoie la réponse IA :
    - convertit en str si besoin
    - supprime les blocs ```xxx
    - supprime un éventuel préfixe 'json'
    """
    if not isinstance(text, str):
        text = str(text)

    # Supprimer les lignes ```xxx (```json, ```python, ``` etc.)
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            # on ignore complètement ces lignes
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()

    # Si ça commence par "json" ou "JSON" -> retirer ce préfixe
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    return cleaned


def _extract_json_object(text: str) -> Dict[str, Any]:
    """
    Essaie de parser le texte en JSON.
    Si le parsing direct échoue, tente d'extraire la première structure {...}
    du texte (au cas où l'IA aurait ajouté du blabla autour).
    """
    cleaned = _clean_json_text(text)

    if not cleaned:
        raise JsonValidationError("La réponse IA est vide après nettoyage.")

    # 1) tentative directe
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass  # on tente autre chose plus bas

    # 2) tentative d'extraction de l'objet JSON principal
    #    on cherche le premier '{' et le dernier '}' dans le texte nettoyé
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise JsonValidationError(
            "Impossible de trouver un objet JSON valide dans la réponse IA.\n"
            f"Texte reçu après nettoyage :\n{cleaned}"
        )

    candidate = cleaned[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise JsonValidationError(
            f"Erreur lors du parsing JSON : {e}\n"
            f"Candidat JSON :\n{candidate}"
        )


def validate_json_correction(
    raw_text: str,
    max_line: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Valide un JSON venant de l'IA :
    - Nettoyage / extraction du JSON
    - Tentative de parsing
    - Validation du schéma attendu
    - Quelques garde-fous de cohérence

    :param raw_text: texte brut renvoyé par l'IA
    :param max_line: (optionnel) nombre de lignes max du fichier cible, pour
                     vérifier que 'line' ne dépasse pas cette valeur.
    :return: dictionnaire Python représentant la correction validée
    """

    if not raw_text or not raw_text.strip():
        raise JsonValidationError("La réponse de l’IA est vide ou nulle.")

    parsed = _extract_json_object(raw_text)

    # --- Vérification du schéma de base ---
    required_keys = {"file", "line", "action", "new_code"}
    if not all(k in parsed for k in required_keys):
        raise JsonValidationError(
            "JSON invalide : il manque une ou plusieurs clés obligatoires.\n"
            f"Reçu : {parsed}"
        )

    action = parsed["action"]

    if action not in ["replace", "insert", "delete", "none"]:
        raise JsonValidationError(
            f"Valeur 'action' invalide : {action}. "
            "Actions valides : replace | insert | delete | none."
        )

    # --- Cas où aucune correction n'est nécessaire ---
    if action == "none":
        # On accepte (file, line, new_code) null ou absents
        file_val = parsed.get("file", None)
        line_val = parsed.get("line", None)
        new_code_val = parsed.get("new_code", None)
        if not (file_val is None and line_val is None and new_code_val is None):
            raise JsonValidationError(
                "Format incorrect pour action='none'. "
                "Attendu : file=null, line=null, new_code=null."
            )
        return parsed  # OK, rien à corriger

    # --- Vérifications communes pour replace / insert / delete ---
    file_val = parsed["file"]
    line_val = parsed["line"]
    new_code_val = parsed["new_code"]

    if file_val is None or not isinstance(file_val, str) or file_val.strip() == "":
        raise JsonValidationError(f"Le champ 'file' doit être un texte non vide : {file_val!r}")

    if not isinstance(line_val, int) or line_val <= 0:
        raise JsonValidationError(f"Le champ 'line' doit être un entier positif : {line_val!r}")

    if max_line is not None and line_val > max_line:
        raise JsonValidationError(
            f"Numéro de ligne trop grand : {line_val} (max autorisé : {max_line})."
        )

    if action in ["replace", "insert"]:
        if not isinstance(new_code_val, str):
            raise JsonValidationError(
                f"Le champ 'new_code' doit être une chaîne pour replace/insert. Reçu : {new_code_val!r}"
            )
        # On peut accepter une chaîne vide, mais en pratique ce serait très étrange.
        # On ajoute donc un warning sous forme d'exception si vraiment vide (et pas pour delete).
        if new_code_val.strip() == "":
            raise JsonValidationError(
                "new_code est vide pour une action replace/insert, ce qui est suspect."
            )

    if action == "delete":
        # pour delete, on tolère new_code vide ou null
        if new_code_val not in ("", None):
            raise JsonValidationError(
                f"Pour delete, new_code doit être vide ('') ou null. Reçu : {new_code_val!r}"
            )

    # (Optionnel) Quelques garde-fous très simples sur new_code,
    # pour éviter des choses manifestement dangereuses.
    # Ici, on évite juste certains mots-clés sensibles.
    if action in ["replace", "insert"]:
        lowered = new_code_val.lower()
        dangerous_tokens = ["os.system", "subprocess", "shutil.rmtree", "open(", "exec(", "eval("]
        if any(tok in lowered for tok in dangerous_tokens):
            raise JsonValidationError(
                "new_code contient des opérations potentiellement dangereuses "
                "(exec, eval, subprocess, etc.)."
            )

    return parsed
