"""Execute Phase 2 without modifying the original foundation launcher."""

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "ml-pipeline/preprocessing"))

from phase2 import prepare

import nbformat as nbf
from nbclient import NotebookClient
from jupyter_client.kernelspec import KernelSpecManager
import json
import tempfile


def execute_notebooks():

    common = '''from pathlib import Path
import json
import pandas as pd
from IPython.display import display, Image

ROOT = Path.cwd()

if not (ROOT / 'data/processed').exists():
    ROOT = ROOT.parent

assert (ROOT / 'data/processed/train.csv').exists(), 'Run python scripts/run_phase2.py first'

train = pd.read_csv(ROOT / 'data/processed/train.csv')'''

    specs = [
        (
            "01_data_exploration.ipynb",
            "Exploratory data analysis",
            "Training-only analysis; validation and test outcomes are reserved.",
            [
                "display(train[['Area','Bedrooms','Bathrooms','Age','Price']].describe().round(2))",

                "display(Image(filename=str(ROOT/'visualizations/price_distribution.png')))\n"
                "display(Image(filename=str(ROOT/'visualizations/area_vs_price.png')))",

                "display(Image(filename=str(ROOT/'visualizations/location_analysis.png')))\n"
                "display(Image(filename=str(ROOT/'visualizations/property_type_analysis.png')))"
            ]
        ),
        (
            "02_data_preprocessing.ipynb",
            "Data validation and preprocessing",
            "Original hashes verified; strict schema checks; deterministic 70/15/15 split.",
            [
                "quality = json.loads((ROOT/'reports/data_quality.json').read_text())\n"
                "display(pd.DataFrame([{'dataset':k,'rows':v['rows'],'columns':len(v['columns']),'missing':v['missing_cells'],'duplicates':v['duplicate_rows'],'integrity':v['integrity']} for k,v in quality['datasets'].items()]))",

                "report = json.loads((ROOT/'reports/preprocessing_report.json').read_text())\n"
                "display(pd.Series(report['split_counts'], name='Rows').to_frame())\n"
                "print('Fitted on:', report['fit_partition'])\n"
                "print('Excluded predictors:', report['excluded_predictors'])",

                "display(pd.DataFrame({'transformed_feature':report['transformed_features']}))"
            ]
        ),
        (
            "03_feature_engineering.ipynb",
            "Feature engineering",
            "Only input-derived ratios are added. Encoder and scaler fitted on training rows; refit inside future CV folds.",
            [
                "engineered = pd.DataFrame({'Area_per_bedroom':train.Area/train.Bedrooms,'Bathrooms_per_bedroom':train.Bathrooms/train.Bedrooms})\n"
                "display(engineered.describe().round(3))",

                "display(Image(filename=str(ROOT/'visualizations/correlation_heatmap.png')))",

                "print('No target-derived predictors or identifier in feature matrix. Unknown categories are ignored by the fitted encoder. No model trained.')"
            ]
        )
    ]

    # Use the currently activated Python environment.
    with tempfile.TemporaryDirectory() as tmp:

        path = Path(tmp) / "kernels" / "task6phase2"
        path.mkdir(parents=True)

        (path / "kernel.json").write_text(
            json.dumps({
                "argv": [
                    sys.executable,
                    "-m",
                    "ipykernel_launcher",
                    "-f",
                    "{connection_file}"
                ],
                "display_name": "Task 6 Phase 2",
                "language": "python"
            })
        )

        manager = KernelSpecManager(
            kernel_dirs=[str(Path(tmp) / "kernels")]
        )

        from jupyter_client import KernelManager

        for filename, title, description, cells in specs:

            nb = nbf.v4.new_notebook(
                cells=[
                    nbf.v4.new_markdown_cell(
                        "# " + title + "\n\n" + description
                    ),
                    nbf.v4.new_code_cell(common)
                ] + [
                    nbf.v4.new_code_cell(c) for c in cells
                ],
                metadata={
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3"
                    },
                    "language_info": {
                        "name": "python"
                    }
                }
            )

            km = KernelManager(
                kernel_name="task6phase2",
                kernel_spec_manager=manager
            )

            client = NotebookClient(
                nb,
                km=km,
                timeout=120,
                resources={
                    "metadata": {
                        "path": str(ROOT)
                    }
                }
            )

            client.execute(cleanup_kc=True)

            nb.metadata["kernelspec"] = {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }

            nbf.write(
                nb,
                ROOT / "notebooks" / filename
            )

            print("Executed:", filename, flush=True)


def main():

    print(
        "PHASE 2 — DATA ENGINEERING",
        flush=True
    )

    result = prepare(ROOT)

    print(
        json.dumps(result, indent=2),
        flush=True
    )

    execute_notebooks()

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    (ROOT / "reports/phase2_test_results.txt").write_text(
        result.stdout
    )

    print(result.stdout, flush=True)

    if result.returncode:
        raise SystemExit(result.returncode)

    print(
        "PHASE 2 COMPLETE — no models trained. "
        "Reports, charts and notebooks generated.",
        flush=True
    )


if __name__ == "__main__":
    main()
