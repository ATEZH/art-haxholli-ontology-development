\# ALD HfO2 Ontology Builder



`build\_model.py` builds and validates the fixed-BS3 ALD HfO2 Deposition ontology from `claim\_ledger.xlsx`. It writes deterministic Turtle and a validation report.



\## Requirements



\- Python 3.11 or newer

\- `rdflib>=7.2`

\- `pandas>=2.0`

\- `openpyxl>=3.1`

\- Java 11 or newer for running ROBOT

\- ROBOT with the HermiT reasoner; required when using `--release` and optional for a standard run



Install the Python dependencies in your environment:



```bash

python -m pip install "rdflib>=7.2" "pandas>=2.0" "openpyxl>=3.1"

```

The workbook must contain:



\- `Corrected Ledger`

\- `Output 3 - Coverage`



For a release run, install ROBOT separately and supply its executable through `--robot`. On Windows, use the path to `robot.bat`, not directly to `robot.jar`. For example:



```powershell

\--robot "C:\\Tools\\robot\\robot.bat"

```



If ROBOT is already on the system `PATH`, `--robot robot` is sufficient. Verify the installation with `robot help` and verify Java with `java -version`.



\## Standard run



```bash

python build\_model.py --ledger claim\_ledger.xlsx --sheet "Corrected Ledger" --out model.ttl --report-date 2026-08-20 --run-cq

```



This produces:



\- `model.ttl` — canonical Turtle ontology

\- `model.validation.txt` — structural-validation report



Window scaffolding and report-derived gaps are enabled by default. Disable them with `--no-window-scaffold` or `--no-report-derived-gaps`.



\## Release run



Release mode requires a ROBOT executable and automatically enables strict parsing, both scaffolds, competency questions, deterministic rebuild testing, OWL 2 DL profile validation, and HermiT reasoning.



```bash

python build\_model.py --ledger claim\_ledger.xlsx --sheet "Corrected Ledger" --out model.ttl --report-date 2026-08-20 --release --robot /path/to/robot

```



Use `python build\_model.py --help` to see all options.

