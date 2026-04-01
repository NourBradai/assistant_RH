"""
Utilitaires pour le nettoyage et la normalisation du texte.
Prépare le texte extrait des PDFs pour une analyse optimale par Regex.
"""
import re


def clean_text(text: str) -> str:
    """
    Nettoie le texte extrait d'un PDF :
    - Normalise les retours à la ligne (\r, \n).
    - Remplace les tabulations par des espaces.
    - Supprime les espaces multiples.
    - Évite les successions de lignes vides.
    """
    if not text:
        return ""

    # Uniformisation des retours chariots
    text = text.replace("\r", "\n")

    # Suppression des tabulations
    text = text.replace("\t", " ")

    # Suppression des espaces multiples (ex: "  " devient " ")
    text = re.sub(r"[ ]{2,}", " ", text)

    # Réduction des lignes vides consécutives
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()