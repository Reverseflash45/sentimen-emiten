import math

import pytest

from app.analitik.statistik import (
    geser,
    imbal_hasil_harian,
    pearson,
    spearman,
)


def test_pearson_hubungan_positif_sempurna():
    assert pearson([1, 2, 3, 4], [2, 4, 6, 8]).koefisien == pytest.approx(1.0)


def test_pearson_hubungan_negatif_sempurna():
    assert pearson([1, 2, 3, 4], [8, 6, 4, 2]).koefisien == pytest.approx(-1.0)


def test_pearson_nilai_diketahui():
    # dihitung manual: r = 12 / sqrt(10 * 19.2) = 12 / sqrt(192) = 0.86603
    r = pearson([1, 2, 3, 4, 5], [2, 4, 5, 4, 8]).koefisien
    assert r == pytest.approx(12 / math.sqrt(192), abs=1e-6)


def test_pearson_deret_konstan_menghasilkan_nol():
    assert pearson([5, 5, 5, 5], [1, 2, 3, 4]).koefisien == 0.0


def test_pearson_menolak_data_terlalu_sedikit():
    with pytest.raises(ValueError):
        pearson([1, 2], [3, 4])


def test_pearson_menolak_panjang_berbeda():
    with pytest.raises(ValueError):
        pearson([1, 2, 3], [1, 2])


def test_spearman_tahan_terhadap_pencilan():
    """Hubungan monoton sempurna, tapi satu nilai melonjak jauh."""
    x = [1, 2, 3, 4, 5]
    y = [1, 2, 3, 4, 1000]
    assert spearman(x, y).koefisien == pytest.approx(1.0)
    assert pearson(x, y).koefisien < 0.9  # Pearson tertarik pencilan


def test_spearman_menangani_nilai_kembar():
    hasil = spearman([1, 2, 2, 3], [1, 2, 2, 3])
    assert hasil.koefisien == pytest.approx(1.0)


def test_imbal_hasil_harian():
    hasil = imbal_hasil_harian([100.0, 110.0, 99.0])
    assert hasil[0] == pytest.approx(0.10)
    assert hasil[1] == pytest.approx(-0.10)
    assert len(hasil) == 2


def test_imbal_hasil_harga_nol_tidak_membuat_error():
    assert imbal_hasil_harian([0.0, 50.0]) == [0.0]


def test_geser_maju_dan_mundur():
    assert geser([1, 2, 3, 4], 1) == [1, 2, 3]
    assert geser([1, 2, 3, 4], -1) == [2, 3, 4]
    assert geser([1, 2, 3, 4], 0) == [1, 2, 3, 4]


def test_kekuatan_dideskripsikan():
    assert pearson([1, 2, 3, 4], [2, 4, 6, 8]).kekuatan() == "sangat kuat"
    assert pearson([5, 5, 5, 5], [1, 2, 3, 4]).kekuatan() == "sangat lemah"
