from memoria.analisi.metriche import fedelta_gruppo, mediana_presenze, presenza
from memoria.fonti.camera import (
    _data,
    aggrega_mensile,
    maggioranza_gruppo,
    numero_atto,
    pulisci_gruppo,
    pulisci_titolo,
)
from memoria.fonti.feed import analizza, menziona


def test_data():
    assert _data("20230124") == "2023-01-24"
    assert _data(None) is None


def test_numero_atto():
    assert numero_atto("DDL 2789-A E ABB - VOTO FINALE") == "2789"
    assert numero_atto("PDL 2822-B - VOTO FINALE") == "2822"


def test_pulizia_testi():
    assert pulisci_titolo(' "Riconoscimento e tutela" (2789) ') == "Riconoscimento e tutela"
    assert pulisci_titolo("dell&amp;#39;Ucraina") == "dell'Ucraina"
    assert pulisci_gruppo("MOVIMENTO 5 STELLE (M5S) (18.10.2022") == "MOVIMENTO 5 STELLE (M5S)"


def test_maggioranza_gruppo():
    assert maggioranza_gruppo({"Contrario": 50, "Non ha votato": 18}) == "Contrario"
    assert maggioranza_gruppo({"Ha votato": 68}) is None


def test_aggrega_mensile_e_presenza():
    rows = [
        {"mese": "202301", "tipo": "Favorevole", "n": "10"},
        {"mese": "202301", "tipo": "Non ha votato", "n": "30"},
        {"mese": "202302", "tipo": "Ha votato", "n": "5"},
    ]
    m = aggrega_mensile(rows, camera="Camera", leg=19)
    assert [x["mese"] for x in m] == ["2023-01", "2023-02"]
    assert m[0]["presenti"] == 10 and m[0]["totale"] == 40
    assert presenza(m) == {"presenti": 15, "totale": 45, "percentuale": 33.3}


def test_mediana_ignora_chi_ha_poche_votazioni():
    tutti = {"a": {"presenti": 50, "totale": 100}, "b": {"presenti": 90, "totale": 100}, "c": {"presenti": 1, "totale": 2}}
    assert mediana_presenze(tutti) == 70.0


def test_fedelta():
    voti = [
        {"id": "1", "voto": "Favorevole", "linea_gruppo": "Favorevole"},
        {"id": "2", "voto": "Contrario", "linea_gruppo": "Favorevole"},
        {"id": "3", "voto": "Non ha votato", "linea_gruppo": "Favorevole"},
        {"id": "4", "voto": "Favorevole", "linea_gruppo": None},
    ]
    f = fedelta_gruppo(voti)
    assert f["allineati"] == 1 and f["difformi"] == 1 and f["voti_difformi"] == ["2"]


def test_feed():
    xml = b"""<rss><channel><item><title>Il Presidente Meloni a Bruxelles</title><link>https://x/1</link>
    <pubDate>Fri, 16 Oct 2026 10:00:00 +0200</pubDate><description>&lt;p&gt;Testo&lt;/p&gt;</description></item></channel></rss>"""
    items = analizza(xml)
    assert items == [{"titolo": "Il Presidente Meloni a Bruxelles", "url": "https://x/1", "data": "2026-10-16", "sommario": "Testo"}]
    assert menziona(items[0], ["Meloni"])
    assert not menziona(items[0], ["Melo"])
