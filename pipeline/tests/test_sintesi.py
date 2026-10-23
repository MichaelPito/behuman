from memoria.analisi.sintesi import orientamento, orientamento_partito, sintesi_politico, valutazione_coerenza


def test_orientamento_fasce():
    assert orientamento(2.9) == "sinistra"
    assert orientamento(4.43) == "centro"
    assert orientamento(6.0) == "centro"
    assert orientamento(6.73) == "destra"
    assert orientamento(None) is None


def test_orientamento_partito_usa_ultima_ondata_e_media_componenti():
    misure = [
        {"chiave": "lrgen", "anno": 2019, "valore": 9.0, "fonte": "CHES"},
        {"chiave": "lrgen", "anno": 2024, "valore": 1.23, "fonte": "CHES"},
        {"chiave": "lrgen", "anno": 2024, "valore": 2.14, "fonte": "CHES"},
        {"chiave": "galtan", "anno": 2024, "valore": 5.0},
    ]
    o = orientamento_partito(misure)
    assert o["anno"] == 2024 and o["componenti"] == 2 and o["etichetta"] == "sinistra" and o["valore"] == 1.69
    assert orientamento_partito([])["etichetta"] is None


def test_valutazione_coerenza():
    assert valutazione_coerenza({"proposizioni_confrontabili": 0})["stato"] == "dati_insufficienti"
    v = valutazione_coerenza({"proposizioni_confrontabili": 3, "proposizioni_con_cambi": 1})
    assert v["stato"] == "con_cambi" and v["temi_senza_cambi"] == 2


def test_sintesi_usa_solo_numeri_della_scheda():
    p = {
        "nome": "Mario Rossi",
        "cariche": [],
        "indicatori": {"Camera": {"presenza": {"percentuale": 50.0, "presenti": 10, "totale": 20},
                                   "fedelta_gruppo": {"percentuale_allineati": 90.0, "allineati": 9, "difformi": 1}}},
        "parlamento": {"Camera": {"presenze_mensili": [], "gruppi": []}},
        "coerenza": {"proposizioni_confrontabili": 1, "proposizioni_con_cambi": 1},
        "cambi_posizione": [{"proposizione": "x", "prima": {"posizione": "a_favore", "data": "2022-03-17"},
                             "dopo": {"posizione": "contro", "data": "2023-01-24"}}],
    }
    s = " ".join(sintesi_politico(p, {"Camera": 72.5}, {"x": {"testo": "Fare X"}}))
    assert "50,0%" in s and "72,5%" in s and "9 volte su 10" in s
    assert "«Fare X»: a favore il 17 marzo 2022, contro il 24 gennaio 2023" in s
