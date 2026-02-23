# conftest.py — Import des hooks QA Autopilot
#
# Si qa_autopilot est installé via pip, les hooks sont
# enregistrés automatiquement via l'entry-point pytest11.
#
# Ce fichier n'est nécessaire QUE si tu utilises
# qa_autopilot.py en mode fichier local (sans pip install).

from qa_autopilot import (
    pytest_addoption,
    pytest_configure,
    _qa_autopilot_fixture,
    pytest_runtest_makereport,
    pytest_sessionfinish,
)
