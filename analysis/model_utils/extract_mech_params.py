import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd



_NON_CONDUCTANCE_FALLBACKS = {
    # Calcium concentration dynamics mechanisms generally do not expose a
    # conductance-like parameter, but these variables are often treated as the
    # mechanism's main tunable scalar in the reduced cell json files.
    "cadad": "cainf",
    "cad_int": "cainf",
    "Cad_int": "Cainf",
    "iconc_Ca": "caiinf",
}


def _build_mech_range_map(mod_dir: Path) -> Dict[str, List[str]]:
    """Parse mod files and return SUFFIX -> RANGE variables."""
    mech_ranges: Dict[str, List[str]] = {}
    suffix_re = re.compile(r"^\s*SUFFIX\s+(\w+)", re.IGNORECASE)
    range_re = re.compile(r"\bRANGE\b\s+([^\n]+)", re.IGNORECASE)

    for mod_path in sorted(mod_dir.glob("*.mod")):
        text = mod_path.read_text(encoding="utf-8", errors="ignore")

        suffix_match = suffix_re.search(text)
        if not suffix_match:
            continue
        suffix = suffix_match.group(1)

        # Collect RANGE blocks that may span multiple lines until a closing brace.
        ranges: List[str] = []
        in_neuron_block = False
        buffer: List[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("NEURON"):
                in_neuron_block = True
            if in_neuron_block:
                buffer.append(raw_line)
            if in_neuron_block and "}" in line:
                break

        neuron_text = "\n".join(buffer)
        for m in range_re.finditer(neuron_text):
            entries = [v.strip() for v in m.group(1).split(",")]
            ranges.extend(v for v in entries if v)

        mech_ranges[suffix] = ranges

    return mech_ranges


def _pick_conductance_var(
        mech: str,
        mech_params: Dict[str, float],
        #mech_ranges: Dict[str, List[str]]
        ) -> Optional[str]:
    """Pick the most likely conductance variable for one mechanism."""
    if not mech_params:
        return None

    keys = [k for k, v in mech_params.items() if isinstance(v, (int, float))]
    if not keys:
        return None

    if mech in _NON_CONDUCTANCE_FALLBACKS and _NON_CONDUCTANCE_FALLBACKS[mech] in mech_params:
        return _NON_CONDUCTANCE_FALLBACKS[mech]

    # Prefer variables that are declared RANGE in the source mod mechanism.
    #range_keys = set(mech_ranges.get(mech, []))
    #considered = [k for k in keys if k in range_keys] or keys
    considered = keys

    exact_priority = [
        "gbar",
        "gmax",
        "g",
        "gkbar",
        "gnabar",
        "gnafbar",
        "gkdrbar",
        "gkabar",
        "gkcbar",
        "gcalbar",
        "gcanbar",
        "gcatbar",
        "gcabar",
        "ghbar",
        "gpeak",
        "gKsbar",
        "pcabar",
    ]
    for candidate in exact_priority:
        if candidate in considered:
            return candidate

    # Common conductance/permeability naming patterns.
    for k in considered:
        low = k.lower()
        if low.startswith("g") or low.endswith("g") or "gbar" in low:
            return k

    for k in considered:
        low = k.lower()
        if low.startswith("p") and low.endswith("bar"):
            return k

    # Fallback: first sorted numeric key for mechs without obvious conductance.
    return sorted(considered)[0]


def build_mech_g_df(
    pops: Iterable[str],
    cells_dir: str | Path = "cells",
    mod_dir: str | Path = "mod",
) -> "pd.DataFrame":
    """
    Build a dataframe with one row per (pop, section) and one conductance-like
    column per mechanism.

    Parameters
    ----------
    pops
        Population names, e.g. ["IT2", "PV", "TC"].
    cells_dir
        Directory that contains *_reduced_cellParams.json files.
    mod_dir
        Directory that contains *.mod files for mechanism lookup.

    Returns
    -------
    pandas.DataFrame
        Columns start with ["pop", "sec"], followed by "mech.var" columns.
    """
    import pandas as pd

    cells_dir = Path(cells_dir)
    mod_dir = Path(mod_dir)
    #mech_ranges = _build_mech_range_map(mod_dir)

    rows = []
    all_cols = set()

    for pop in pops:
        json_path = cells_dir / f"{pop}_reduced_cellParams.json"

        cell_data = json.loads(json_path.read_text(encoding="utf-8"))
        for sec_name, sec_data in cell_data.get("secs", {}).items():
            row = {"pop": pop, "sec": sec_name}
            mechs = sec_data.get("mechs", {})
            for mech_name, mech_params in mechs.items():
                if not isinstance(mech_params, dict):
                    continue
                var_name = _pick_conductance_var(mech_name, mech_params)
                if var_name is None:
                    continue
                column = f"{mech_name}.{var_name}"
                row[column] = mech_params[var_name]
                all_cols.add(column)

            rows.append(row)

    ordered_cols = ["pop", "sec"] + sorted(all_cols)
    return pd.DataFrame(rows).reindex(columns=ordered_cols)


if __name__ == "__main__":
    cells_dir = Path(__file__).parents[2] / 'cells'
    demo = build_mech_g_df(["IT2", "PV", "TC"])
    print(demo.head())
