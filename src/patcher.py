import os
import shutil
from typing import Dict, Any, List


def apply_indent(reference_line: str, new_code: str) -> str:
    """
    Conserve l'indentation de la ligne de référence sur la nouvelle ligne.

    - On récupère le préfixe d'espaces / tabulations de reference_line.
    - On supprime l'indentation superflue au début de new_code.
    - On renvoie le code corrigé avec la bonne indentation.
    """
    if reference_line is None:
        # Pas de ligne de référence → on renvoie la ligne telle quelle
        return new_code

    # Préfixe d'indentation (espaces ou tabs) de la ligne originale
    indent_prefix = ""
    for ch in reference_line:
        if ch in (" ", "\t"):
            indent_prefix += ch
        else:
            break

    return indent_prefix + new_code.lstrip("\t ")


def apply_patch(project_root: str, correction: Dict[str, Any]) -> str:
    """
    Applique une correction sur un fichier source.

    :param project_root: Chemin racine du projet.
    :param correction: Dictionnaire de correction validé, de forme :
        {
            "file": "buggy_script.py",
            "line": 3,
            "action": "replace" | "insert" | "delete" | "none",
            "new_code": "return a / b if b != 0 else None"
        }
    :return: Chemin du fichier modifié (ou message si aucune correction).
    """
    action = correction["action"]

    # Cas particulier : aucune correction à appliquer
    if action == "none":
        print("[patcher] Aucune correction à appliquer (action = none).")
        return "Aucune correction à appliquer."

    file_name = correction["file"]
    line_number = correction["line"]
    new_code = correction["new_code"]

    # On suppose que les fichiers à corriger sont dans 'sources/'
    file_path = os.path.join(project_root, "sources", file_name)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Fichier à corriger introuvable : {file_path}")

    # Sauvegarde du fichier original
    backup_path = file_path + ".bak"
    shutil.copyfile(file_path, backup_path)
    print(f"[patcher] Sauvegarde du fichier original : {backup_path}")

    # Lecture des lignes
    with open(file_path, "r", encoding="utf-8") as f:
        lines: List[str] = f.readlines()

    # Passage 1-based -> 0-based
    index = line_number - 1

    if index < 0 or index > len(lines):
        raise IndexError(
            f"Numéro de ligne invalide : {line_number} (fichier '{file_name}' "
            f"contient {len(lines)} lignes)"
        )

    # --- ACTION: REPLACE ---
    if action == "replace":
        print(f"[patcher] Remplacement de la ligne {line_number} dans {file_name}")

        if index >= len(lines):
            raise IndexError(
                f"Impossible de remplacer la ligne {line_number} : index hors limites."
            )

        original_line = lines[index]
        new_line = apply_indent(original_line, new_code)

        # S'assurer que la ligne finit par un saut de ligne
        if not new_line.endswith("\n"):
            new_line += "\n"

        lines[index] = new_line

    # --- ACTION: INSERT ---
    elif action == "insert":
        print(f"[patcher] Insertion avant la ligne {line_number} dans {file_name}")

        # Ligne de référence pour l'indentation :
        # si on insère au début, on ne connaît pas encore l'indentation → pas de préfixe
        if 0 <= index < len(lines):
            ref_line = lines[index]
        elif index > 0:
            ref_line = lines[index - 1]
        else:
            ref_line = ""

        new_line = apply_indent(ref_line, new_code)

        if not new_line.endswith("\n"):
            new_line += "\n"

        lines.insert(index, new_line)

    # --- ACTION: DELETE ---
    elif action == "delete":
        print(f"[patcher] Suppression de la ligne {line_number} dans {file_name}")

        if index >= len(lines):
            raise IndexError(
                f"Impossible de supprimer la ligne {line_number} : index hors limites."
            )

        lines.pop(index)

    else:
        raise ValueError(f"Action de patch inconnue : {action}")

    # Écriture du fichier modifié
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"[patcher] Fichier mis à jour : {file_path}")
    return file_path


def restore_backup(project_root: str, file_name: str) -> str:
    """
    Restaure un fichier à partir de son backup .bak

    :param project_root: Racine du projet.
    :param file_name: Nom du fichier dans le dossier 'sources' (ex : 'buggy_1.py').
    :return: Chemin du fichier restauré.
    """
    file_path = os.path.join(project_root, "sources", file_name)
    backup_path = file_path + ".bak"

    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Aucun backup .bak trouvé pour : {file_path}")

    shutil.copyfile(backup_path, file_path)
    print(f"[patcher] Restauration depuis le backup : {backup_path} -> {file_path}")
    return file_path
