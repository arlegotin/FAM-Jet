"""Current source/config binding; reviewed independent math reused unchanged."""
from pathlib import Path
from famjet.config import load_config
from task18_epsilon_learning_gate import EXPECTED,PACKAGE,sha
from task18_structured_epsilon_numeric import metric,static_inventory,reference_structured,ORIGIN,ORIGIN_PACKAGE

def config(family):return load_config(Path('artifacts/task18-evidence/epsilon1em6-learning-preparation-76e5f8c')/(family+'-learning.yaml'))
