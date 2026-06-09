from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd
import xarray as xr


INPUT_PATH = Path(__file__).resolve().parent / "test_data" / "netParams_00000_seed_1000.json"
ROUND_DECIMALS = 3
EXPORT_NON_NUMERIC_AS_STR = 1
POP_GROUPS = {
    "L2": ["IT2", "PV2", "SOM2", "VIP2", "NGF2"],
}
POP_GROUP_NAME = "L2"


def _build_output_path() -> Path:
    parts = [f"{INPUT_PATH.stem}_probability_matrix"]
    if POP_GROUP_NAME is not None:
        parts.append(POP_GROUP_NAME)
    if EXPORT_NON_NUMERIC_AS_STR:
        parts.append("str")
    return INPUT_PATH.with_name("_".join(parts) + ".csv")


OUTPUT_PATH = _build_output_path()


def load_netparams(path: Path) -> dict:
    """Load the nested netParams payload from a saved NetPyNE json file."""
    with path.open("r", encoding="utf-8") as fid:
        data = json.load(fid)
    return data["net"]["params"]


def _is_simple_pop_conds(conds: object) -> bool:
    if not isinstance(conds, dict):
        return False
    return set(conds) in ({"pop"}, {"pop", "ynorm"})


def _extract_single_pop(conds: object) -> str | None:
    if not isinstance(conds, dict):
        return None

    pops = conds.get("pop")
    if isinstance(pops, list) and len(pops) == 1 and isinstance(pops[0], str):
        return pops[0]

    return None


def _report_non_pop_only_conn(
        conn_name: str,
        probability: object,
        pre_conds: object,
        post_conds: object,
        ) -> None:
    print(
        "Non-pop-only conditions:",
        conn_name,
        f"probability={probability}",
        f"preConds={pre_conds}",
        f"postConds={post_conds}",
    )


def _coerce_probability(probability: object) -> float | None:
    if isinstance(probability, (int, float, np.integer, np.floating)):
        return float(probability)
    return None


def _simplify_probability_expression(probability: object) -> object:
    if not isinstance(probability, str):
        return probability

    match = re.fullmatch(
        r"\s*([0-9]*\.?[0-9]+)\s*\*\s*exp\(\s*-dist_2D\s*/\s*([0-9]*\.?[0-9]+)\s*\)\s*",
        probability,
    )
    if match is None:
        return probability

    amplitude = round(float(match.group(1)), ROUND_DECIMALS)
    length = int(round(float(match.group(2))))
    return f"{amplitude:.{ROUND_DECIMALS}f} * L({length})"


def _get_pop_names(netparams: dict) -> list[str]:
    pop_names = [
        pop_name for pop_name in netparams.get("popParams", {})
        if "frz" not in pop_name
    ]
    if POP_GROUP_NAME is None:
        return sorted(pop_names)

    if POP_GROUP_NAME not in POP_GROUPS:
        raise ValueError(f"Unknown population group: {POP_GROUP_NAME}")

    ordered_group = POP_GROUPS[POP_GROUP_NAME]
    available = set(pop_names)
    return [pop_name for pop_name in ordered_group if pop_name in available]


def iter_relevant_connections(netparams: dict) -> Iterator[tuple[str, dict, dict, object]]:
    """Yield non-frz connections and report condition shapes beyond pop/ynorm."""
    for conn_name, conn in netparams.get("connParams", {}).items():
        if "frz" in conn_name:
            continue

        pre_conds = conn.get("preConds", {})
        post_conds = conn.get("postConds", {})
        probability = conn.get("probability")

        if not _is_simple_pop_conds(pre_conds) or not _is_simple_pop_conds(post_conds):
            _report_non_pop_only_conn(conn_name, probability, pre_conds, post_conds)

        yield conn_name, pre_conds, post_conds, probability


def build_probability_matrix(netparams: dict) -> xr.DataArray:
    """Build an alphabetical post x pre population probability matrix."""
    pop_names = _get_pop_names(netparams)
    pop_name_set = set(pop_names)

    probability_matrix = xr.DataArray(
        np.full((len(pop_names), len(pop_names)), 0.0, dtype=object),
        coords={"post_pop": pop_names, "pre_pop": pop_names},
        dims=("post_pop", "pre_pop"),
        name="probability",
    )

    pair_records: dict[tuple[str, str], list[tuple[str, object]]] = defaultdict(list)

    for conn_name, pre_conds, post_conds, probability in iter_relevant_connections(netparams):
        pre_pop = _extract_single_pop(pre_conds)
        post_pop = _extract_single_pop(post_conds)

        if pre_pop is None or post_pop is None:
            print(
                "Skipping unmappable connection:",
                conn_name,
                f"probability={probability}",
                f"preConds={pre_conds}",
                f"postConds={post_conds}",
            )
            continue

        if pre_pop not in pop_name_set or post_pop not in pop_name_set:
            continue

        pair_records[(pre_pop, post_pop)].append((conn_name, probability))

    for (pre_pop, post_pop), records in pair_records.items():
        numeric_values = {_coerce_probability(probability) for _, probability in records}
        string_values = {
            probability for _, probability in records
            if isinstance(probability, str)
        }

        has_numeric = None not in numeric_values
        has_string = bool(string_values)

        if has_numeric and not has_string and len(numeric_values) == 1:
            probability_matrix.loc[dict(post_pop=post_pop, pre_pop=pre_pop)] = next(iter(numeric_values))
            continue

        if not has_numeric and has_string and len(string_values) == 1:
            shared_expression = next(iter(string_values))
            simplified_expression = _simplify_probability_expression(shared_expression)
            conn_names = ", ".join(conn_name for conn_name, _ in records)
            print(
                "Probability expression unresolved for pair:",
                f"{pre_pop}->{post_pop}",
                f"expression={simplified_expression}",
                f"connections={conn_names}",
            )
            if EXPORT_NON_NUMERIC_AS_STR:
                probability_matrix.loc[dict(post_pop=post_pop, pre_pop=pre_pop)] = simplified_expression
            else:
                probability_matrix.loc[dict(post_pop=post_pop, pre_pop=pre_pop)] = np.nan
            continue

        details = ", ".join(f"{conn_name}={probability}" for conn_name, probability in records)
        print(
            "Conflicting probabilities for pair:",
            f"{pre_pop}->{post_pop}",
            details,
        )
        probability_matrix.loc[dict(post_pop=post_pop, pre_pop=pre_pop)] = np.nan

    return probability_matrix


def _round_probability_value(value: object, ndigits: int) -> object:
    numeric_value = _coerce_probability(value)
    if numeric_value is None:
        return value
    if np.isnan(numeric_value):
        return np.nan
    return round(numeric_value, ndigits)


def export_probability_matrix_csv(probability_da: xr.DataArray, path: Path) -> None:
    """Export the xarray matrix to a csv file."""
    df = pd.DataFrame(
        probability_da.values,
        index=probability_da.coords["post_pop"].values,
        columns=probability_da.coords["pre_pop"].values,
    )
    df.index.name = "post_pop"
    df.columns.name = "pre_pop"
    df = df.map(lambda value: _round_probability_value(value, ROUND_DECIMALS))
    df.to_csv(path)


if __name__ == "__main__":
    netparams = load_netparams(INPUT_PATH)
    probability_matrix = build_probability_matrix(netparams)
    export_probability_matrix_csv(probability_matrix, OUTPUT_PATH)
    print(f"Saved probability matrix to {OUTPUT_PATH}")
