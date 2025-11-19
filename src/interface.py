import streamlit as st
import os
import json

from executor import run_python_script
from ai_agent import ask_ai_for_correction, ask_ai_for_explanation
from json_validator import validate_json_correction
from patcher import apply_patch, restore_backup


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

    # --------- 1) CONFIGURATION ---------
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

    # Choix du provider IA
    provider = st.radio(
        "Choisir le fournisseur IA",
        options=["mistral", "groq"],
        index=0,
        format_func=lambda x: "Mistral AI" if x == "mistral" else "Groq"
    )

    # --------- 2) LANCER L'ANALYSE (remplit session_state) ---------
    if st.button("Lancer l'analyse"):
        new_config = {
            "project_path": project_path,
            "script_path": script_path,
            "venv_python": venv_python
        }
        if save_cfg:
            save_config(new_config)
            st.success("Configuration sauvegardée ✅")

        script_full_path = os.path.join(project_path, script_path)

        # Lecture du code
        try:
            with open(script_full_path, "r", encoding="utf-8") as f:
                code = f.read()
        except FileNotFoundError:
            st.error(f"Script introuvable : {script_full_path}")
            st.session_state.pop("analysis", None)
            return

        # Exécution initiale
        try:
            stdout, stderr, returncode = run_python_script(
                project_root=project_path,
                script_relative_path=script_path,
                python_executable=venv_python
            )
        except FileNotFoundError as e:
            st.error(str(e))
            st.session_state.pop("analysis", None)
            return

        analysis = {
            "project_path": project_path,
            "script_path": script_path,
            "venv_python": venv_python,
            "script_full_path": script_full_path,
            "code": code,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": returncode,
            "provider": provider,
        }

        # S'il n'y a pas d'erreur : pas besoin d'IA
        if returncode == 0:
            analysis["explanation"] = "Le script s'est exécuté sans erreur. Aucune correction nécessaire."
            analysis["ai_raw"] = ""
            analysis["correction"] = None
            st.session_state["analysis"] = analysis
        else:
            # Explication pour débutant
            try:
                explanation = ask_ai_for_explanation(code, stderr, provider=provider)
            except Exception as e:
                explanation = f"Impossible d'obtenir une explication de l'IA : {e}"

            # Proposition de correction
            try:
                ai_raw = ask_ai_for_correction(code, stderr, provider=provider)
                correction = validate_json_correction(ai_raw)
                analysis["ai_raw"] = ai_raw
                analysis["correction"] = correction
            except Exception as e:
                analysis["ai_raw"] = str(e)
                analysis["correction"] = None

            analysis["explanation"] = explanation
            st.session_state["analysis"] = analysis

        st.success("Analyse terminée. Les résultats sont affichés plus bas.")

    # --------- 3) AFFICHAGE DES RÉSULTATS STOCKÉS ---------
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info("Lance une analyse pour voir les résultats.")
        return

    code = analysis["code"]
    stdout = analysis["stdout"]
    stderr = analysis["stderr"]
    returncode = analysis["returncode"]
    explanation = analysis.get("explanation", "")
    ai_raw = analysis.get("ai_raw", "")
    correction = analysis.get("correction", None)
    script_full_path = analysis["script_full_path"]
    project_path = analysis["project_path"]
    script_path = analysis["script_path"]
    venv_python = analysis["venv_python"]

    # 1️⃣ Code source actuel
    st.subheader("1️⃣ Code source actuel")
    st.code(code, language="python")

    # 2️⃣ Exécution initiale
    st.subheader("2️⃣ Exécution initiale du script")
    st.markdown("**Sortie standard (stdout)**")
    st.code(stdout or "(vide)")
    st.markdown("**Erreur (stderr)**")
    st.code(stderr or "(aucune erreur)")

    if returncode == 0:
        st.success("Le script s'est exécuté sans erreur. Rien à corriger.")
        return

    # 3️⃣ Explication de l'erreur
    st.subheader("3️⃣ Explication de l'erreur (pour débutant)")
    st.write(explanation)

    # 4️⃣ Proposition de correction
    st.subheader("4️⃣ Proposition de correction par l'IA")
    st.markdown("**Réponse brute de l'IA (JSON attendu)**")
    st.code(ai_raw, language="json")

    if correction is None:
        st.error("Aucune correction exploitable n'a été produite par l'IA.")
        return

    # 5️⃣ Validation + affichage du JSON
    st.subheader("5️⃣ JSON de correction validé")
    st.json(correction)

    # 6️⃣ Application du patch (validation manuelle)
    st.subheader("6️⃣ Application du patch (validation manuelle)")
    apply_confirm = st.checkbox(
        "✅ Je confirme que je veux appliquer cette correction au fichier",
        key="confirm_patch"
    )

    if st.button("Appliquer cette correction au fichier"):
        if not apply_confirm:
            st.warning("Coche d'abord la case de confirmation avant d'appliquer le patch.")
            return

        try:
            modified_file_path = apply_patch(project_root=project_path, correction=correction)
            st.success(f"Patch appliqué au fichier : {modified_file_path}")
        except Exception as e:
            st.error(f"Erreur lors de l'application du patch : {e}")
            return

        # Relire le fichier corrigé
        st.markdown("**Nouveau contenu du fichier corrigé**")
        try:
            with open(script_full_path, "r", encoding="utf-8") as f:
                new_code = f.read()
            st.code(new_code, language="python")
        except Exception as e:
            st.error(f"Impossible de relire le fichier corrigé : {e}")
            return

        # 7️⃣ Ré-exécution après correction
        st.subheader("7️⃣ Ré-exécution après correction")
        stdout2, stderr2, returncode2 = run_python_script(
            project_root=project_path,
            script_relative_path=script_path,
            python_executable=venv_python
        )

        st.markdown("**Sortie standard (après correction)**")
        st.code(stdout2 or "(vide)")
        st.markdown("**Erreur (après correction)**")
        st.code(stderr2 or "(aucune erreur)")

        if returncode2 == 0:
            st.success("Le script s'est exécuté sans erreur après correction ✅")
        else:
            st.warning("Il reste des erreurs après correction.")

    # 8️⃣ Bouton de restauration depuis le .bak
    backup_path = script_full_path + ".bak"
    if os.path.exists(backup_path):
        st.subheader("8️⃣ Restaurer la version précédente (.bak)")
        st.info(f"Un backup existe pour ce fichier : {backup_path}")

        if st.button("Restaurer le fichier depuis le backup (.bak)"):
            try:
                restored_path = restore_backup(
                    project_root=project_path,
                    file_name=os.path.basename(script_full_path)
                )
                st.success(f"Fichier restauré depuis le backup : {restored_path}")

                # Relire le contenu restauré
                try:
                    with open(script_full_path, "r", encoding="utf-8") as f:
                        restored_code = f.read()
                    st.markdown("**Contenu du fichier après restauration**")
                    st.code(restored_code, language="python")
                except Exception as e:
                    st.error(f"Impossible de relire le fichier restauré : {e}")
                    return

                # Ré-exécuter le script restauré
                st.subheader("Ré-exécution après restauration")
                stdout_r, stderr_r, returncode_r = run_python_script(
                    project_root=project_path,
                    script_relative_path=script_path,
                    python_executable=venv_python
                )
                st.markdown("**Sortie standard (après restauration)**")
                st.code(stdout_r or "(vide)")
                st.markdown("**Erreur (après restauration)**")
                st.code(stderr_r or "(aucune erreur)")

            except Exception as e:
                st.error(f"Erreur lors de la restauration du backup : {e}")


if __name__ == "__main__":
    main()
