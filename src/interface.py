import streamlit as st
import os
import json

from executor import run_python_script
from ai_agent import ask_ai_for_correction
from json_validator import parse_and_validate_correction, JsonValidationError
from patcher import apply_patch


def load_config() -> dict:
    """
    Charge la configuration depuis src/config.json si présent,
    sinon propose des valeurs par défaut.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "config.json")

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Valeurs par défaut si pas de config
    project_root_default = os.path.abspath(os.path.join(current_dir, ".."))
    return {
        "project_path": project_root_default,
        "script_path": "sources/buggy_script.py",
        "venv_python": ""
    }


def save_config(config: dict) -> None:
    """
    Sauvegarde la configuration dans src/config.json
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def main():
    st.title("🪲 Agent de debugging Python (version Streamlit)")

    # 1) Chargement / édition de la configuration
    config = load_config()

    default_project = config.get("project_path")
    default_script = config.get("script_path", "sources/buggy_script.py")
    default_venv_python = config.get("venv_python", "")

    project_path = st.text_input(
        "Chemin du projet",
        value=default_project,
        help="Dossier racine où se trouve ton projet (auto-debugger-agent)."
    )
    project_path = os.path.abspath(project_path)

    # Découverte des scripts dans /sources
    sources_dir = os.path.join(project_path, "sources")
    script_options = []

    if os.path.isdir(sources_dir):
        for name in os.listdir(sources_dir):
            if name.endswith(".py"):
                script_options.append(os.path.join("sources", name))

    if not script_options:
        script_options = [default_script]

    if default_script in script_options:
        default_index = script_options.index(default_script)
    else:
        default_index = 0

    script_path = st.selectbox(
        "Script à analyser",
        options=script_options,
        index=default_index,
        help="Choisis le script Python à exécuter et corriger."
    )

    venv_python = st.text_input(
        "Chemin de l'interpréteur Python du projet (venv)",
        value=default_venv_python,
        help="Exemple : C:/25-26/venv2526/Scripts/python.exe"
    )

    if venv_python.strip() == "":
        st.info(
            "Aucun interpréteur de venv spécifié. "
            "L'agent utilisera l'environnement Python courant (sys.executable)."
        )

    save_cfg = st.checkbox("Sauvegarder la configuration", value=True)

    if st.button("Lancer l'analyse"):
        # Met à jour / sauve la config
        new_config = {
            "project_path": project_path,
            "script_path": script_path,
            "venv_python": venv_python
        }
        if save_cfg:
            save_config(new_config)
            st.success("Configuration sauvegardée ✅")

        # 2) Afficher le code source
        st.subheader("1️⃣ Code source actuel")
        script_full_path = os.path.join(project_path, script_path)

        try:
            with open(script_full_path, "r", encoding="utf-8") as f:
                code = f.read()
            st.code(code, language="python")
        except FileNotFoundError:
            st.error(f"Script introuvable : {script_full_path}")
            return

        # 3) Exécution initiale du script
        st.subheader("2️⃣ Exécution initiale du script")
        try:
            stdout, stderr, returncode = run_python_script(project_path, script_path, venv_python)
        except FileNotFoundError as e:
            st.error(str(e))
            return

        st.markdown("**Sortie standard (stdout)**")
        st.code(stdout or "(vide)")
        st.markdown("**Erreur (stderr)**")
        st.code(stderr or "(aucune erreur)")

        if returncode == 0:
            st.success("Le script s'est exécuté sans erreur. Rien à corriger.")
            return

        # 4) Appel IA (Mistral ou autre, via ai_agent.py)
        st.subheader("3️⃣ Proposition de correction par l'IA")
        ai_response_text = ask_ai_for_correction(code, stderr, provider="mistral")
        st.markdown("**Réponse brute de l'IA**")
        st.code(ai_response_text, language="json")

        # 5) Validation du JSON
        st.subheader("4️⃣ Validation du JSON de correction")
        max_line = len(code.splitlines())
        try:
            correction = parse_and_validate_correction(ai_response_text, max_line)
            st.success("JSON valide ✅")
            st.json(correction)
        except JsonValidationError as e:
            st.error(f"JSON de correction invalide : {e}")
            return

        # 6) Application du patch
        st.subheader("5️⃣ Application du patch")
        apply_auto = st.checkbox("Appliquer automatiquement la correction maintenant ?", value=True)

        if apply_auto:
            try:
                modified_file_path = apply_patch(project_path, correction)
                st.success(f"Patch appliqué au fichier : {modified_file_path}")
            except Exception as e:
                st.error(f"Erreur lors de l'application du patch : {e}")
                return

            # Afficher le nouveau code
            st.markdown("**Nouveau contenu du fichier corrigé**")
            try:
                with open(script_full_path, "r", encoding="utf-8") as f:
                    new_code = f.read()
                st.code(new_code, language="python")
            except Exception as e:
                st.error(f"Impossible de relire le fichier corrigé : {e}")
                return

            # 7) Ré-exécution après correction
            st.subheader("6️⃣ Ré-exécution après correction")
            stdout2, stderr2, returncode2 = run_python_script(project_path, script_path, venv_python)

            st.markdown("**Sortie standard (après correction)**")
            st.code(stdout2 or "(vide)")
            st.markdown("**Erreur (après correction)**")
            st.code(stderr2 or "(aucune erreur)")

            if returncode2 == 0:
                st.success("Le script s'est exécuté sans erreur après correction ✅")
            else:
                st.warning("Il reste des erreurs après correction.")
        else:
            st.info("La correction n'a pas été appliquée. Coche la case pour appliquer le patch.")


if __name__ == "__main__":
    main()
