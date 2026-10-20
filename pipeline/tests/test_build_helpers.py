from memoria.build import gruppo_corrisponde, nomi_per_feed
from memoria.fonti.ches import misure_partito
from memoria.fonti.senato import trimestri


def test_gruppo_corrisponde_con_intervallo():
    spec = "91@2022-10-13..2023-11-08"
    assert gruppo_corrisponde(spec, "91", "2023-01-10")
    assert not gruppo_corrisponde(spec, "91", "2024-01-10")
    assert not gruppo_corrisponde(spec, "85", "2023-01-10")
    assert gruppo_corrisponde("FDI", "FDI", "2024-01-01")


def test_trimestri_coprono_tutto_il_periodo():
    t = trimestri("2021-10-20", "2022-03-05")
    assert t == [("2021-10-20", "2022-01-01"), ("2022-01-01", "2022-03-06")]


def test_nomi_feed_non_usano_il_solo_cognome():
    nomi = nomi_per_feed("Giuseppe Conte")
    assert "Conte" not in nomi
    assert "Presidente Conte" in nomi and "Giuseppe Conte" in nomi


def test_ches_filtra_paese_partito_anno():
    righe = [
        {"country": "8", "party_id": "844", "year": "2024", "party": "FDI", "lrgen": "8.4666", "galtan": "9.13", "eu_position": "3.27"},
        {"country": "8", "party_id": "844", "year": "2014", "party": "FdI", "lrgen": "9", "galtan": "9", "eu_position": "2"},
        {"country": "3", "party_id": "844", "year": "2024", "party": "X", "lrgen": "1", "galtan": "1", "eu_position": "1"},
    ]
    m = misure_partito(righe, ["844"], {"2019", "2024"})
    assert {x["anno"] for x in m} == {2024}
    assert next(x for x in m if x["chiave"] == "lrgen")["valore"] == 8.47
