from briefkit.forecast.ledger import Ledger, LedgerRow


def make_row(**over):
    base = {
        "ticker": "NVDA",
        "as_of": "2026-11-10",
        "horizon": 5,
        "model": "garch-1-1",
        "last_close": 100.0,
        "annualized_vol": 0.3,
        "horizon_sigma": 0.04,
        "band_low": 95.0,
        "band_high": 105.0,
        "baseline_vol": 0.2,
        "baseline_sigma": 0.03,
        "baseline_band_low": 97.0,
        "baseline_band_high": 103.0,
        "created_at": "2026-11-10T21:00:00",
    }
    base.update(over)
    return LedgerRow(**base)


def test_rows_round_trip_with_every_field(tmp_path):
    ledger = Ledger(str(tmp_path / "sub" / "ledger.sqlite"))
    ledger.record([make_row()])
    [got] = ledger.rows()
    assert got == make_row()


def test_recording_the_same_forecast_twice_keeps_one_row(tmp_path):
    ledger = Ledger(str(tmp_path / "l.sqlite"))
    ledger.record([make_row()])
    ledger.record([make_row(annualized_vol=0.99)])
    rows = ledger.rows()
    assert len(rows) == 1
    assert rows[0].annualized_vol == 0.3


def test_different_model_horizon_or_date_are_separate_rows(tmp_path):
    ledger = Ledger(str(tmp_path / "l.sqlite"))
    ledger.record(
        [
            make_row(),
            make_row(model="baseline-ewma"),
            make_row(horizon=21),
            make_row(as_of="2026-11-11"),
        ]
    )
    assert len(ledger.rows()) == 4


def test_rows_can_be_filtered_by_ticker(tmp_path):
    ledger = Ledger(str(tmp_path / "l.sqlite"))
    ledger.record([make_row(), make_row(ticker="SPY")])
    assert [r.ticker for r in ledger.rows("SPY")] == ["SPY"]
