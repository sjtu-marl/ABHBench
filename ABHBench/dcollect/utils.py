import base64
import math
import os
import pickle
import zlib
from collections.abc import Mapping
from typing import Any

import numpy as np
from statsmodels.stats.power import GofChisquarePower


def _b64u_enc(b: bytes) -> str:
    """Base64URL encode without '=' padding."""
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64u_dec(s: str) -> bytes:
    """Base64URL decode with implicit padding restoration."""
    return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))


def encode_dict_pickle(d: Mapping[Any, Any]) -> str:
    """Encode a (possibly nested) dict via pickle into a compact string."""
    if not isinstance(d, Mapping):
        raise TypeError("Expected a mapping (dict-like).")
    p = pickle.dumps(d, protocol=pickle.HIGHEST_PROTOCOL)
    z = zlib.compress(p, level=9)
    mode, payload = ("Z", z) if len(z) < len(p) else ("P", p)
    return "p1" + mode + _b64u_enc(payload)


def decode_dict_pickle(code: str) -> dict:
    """Decode string produced by encode_dict_pickle().  TRUSTED INPUTS ONLY."""
    if not (isinstance(code, str) and code.startswith("p1") and len(code) >= 3):
        raise ValueError("Invalid code header.")
    mode, payload_b64 = code[2], code[3:]
    data = _b64u_dec(payload_b64)
    if mode == "Z":
        data = zlib.decompress(data)
    elif mode != "P":
        raise ValueError(f"Unknown mode: {mode!r}")
    return pickle.loads(data)


def calculate_n_per_condition(
    n_options: int, effect_w: float, alpha: float, power_tar: float
) -> int:
    """Calculate per-condition sample size using G-L test for contingency tables."""
    n_perms = math.factorial(n_options)
    n_bins = (n_options - 1) * (n_perms - 1) + 1
    n_total = int(
        np.ceil(
            GofChisquarePower().solve_power(
                effect_size=effect_w, n_bins=n_bins, alpha=alpha, power=power_tar
            )
        )
    )
    return int(np.ceil(n_total / n_perms))


def get_n_choices(collect_n: int, n_options: int, config_prefix: str) -> int:
    """Get number of choices, with auto-calculation when collect_n < 1."""
    if collect_n >= 1:
        return collect_n
    effect_w = float(os.environ.get(f"{config_prefix}.effect_w", "0.30"))
    alpha = float(os.environ.get(f"{config_prefix}.alpha", "0.05"))
    power_tar = float(os.environ.get(f"{config_prefix}.power_tar", "0.90"))
    return calculate_n_per_condition(n_options, effect_w, alpha, power_tar)
