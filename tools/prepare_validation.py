"""Create disposable HA configurations using only synthetic test fixtures."""
import argparse
from pathlib import Path
import shutil
import sys

import yaml
import generate as g

sys.path.insert(0,str(g.ROOT/"tests"))
from test_policy import configured

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--directory",default="output/validation")
args=parser.parse_args()
root=Path(args.directory)
if root.exists():
    parser.error("Choose a new directory; existing validation output is not overwritten")
for name,cfg in [("baseline",g.load(g.ROOT/"config.example.yaml")),("configured",configured())]:
    folder=root/name
    (folder/"packages").mkdir(parents=True)
    (folder/"configuration.yaml").write_text("homeassistant:\n  name: Isolated validation\n  latitude: 0\n  longitude: 0\n  elevation: 0\n  unit_system: metric\n  time_zone: UTC\n  packages: !include_dir_named packages\n")
    (folder/"packages/tesla_grok.yaml").write_text(yaml.safe_dump(g.build(cfg),sort_keys=False,allow_unicode=True))
    if name=="configured":
        shutil.copyfile(g.ROOT/"examples/adapters.yaml",folder/"packages/adapters.yaml")
print("Two disposable configurations prepared. No real entity inventory used.")
