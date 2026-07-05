"""Offline integration tests for the static Jupyter report notebook generation."""
from __future__ import annotations

import json
import re
import sys
import importlib.util
from pathlib import Path

from techna import data_layer as dl

# Load techna.py dynamically to avoid collision with the techna package directory
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("techna_cli_notebook", str(ROOT / "techna.py"))
if spec is None or spec.loader is None:
    raise ImportError("Failed to load techna.py spec")
techna_cli = importlib.util.module_from_spec(spec)
sys.modules["techna_cli_notebook"] = techna_cli
spec.loader.exec_module(techna_cli)
main = techna_cli.main


def test_cli_generates_notebook(monkeypatch, golden_long_df, tmp_path):
    """Scenario: Running with --notebook generates a static .ipynb file next to the report."""
    mock_data = dl.PriceData(
        ticker="TEST",
        df=golden_long_df,
        source="fixture",
        warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    # Run CLI with --notebook and --explain to check briefing rendering too
    exit_code = main(["TEST", "--no-chart", "--no-interactive", "--notebook", "--explain", "--out", str(tmp_path)])
    assert exit_code == 0

    # Verify report notebook exists
    notebook_file = tmp_path / "TEST_report.ipynb"
    assert notebook_file.exists()

    # Read notebook
    with open(notebook_file, encoding="utf-8") as f:
        nb_data = json.load(f)

    # Verify basic notebook structure
    assert nb_data["nbformat"] >= 4
    assert isinstance(nb_data["cells"], list)
    assert len(nb_data["cells"]) > 0


def test_notebook_content_structure_and_no_code_cells(monkeypatch, golden_long_df, tmp_path):
    """Scenario: The generated notebook has only markdown cells, embeds findings and images."""
    mock_data = dl.PriceData(
        ticker="TEST",
        df=golden_long_df,
        source="fixture",
        warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    # Run CLI WITH charts (embedding needs real PNGs on disk to embed --
    # --no-chart would leave nothing to embed and defeat this test's purpose).
    exit_code = main(["TEST", "--no-interactive", "--notebook", "--explain", "--out", str(tmp_path)])
    assert exit_code == 0

    notebook_file = tmp_path / "TEST_report.ipynb"
    with open(notebook_file, encoding="utf-8") as f:
        nb_data = json.load(f)

    # Assert that all cells are markdown cells (no code execution cells)
    for cell in nb_data["cells"]:
        assert cell["cell_type"] == "markdown", f"Expected only markdown cells, found: {cell['cell_type']}"
        assert "source" in cell
        assert isinstance(cell["source"], list) or isinstance(cell["source"], str)

    # Check some expected content in cells
    source_texts = []
    for cell in nb_data["cells"]:
        src = cell["source"]
        if isinstance(src, list):
            source_texts.append("".join(src))
        else:
            source_texts.append(src)

    # Assert title exists
    assert any("Techna Analysis Report for TEST" in text for text in source_texts)

    # Assert analyst briefing section exists
    assert any("Analyst Briefing (Synthesis — Not Advice)" in text for text in source_texts)

    # Assert score profile table exists
    assert any("Score Profile (Independent Dimensions)" in text for text in source_texts)

    # Assert trend finding exists
    assert any("Trend Analysis" in text and "Finding:" in text for text in source_texts)

    # Assert static chart images are EMBEDDED as base64 data URIs (not relative
    # file links) -- so the notebook stays self-contained and portable even
    # when shared as a single file, without its sibling PNGs.
    assert any(
        "![Test Overview](data:image/png;base64," in text for text in source_texts
    )
    assert any(
        "![Test Momentum](data:image/png;base64," in text for text in source_texts
    )
    assert any(
        "![Test Correlogram](data:image/png;base64," in text for text in source_texts
    )
    # No relative-path image links should remain anywhere in the notebook.
    assert not any(re.search(r"!\[[^\]]*\]\([^)]*\.png\)", text) for text in source_texts)

    # Assert each chart is preceded by the live source of the drawing
    # function that produced it (fetched via inspect.getsource(), not
    # hand-copied) -- so anyone reading the notebook sees exactly what code
    # drew each image, without needing a separate showcase notebook.
    assert any(
        "Source: `report_builder.draw_overview_chart`" in text and "```python" in text
        for text in source_texts
    )
    assert any(
        "Source: `report_builder.draw_momentum_chart`" in text
        for text in source_texts
    )
    assert any(
        "Source: `report_builder.draw_correlogram_chart`" in text
        for text in source_texts
    )

    # Assert each module also shows its RAW metric numbers (not just the
    # prose finding) and the live source of the indicator function(s) that
    # computed them -- so the reader can check the actual figures, not only
    # a paraphrase, and see exactly what code produced them.
    assert any(
        "Raw metric values (from the JSON sidecar)" in text and "```json" in text
        for text in source_texts
    )
    assert any(
        "Source: `techna.indicators.momentum.compute_rsi`" in text and "```python" in text
        for text in source_texts
    )
    assert any(
        "Source: `techna.indicators.risk_context.compute_beta`" in text
        for text in source_texts
    )
    assert any(
        "Source: `techna.scoring.compute_dimension_scores`" in text
        for text in source_texts
    )

    # Assert each chart is ALSO followed by a plain-English "how this chart
    # works" explanation (docstrings, not raw code) -- complementing the
    # source-code cells above the image with prose a non-programmer can read.
    overview_idx = next(
        i for i, text in enumerate(source_texts)
        if "![Test Overview](data:image/png;base64," in text
    )
    explanation_text = source_texts[overview_idx + 1]
    assert explanation_text.startswith("#### How this chart works")
    assert "What's plotted:" in explanation_text
    assert "How the underlying numbers are computed:" in explanation_text


def test_notebook_is_portable_without_sibling_pngs(monkeypatch, golden_long_df, tmp_path):
    """Scenario: copying ONLY the .ipynb (no PNGs) elsewhere still shows every chart,
    because the images are embedded, not linked."""
    import shutil

    mock_data = dl.PriceData(
        ticker="TEST", df=golden_long_df, source="fixture", warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    exit_code = main(["TEST", "--no-interactive", "--notebook", "--out", str(tmp_path)])
    assert exit_code == 0

    # Copy ONLY the notebook file to a separate, empty directory.
    standalone_dir = tmp_path / "standalone"
    standalone_dir.mkdir()
    shutil.copy(tmp_path / "TEST_report.ipynb", standalone_dir / "TEST_report.ipynb")

    with open(standalone_dir / "TEST_report.ipynb", encoding="utf-8") as f:
        nb_data = json.load(f)

    all_source = "".join(
        "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        for c in nb_data["cells"]
    )
    # At least one embedded image must be present in the standalone copy.
    assert re.search(r"data:image/png;base64,[A-Za-z0-9+/=]{100,}", all_source)


def test_every_json_module_appears_in_the_notebook(monkeypatch, golden_long_df, tmp_path):
    """Regression: every module written to the JSON sidecar must also appear
    in the notebook's module_mapping.

    A module missing from module_mapping silently loses its finding, raw
    metrics, indicator source, AND chart in the notebook -- with no error
    anywhere (this happened for real with "volume_profile_weekly").
    """
    mock_data = dl.PriceData(
        ticker="TEST", df=golden_long_df, source="fixture", warnings=[],
    )
    monkeypatch.setattr(dl, "get_prices", lambda *args, **kwargs: mock_data)

    exit_code = main(["TEST", "--no-interactive", "--notebook", "--out", str(tmp_path)])
    assert exit_code == 0

    with open(tmp_path / "TEST_result.json", encoding="utf-8") as f:
        result = json.load(f)
    modules_by_name = {m["module"]: m for m in result["modules"]}

    with open(tmp_path / "TEST_report.ipynb", encoding="utf-8") as f:
        nb_data = json.load(f)
    source_texts = [
        "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        for c in nb_data["cells"]
    ]
    full_text = "\n".join(source_texts)

    # "briefing" is a real module in the JSON but is rendered as the
    # Analyst Briefing section, not through module_mapping -- excluded here.
    for mod_name, mod in modules_by_name.items():
        if mod_name == "briefing":
            continue
        finding_text = mod["metrics"].get("finding", "")
        assert finding_text and finding_text in full_text, (
            f"module '{mod_name}' finding is missing from the notebook -- "
            f"likely absent from render_report_notebook's module_mapping"
        )
