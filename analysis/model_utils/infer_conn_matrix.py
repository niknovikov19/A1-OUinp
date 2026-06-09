from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd
import xarray as xr


INPUT_PATH = Path(__file__).resolve().parent / "test_data" / "netParams_00000_seed_1000.json"
OUTPUT_PATH = INPUT_PATH.with_name(f"{INPUT_PATH.stem}_weight_matrix.csv")


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
        weight: object,
        pre_conds: object,
        post_conds: object,
        ) -> None:
    print(
        "Non-pop-only conditions:",
        conn_name,
        f"weight={weight}",
        f"preConds={pre_conds}",
        f"postConds={post_conds}",
    )


def iter_relevant_connections(netparams: dict) -> Iterator[tuple[str, dict, dict, object]]:
    """Yield non-frz connections and report condition shapes beyond pop/ynorm."""
    for conn_name, conn in netparams.get("connParams", {}).items():
        if "frz" in conn_name:
            continue

        pre_conds = conn.get("preConds", {})
        post_conds = conn.get("postConds", {})
        weight = conn.get("weight")

        if not _is_simple_pop_conds(pre_conds) or not _is_simple_pop_conds(post_conds):
            _report_non_pop_only_conn(conn_name, weight, pre_conds, post_conds)

        yield conn_name, pre_conds, post_conds, weight


def build_weight_matrix(netparams: dict) -> xr.DataArray:
    """Build an alphabetical post x pre population weight matrix."""
    pop_names = sorted(
        pop_name for pop_name in netparams.get("popParams", {})
        if "frz" not in pop_name
    )

    weight_matrix = xr.DataArray(
        np.zeros((len(pop_names), len(pop_names)), dtype=float),
        coords={"post_pop": pop_names, "pre_pop": pop_names},
        dims=("post_pop", "pre_pop"),
        name="weight",
    )

    pair_records: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)

    for conn_name, pre_conds, post_conds, weight in iter_relevant_connections(netparams):
        pre_pop = _extract_single_pop(pre_conds)
        post_pop = _extract_single_pop(post_conds)

        if pre_pop is None or post_pop is None:
            print(
                "Skipping unmappable connection:",
                conn_name,
                f"weight={weight}",
                f"preConds={pre_conds}",
                f"postConds={post_conds}",
            )
            continue

        if pre_pop not in weight_matrix.coords["pre_pop"].values:
            print(f"Skipping unknown presynaptic population: {conn_name} pre_pop={pre_pop}")
            continue
        if post_pop not in weight_matrix.coords["post_pop"].values:
            print(f"Skipping unknown postsynaptic population: {conn_name} post_pop={post_pop}")
            continue

        pair_records[(pre_pop, post_pop)].append((conn_name, weight))

    for (pre_pop, post_pop), records in pair_records.items():
        unique_weights = {weight for _, weight in records}
        if len(unique_weights) == 1:
            weight_matrix.loc[dict(post_pop=post_pop, pre_pop=pre_pop)] = next(iter(unique_weights))
            continue

        details = ", ".join(f"{conn_name}={weight}" for conn_name, weight in records)
        print(
            "Conflicting weights for pair:",
            f"{pre_pop}->{post_pop}",
            details,
        )
        weight_matrix.loc[dict(post_pop=post_pop, pre_pop=pre_pop)] = np.nan

    return weight_matrix


def export_weight_matrix_csv(weight_da: xr.DataArray, path: Path) -> None:
    """Export the xarray matrix to a csv file."""
    df = pd.DataFrame(
        weight_da.values,
        index=weight_da.coords["post_pop"].values,
        columns=weight_da.coords["pre_pop"].values,
    )
    df.index.name = "post_pop"
    df.columns.name = "pre_pop"
    df.to_csv(path)


if __name__ == "__main__":
    netparams = load_netparams(INPUT_PATH)
    weight_matrix = build_weight_matrix(netparams)
    export_weight_matrix_csv(weight_matrix, OUTPUT_PATH)
    print(f"Saved weight matrix to {OUTPUT_PATH}")
