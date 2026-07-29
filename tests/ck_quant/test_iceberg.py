from random import Random

from freqtrade.ck_quant.iceberg import IcebergSettings


def test_iceberg_disabled_by_default():
    settings = IcebergSettings.from_config({})

    assert settings.enabled is False
    assert settings.entry is True
    assert settings.exit is True


def test_iceberg_slice_respects_ratio_and_remainder():
    settings = IcebergSettings(enabled=True, visible_ratio=0.1, max_slices=20)

    assert settings.slice_stake(1000, 1000) == 100
    assert settings.slice_stake(55, 1000) == 55


def test_iceberg_max_slices_sets_minimum_child():
    settings = IcebergSettings(enabled=True, visible_ratio=0.01, max_slices=5)

    assert settings.slice_stake(1000, 1000) == 200


def test_iceberg_minimum_stake_and_jitter():
    settings = IcebergSettings(
        enabled=True,
        visible_ratio=0.1,
        max_slices=10,
        min_slice_stake=150,
        size_jitter=0.2,
    )

    child = settings.slice_stake(1000, 1000, rng=Random(1))

    assert 150 <= child <= 180

