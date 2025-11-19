import os
import json

from executor import run_python_script
from ai_agent import ask_ai_for_correction
from json_validator import parse_and_validate_correction, JsonValidationError
from patcher import apply_patch


def load_config() -> dict:
    """Charge la configuration depuis src/config.json (par rapport à ce fichier)."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "config.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Fichier de configuration introuvable : {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_file(path: str) -> str:
    """Lit un fichier texte entier et le renvoie sous forme de chaîne."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    # 1. Chargement de la configuration
    config = load_config()
    project_root = config["project_path"]
    script_relative_path = config["script_path"]
    venv_python = config.get("venv_python")  # peut être None

    print("[main] Projet racine :", project_root)
    print("[main] Script cible :", script_relative_path)
    print("[main] Interpréteur Python (venv) :", venv_python or "(sys.executable)")

    # 2. Première exécution du script (avec bug)
    stdout, stderr, returncode = run_python_script(project_root, script_relative_path, venv_python)

    print("\n[main] ---- SORTIE STANDARD ----")
    print(stdout)
    print("[main] ---- ERREUR ----")
    print(stderr)

    if returncode == 0:
        print("[main] Le script s'est exécuté sans erreur. Rien à corriger.")
        return

    # 3. Lecture du code source
    script_path = os.path.join(project_root, script_relative_path)
    code = read_file(script_path)

    # 4. Appel (IA) pour obtenir une correction
    ai_response_text = ask_ai_for_correction(code, stderr, provider="mistral")
    print("\n[main] ---- RÉPONSE IA BRUTE ----")
    print(ai_response_text)

    # 5. Validation du JSON de correction
    max_line = len(code.splitlines())
    try:
        correction = parse_and_validate_correction(ai_response_text, max_line)
    except JsonValidationError as e:
        print("[main] JSON de correction invalide :", e)
        return

    print("\n[main] ---- CORRECTION VALIDÉE ----")
    print(correction)

    # 6. Application du patch
    modified_file_path = apply_patch(project_root, correction)
    print("\n[main] Fichier modifié :", modified_file_path)

    # 7. Ré-exécution du script pour vérifier que l'erreur a disparu
    print("\n[main] Ré-exécution du script après correction...")
    stdout2, stderr2, returncode2 = run_python_script(project_root, script_relative_path, venv_python)

    print("\n[main] ---- SORTIE STANDARD (après correction) ----")
    print(stdout2)
    print("[main] ---- ERREUR (après correction) ----")
    print(stderr2)

    if returncode2 == 0:
        print("[main] ✅ Le script s'est exécuté sans erreur après correction.")
    else:
        print("[main] ❌ Il reste des erreurs après correction.")


if __name__ == "__main__":
    main()
