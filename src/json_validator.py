import json
from typing import Any, Dict


class JsonValidationError(Exception):
    """Erreur levée lorsque le JSON de correction est invalide."""
    pass


def parse_and_validate_correction(json_text: str, max_line: int) -> Dict[str, Any]:
    """
    Parse un texte JSON et valide sa structure.
    :param json_text: Texte renvoyé par l'IA.
    :param max_line: Nombre total de lignes du fichier à corriger.
    :return: Dictionnaire Python représentant la correction.
    :raises JsonValidationError: si quelque chose ne va pas.
    """
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise JsonValidationError(f"JSON invalide : {e}")

    # Vérification des clés obligatoires
    for key in ("file", "line", "action", "new_code"):
        if key not in data:
            raise JsonValidationError(f"Clé manquante dans le JSON : {key}")

    file = data["file"]
    line = data["line"]
    action = data["action"]
    new_code = data["new_code"]

    # Types
    if file is not None and not isinstance(file, str):
        raise JsonValidationError("Le champ 'file' doit être une chaîne ou null.")
    if line is not None and not isinstance(line, int):
        raise JsonValidationError("Le champ 'line' doit être un entier ou null.")
    if not isinstance(action, str):
        raise JsonValidationError("Le champ 'action' doit être une chaîne.")
    if new_code is not None and not isinstance(new_code, str):
        raise JsonValidationError("Le champ 'new_code' doit être une chaîne ou null.")

    # Action cohérente
    allowed_actions = {"replace", "insert", "delete", "none"}
    if action not in allowed_actions:
        raise JsonValidationError(f"Action inconnue : {action}")

    if action == "none":
        # Aucun changement attendu
        if not (file is None and line is None and new_code is None):
            raise JsonValidationError("Pour action 'none', file/line/new_code doivent être null.")
        return data

    # Pour les autres actions, on doit avoir un fichier et une ligne valides
    if file is None or line is None:
        raise JsonValidationError("Pour une action autre que 'none', 'file' et 'line' ne peuvent pas être null.")

    if line < 1 or line > max_line:
        raise JsonValidationError(f"Numéro de ligne invalide : {line}. Le fichier a {max_line} lignes.")

    if action in {"replace", "insert"} and (new_code is None or new_code.strip() == ""):
        raise JsonValidationError(f"Action '{action}' nécessite un 'new_code' non vide.")

    if action == "delete" and new_code not in (None, "", " "):
        raise JsonValidationError("Pour 'delete', 'new_code' doit être vide ou null.")

    return data
