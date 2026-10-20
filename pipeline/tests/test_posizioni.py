from memoria.analisi.posizioni import (
    Posizione,
    linea_da_conteggi,
    posizione_da_voto,
    riepilogo_coerenza,
    rileva_cambi,
)


def P(data, pos, prop="x", tipo="voto"):
    return Posizione(proposizione=prop, data=data, posizione=pos, tipo=tipo, descrizione="")


def test_nessun_cambio_se_coerente():
    assert rileva_cambi([P("2022-01-01", "a_favore"), P("2023-01-01", "a_favore")]) == []


def test_cambio_semplice():
    cambi = rileva_cambi([P("2023-01-01", "contro"), P("2022-01-01", "a_favore")])
    assert len(cambi) == 1
    assert cambi[0]["prima"]["data"] == "2022-01-01"
    assert cambi[0]["dopo"]["posizione"] == "contro"


def test_astensione_non_genera_cambio_ma_non_interrompe_il_confronto():
    cambi = rileva_cambi([P("2022-01-01", "a_favore"), P("2022-06-01", "astensione"), P("2023-01-01", "contro")])
    assert len(cambi) == 1
    assert cambi[0]["prima"]["data"] == "2022-01-01"


def test_andata_e_ritorno_sono_due_cambi():
    cambi = rileva_cambi([P("2021-01-01", "a_favore"), P("2022-01-01", "contro"), P("2023-01-01", "a_favore")])
    assert len(cambi) == 2


def test_proposizioni_separate():
    cambi = rileva_cambi([P("2021-01-01", "a_favore", "a"), P("2022-01-01", "contro", "b")])
    assert cambi == []


def test_polarita_inversa():
    assert posizione_da_voto("Favorevole") == "a_favore"
    assert posizione_da_voto("Favorevole", "inversa") == "contro"
    assert posizione_da_voto("Astensione", "inversa") == "astensione"
    assert posizione_da_voto("Non ha votato") is None


def test_linea_gruppo():
    assert linea_da_conteggi({"Favorevole": 102, "Contrario": 2, "Non ha votato": 49}) == "a_favore"
    assert linea_da_conteggi({"Non ha votato": 10}) is None
    assert linea_da_conteggi({"Favorevole": 3, "Contrario": 3}) is None


def test_riepilogo():
    pos = [P("2021-01-01", "a_favore", "a"), P("2022-01-01", "contro", "a"), P("2022-01-01", "contro", "b")]
    r = riepilogo_coerenza(pos, rileva_cambi(pos))
    assert r == {
        "proposizioni_con_posizioni": 2,
        "proposizioni_confrontabili": 1,
        "proposizioni_con_cambi": 1,
        "cambi_totali": 1,
    }
