from __future__ import annotations

import sys
import types

import pandas as pd


def valid_daily(ts_code: str = "000001.SZ") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": ts_code,
                "trade_date": "20260520",
                "open": 10.0,
                "high": 10.2,
                "low": 9.9,
                "close": 10.1,
                "vol": 1000,
                "amount": 10100,
                "turnover_rate": 0.5,
                "is_paused": 0,
                "is_st": 0,
                "name": "平安银行",
            }
        ]
    )


class FakeDataApi:
    def __init__(self, histories: dict[str, pd.DataFrame]) -> None:
        self.histories = histories
        self.instances: list[types.SimpleNamespace] = []

    def factory(self, token: str = "", timeout: int = 10, http_url: str = ""):
        instance = types.SimpleNamespace(
            token=token,
            timeout=timeout,
            http_url=http_url,
            daily=lambda **kwargs: self.histories[str(kwargs["ts_code"])],
        )
        self.instances.append(instance)
        return instance


def restore_module(name: str, module: object | None) -> None:
    if module is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = module
