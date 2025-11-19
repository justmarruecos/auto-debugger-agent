import subprocess
import sys
import os
from typing import Tuple


def run_python_script(
    project_root: str,
    script_relative_path: str,
    python_executable: str | None = None
) -> Tuple[str, str, int]:
    """
    Exécute un script Python situé dans le projet et capture stdout, stderr, returncode.

    :param project_root: Chemin absolu du dossier racine du projet.
    :param script_relative_path: Chemin du script depuis la racine (ex: 'sources/buggy_script.py').
    :param python_executable: Chemin vers l'interpréteur Python à utiliser (venv du projet).
                              Si None, utilise sys.executable (environnement courant).
    :return: (stdout, stderr, returncode)
    """
    # Construit le chemin complet vers le script
    script_path = os.path.join(project_root, script_relative_path)

    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script introuvable : {script_path}")

    # Si aucun interpréteur n'est fourni, on utilise celui de l'environnement courant
    if python_executable is None or python_executable.strip() == "":
        python_executable = sys.executable

    print(f"[executor] Exécution du script : {script_path}")
    print(f"[executor] Interpréteur Python utilisé : {python_executable}")

    result = subprocess.run(
        [python_executable, script_path],
        capture_output=True,
        text=True
    )

    stdout = result.stdout
    stderr = result.stderr
    returncode = result.returncode

    return stdout, stderr, returncode
