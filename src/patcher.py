import os
import shutil
from typing import Dict, Any, List


def apply_indent(original_line: str, new_code: str) -> str:
    """
    Conserve l'indentation de la ligne originale pour éviter les erreurs Python.

    original_line : la ligne telle qu'elle était dans le fichier avant correction
    new_code      : la nouvelle ligne proposée par l'IA (souvent sans indentation)

    On récupère le nombre d'espaces au début de la ligne originale,
    puis on les applique à la nouvelle ligne.
    """
    # Nombre de caractères d'indentation (espaces, éventuellement tabulations)
    indent = len(original_line) - len(original_line.lstrip())

    # On enlève l'indentation éventuelle de new_code, puis on remet celle de base
    return " " * indent + new_code.lstrip()


def apply_patch(project_root: str, correction: Dict[str, Any]) -> str:
    """
    Applique une correction sur un fichier source.
    :param project_root: Chemin racine du projet.
    :param correction: Dictionnaire de correction validé.
    :return: Chemin du fichier modifié.
    """
    action = correction["action"]

    if action == "none":
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

    index = line_number - 1  # passage 1-based -> 0-based

    if action == "replace":
        print(f"[patcher] Remplacement de la ligne {line_number} dans {file_name}")

        # Ligne originale (avec indentation correcte)
        original_line = lines[index]

        # On applique la même indentation à la nouvelle ligne
        new_line = apply_indent(original_line, new_code)

        # On veille à ce que la nouvelle ligne se termine par un saut de ligne
        if not new_line.endswith("\n"):
            new_line = new_line + "\n"

        lines[index] = new_line

    elif action == "insert":
        print(f"[patcher] Insertion avant la ligne {line_number} dans {file_name}")
        if not new_code.endswith("\n"):
            new_code = new_code + "\n"
        lines.insert(index, new_code)

    elif action == "delete":
        print(f"[patcher] Suppression de la ligne {line_number} dans {file_name}")
        lines.pop(index)

    # Écriture du fichier modifié
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return file_path