from memoria.revisione.estrai import citazione_presente


def test_citazione_presente_tollera_virgolette_e_spazi():
    testo = "Il ministro ha dichiarato: «Non aumenteremo le   tasse sulla casa», poi ha lasciato la sala."
    assert citazione_presente('"Non aumenteremo le tasse sulla casa"', testo)


def test_citazione_inventata_scartata():
    testo = "Il ministro ha dichiarato: «Non aumenteremo le tasse sulla casa»."
    assert not citazione_presente("Ridurremo le tasse sulla casa", testo)


def test_citazione_troppo_corta_scartata():
    assert not citazione_presente("tasse", "tasse tasse tasse")
