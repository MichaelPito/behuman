from memoria.fonti import cdm, dichiarazioni, istituzioni, leggi, stenografici
from memoria.sezioni import dichiarazioni as sez_dich
from memoria.sezioni import governo


PAGINA = """
<div>Seduta n. 730 di martedì 14 ottobre 2025</div>
<p class="titolo">Interrogazioni a risposta immediata.</p>
<p class="sottotitolo">(Iniziative per la natalità – n. 3-01234)</p>
<p class="intervento" id="sed0730.int1"><a href="/deputati?idPersona=111">MARIO ROSSI</a> (FDI). Grazie, Presidente. Il 62 per cento delle famiglie
<em>(Applausi dei deputati del gruppo Fratelli d'Italia)</em> non ce la fa.</p>
<p class="interventoVirtuale">Seconda parte dell'intervento.</p>
<p class="intervento" id="sed0730.int2"><a href="/deputati?idPersona=999">PRESIDENTE</a>. Grazie.</p>
<p class="intervento" id="sed0730.int3"><a href="/deputati?idPersona=111">MARIO ROSSI</a> (FDI). E aggiungo una cosa.</p>
<p class="intervento" id="sed0730.int4"><a href="/deputati?idPersona=222">ANNA BIANCHI</a>, <em>Ministra del lavoro</em>. Rispondo subito.</p>
"""


def test_stenografico_analizza():
    d = stenografici.analizza(PAGINA, 19, 730)
    assert d["data"] == "2025-10-14"
    assert [i["oratore"] for i in d["interventi"]] == ["MARIO ROSSI", "ANNA BIANCHI"]  # stessa persona e argomento: un intervento
    rossi, bianchi = d["interventi"]
    assert rossi["gruppo"] == "FDI" and "Applausi" not in rossi["testo"] and "Seconda parte" in rossi["testo"] and "aggiungo" in rossi["testo"]
    assert rossi["url"].endswith("idSeduta=0730&tipo=stenografico#sed0730.int1")
    assert bianchi["ruolo"] == "Ministra del lavoro" and bianchi["testo"] == "Rispondo subito."


def test_data_dichiarazione_anno_sottinteso():
    assert dichiarazioni.data_dichiarazione("14 ottobre", "2026-10-16") == "2026-10-14"
    assert dichiarazioni.data_dichiarazione("28 dicembre", "2026-01-05") == "2025-12-28"
    assert dichiarazioni.data_dichiarazione("21 luglio 2020", "2021-03-01") == "2020-07-21"
    assert dichiarazioni.data_dichiarazione("ieri", "2021-03-01") is None


def test_tipo_fonte():
    assert dichiarazioni.tipo_fonte("https://www.camera.it/leg19/410?idSeduta=0727") == "Camera"
    assert dichiarazioni.tipo_fonte("https://www.instagram.com/p/x") == "Instagram"
    assert dichiarazioni.tipo_fonte("https://www.corriere.it/x") == "Stampa o altro"
    assert dichiarazioni.tipo_fonte("") == "Non indicata"


def test_abbina_verifica_con_resoconto():
    interventi = [{"leg": 19, "seduta": 727, "testo": "È inverno pieno. Il 62 per cento di italiani e di italiane che non fanno figli e che sono stati intervistati dichiarano che la scelta di non fare figli ha ragioni di carattere economico."}]
    fc = {"fonte_originale": "https://www.camera.it/Leg19/410?idSeduta=0727&tipo=stenografico#:~:text=x",
          "frase": "Il 62 per cento di italiani e di italiane che non fanno figli (...) dichiarano che la scelta di non fare figli ha ragioni di carattere economico"}
    assert dichiarazioni.abbina_verifica(fc, interventi) is interventi[0]
    assert dichiarazioni.abbina_verifica({**fc, "fonte_originale": "https://www.camera.it/leg18/410?idSeduta=0727"}, interventi) is None


def test_estratto_taglia_a_fine_frase():
    t = "Prima frase abbastanza lunga da contare. Seconda frase che supera il limite di lunghezza."
    assert dichiarazioni.estratto(t, 50) == "Prima frase abbastanza lunga da contare. […]"
    assert dichiarazioni.estratto("breve", 50) == "breve"


def test_categoria_intervento():
    assert sez_dich.categoria("Interrogazioni a risposta immediata.") == "Question time"
    assert sez_dich.categoria("Seguito della discussione del disegno di legge: Conversione in legge del decreto-legge") == "Leggi e decreti in esame"
    assert sez_dich.categoria("Discussione della mozione Molinari ed altri n. 1-00569") == "Mozioni"
    assert sez_dich.categoria("Commemorazione") == "Altri argomenti"


def test_riepilogo_dichiarazioni_conta_per_anno():
    camera = [{"data": "2023-05-01", "categoria": "Mozioni", "argomento": "A", "parole": 100},
              {"data": "2023-06-01", "categoria": "Mozioni", "argomento": "A", "parole": 50},
              {"data": "2024-01-01", "categoria": "Question time", "argomento": "B", "parole": 10}]
    r = sez_dich.riepilogo(camera, [], [{"data": "2024-02-02", "interventi": 3}], [{"data": "2024-03-03", "fonte_tipo": "X"}])
    assert r["totale"] == 3 + 3 + 1 and r["parole_camera"] == 160
    assert r["per_anno"] == [{"anno": "2023", "camera": 2, "governo": 0, "senato": 0, "verificate": 0},
                             {"anno": "2024", "camera": 1, "governo": 0, "senato": 3, "verificate": 1}]
    assert r["categorie"][0] == {"categoria": "Mozioni", "n": 2}
    assert r["argomenti_frequenti"] == [{"argomento": "A", "n": 2, "dal": "2023-05-01", "al": "2023-06-01"}]
    assert "giudiz" not in sez_dich.testo_recap("X", r, "2021-01-01")


def test_regex_legge_e_pronunce():
    rx = istituzioni.regex_legge("2024-06-26", 86)
    import re
    assert re.search(rx, "della legge 26 giugno 2024, n. 86 (Disposizioni…)", re.I)
    assert not re.search(rx, "legge 26 giugno 2024, n. 861", re.I)
    elenco = [{"numero_pronuncia": "192", "anno_pronuncia": "2024", "tipologia_pronuncia": "S", "epigrafe": "giudizio sulla legge 26 giugno 2024, n. 86",
               "dispositivo": "per questi motivi LA CORTE COSTITUZIONALE dichiara l'illegittimità costituzionale dell'art. 1", "data_deposito": "2024-12-03"},
              {"numero_pronuncia": "5", "anno_pronuncia": "2024", "tipologia_pronuncia": "O", "epigrafe": "altro", "dispositivo": ""}]
    p = istituzioni.pronunce_su_legge(elenco, "2024-06-26", 86)
    assert len(p) == 1 and p[0]["esito"].startswith("illegittimità") and p[0]["tipo"] == "sentenza"


def test_tipo_legge_e_data_decreto():
    assert leggi.tipo_legge("di conversione di decreto-legge", "Conversione in legge…") == "conversione di decreto-legge"
    assert leggi.tipo_legge("ordinaria", "Ratifica ed esecuzione dell'Accordo") == "ratifica di un accordo internazionale"
    assert leggi.tipo_legge("ordinaria", "Delega al Governo per la riforma fiscale") == "legge con delega al Governo"
    assert leggi.data_decreto("Conversione in legge del decreto-legge 12 dicembre 2022, n. 190") == "2022-12-12"


LEGGE = {
    "id": "L-2023-7", "numero": 7, "data": "2023-01-27", "tipo": "conversione di decreto-legge",
    "titolo": "Conversione in legge, con modificazioni, del decreto-legge 12 dicembre 2022, n. 190, recante disposizioni urgenti in materia di prolungamento delle operazioni di votazione",
    "iniziativa": "Governativa", "del_governo": True, "decreto_legge_del": "2022-12-12",
    "iter": [{"fase": "C.698", "presentato": "2022-12-12"}, {"fase": "S.467", "presentato": "2023-01-17"}],
    "voti": [{"camera": "Camera", "tipo": "fiducia", "data": "2023-01-16", "favorevoli": 200, "contrari": 100, "astenuti": 0},
             {"camera": "Camera", "tipo": "finale", "data": "2023-01-17", "favorevoli": 288, "contrari": 0, "astenuti": 0},
             {"camera": "Senato", "tipo": "finale", "data": "2023-01-24", "favorevoli": 146, "contrari": 1, "astenuti": 0}],
}


def test_in_pratica_solo_dati():
    p = governo.in_pratica(LEGGE)
    assert p["argomento"] == "Disposizioni urgenti in materia di prolungamento delle operazioni di votazione"
    assert "12 dicembre 2022" in p["cosa_e"] and "con modifiche" in p["cosa_e"]
    assert any("46 giorni e 2 letture" in f for f in p["fatti"])
    assert any("questione di fiducia (1 voto, Camera)" in f for f in p["fatti"])
    assert any("Camera: 288 sì, 0 no" in f and "Senato: 146 sì, 1 no" in f for f in p["fatti"])


def test_cdm_abbina_per_titolo_e_data():
    sez = [{"titolo": "Disposizioni urgenti in materia di prolungamento delle operazioni di votazione", "tipo": "decreto-legge", "data": "2022-12-09",
            "testo": "Il Consiglio dei ministri, su proposta del Ministro dell'interno, ha approvato un decreto-legge che prolunga il voto.", "url": "u"},
           {"titolo": "Disposizioni urgenti in materia di prolungamento delle operazioni di votazione", "tipo": "decreto-legge", "data": "2021-01-01", "testo": "vecchio", "url": "v"}]
    m = cdm.abbina([LEGGE], sez)
    assert m["L-2023-7"]["url"] == "u" and m["L-2023-7"]["testo"].startswith("[…] ha approvato")


def test_abbina_verifica_pdf_e_incisi():
    interventi = [{"leg": 18, "seduta": 691, "testo": "Il 62 per cento di chi non fa figli dichiara - pensi un po' - che la scelta ha ragioni economiche e sociali."}]
    fc = {"fonte_originale": "https://documenti.camera.it/leg18/resoconti/assemblea/html/sed0691/stenografico.pdf#page=2",
          "frase": "Il 62 per cento di chi non fa figli dichiara che la scelta ha ragioni economiche"}
    assert dichiarazioni.abbina_verifica(fc, interventi) is interventi[0]
    assert dichiarazioni.abbina_verifica({**fc, "frase": "Frase completamente diversa sulle pensioni minime e sulle accise"}, interventi) is None


def test_sunto_estrattivo_senza_cortesie():
    from memoria.analisi.sunto import sunto, temi
    t = ("Grazie, Presidente. Onorevoli colleghi, oggi discutiamo delle accise sui carburanti. "
         "Le accise sui carburanti pesano sulle famiglie e sulle imprese che usano i carburanti ogni giorno. "
         "Il tempo è bello. "
         "Per questo chiediamo di ridurre le accise sui carburanti di 10 centesimi al litro. "
         "Annuncio il voto favorevole del mio gruppo.")
    s = sunto(t)
    assert "Grazie" not in s and "Annuncio" not in s and "Il tempo è bello" not in s
    assert "ridurre le accise" in s
    assert all(f in t for f in s.split(" […] "))  # solo frasi intere del testo (salvo l'appellativo iniziale)
    assert "Energia e carburanti" in temi(t) and "Fisco e tasse" in temi(t)


def test_richieste_prima_dell_incarico():
    from memoria.sezioni.impegni import carica_temi
    T = {t.id: t for t in carica_temi()}
    acc, red, tasse, sb = T["accise-carburanti"], T["reddito-cittadinanza"], T["tasse"], T["sbarchi"]
    assert acc.richiesta("Chiediamo che le accise siano progressivamente abolite") == ("abolizione", "abolite")
    assert acc.richiesta("[Delle sette accise più antiche] la più vecchia è del 1935. [Abolirle tutte e sette] costerebbe poco")[0] == "abolizione"
    assert acc.richiesta("Noi non abbiamo aumentato le accise, le abbiamo allineate") is None
    assert acc.richiesta("Il provvedimento di riduzione delle accise è stato traslato sul prezzo finale") is None  # descrizione
    assert acc.richiesta("Automatica riduzione di Iva e accise.", programma=True) == ("riduzione", "riduzione")
    assert red.richiesta("Il reddito di cittadinanza è il modo con cui eliminiamo la povertà") is None
    assert red.richiesta("Sarebbe stato più semplice abolire il reddito di cittadinanza") == ("abolizione", "abolire")
    assert tasse.richiesta("Nel 2019 le tasse diminuiranno per il 7 per cento delle imprese") is None
    assert sb.richiesta("Quello che noi proponiamo è un blocco navale") == ("riduzione", "blocco")
    assert sb.richiesta("Il blocco navale è un atto di guerra, dicono") is None


def test_esito_indicatore():
    from memoria.sezioni.impegni import esito_indicatore
    m = lambda ini, oggi: {"variazione_dall_incarico": round(100 * (oggi - ini) / ini, 1), "oggi": {"valore": oggi}}
    assert esito_indicatore("riduzione", m(0.478, 0.673)) == "direzione_opposta"
    assert esito_indicatore("riduzione", m(92938, 37722)) == "direzione_chiesta"
    assert esito_indicatore("riduzione", m(100, 100.5)) == "invariato"
    assert esito_indicatore("abolizione", m(0.7, 0)) == "raggiunto"


def test_frasi_manuali_valide():
    from memoria.sezioni.impegni import carica_temi, frasi_manuali
    m = frasi_manuali(carica_temi())
    meloni = [x for x in m["giorgia-meloni"] if x["tema"] == "accise-carburanti"]
    assert meloni and meloni[0]["direzione"] == "abolizione" and meloni[0]["data"] == "2019-05-06"
    T = {t.id: t for t in carica_temi()}
    assert T["accise-carburanti"].richiesta("Gli aumenti previsti vanno bloccati e le accise esistenti vanno progressivamente abolite.")[0] == "abolizione"


def test_citazioni_nei_titoli():
    from memoria.analisi.affermazioni import citazione
    assert citazione("Nordio: \"Valutiamo di destinare carceri per adulti ai minori\"", "Carlo Nordio") == "Valutiamo di destinare carceri per adulti ai minori"
    assert citazione("Militari a Milano, lezione di Crosetto alla sinistra: “Realtà mistificata: nessun super potere”", "Guido Crosetto").startswith("Realtà mistificata")
    assert citazione("Lo scontro Calenda-Renzi per la telefonata a Putin: \"Mitomane, non c'eri\"", "Matteo Renzi") is None
    assert citazione("Lo scontro Calenda-Renzi per la telefonata a Putin: \"Mitomane, non c'eri\"", "Carlo Calenda") is None
    assert citazione("Fratoianni e Bonelli al presidio: «Stanno criminalizzando chi protesta»", "Angelo Bonelli") is None
    assert citazione("Conte: \"Parole Nordio sui minori non da politico\"", "Carlo Nordio") is None


def test_verifica_affermazione_con_dati():
    from memoria.analisi.affermazioni import carica_regole, verifica_indicatore
    from memoria.sezioni.impegni import carica_temi
    ind = {"sbarchi-12-mesi": {"nome": "Sbarchi", "unita": "persone", "fonte": "UNHCR", "fonte_url": "u", "serie": [("2022-09-28", 92938), ("2026-09-28", 37722)]},
           "accisa-benzina": {"nome": "Accisa benzina", "unita": "€ al litro", "fonte": "MASE", "fonte_url": "u", "serie": [("2022-10-17", 0.478), ("2026-10-19", 0.673)]},
           "accisa-gasolio": {"nome": "Accisa gasolio", "unita": "€ al litro", "fonte": "MASE", "fonte_url": "u", "serie": [("2022-10-17", 0.367), ("2026-10-19", 0.673)]}}
    r, t = carica_regole(), carica_temi()
    assert verifica_indicatore("Abbiamo dimezzato gli sbarchi", r, t, ind, "2022-10-21")["esito"] == "confermata"
    assert verifica_indicatore("Sbarchi in aumento, record di arrivi", r, t, ind, "2022-10-21")["esito"] == "smentita"
    assert verifica_indicatore("Il governo ha aumentato le accise", r, t, ind, "2022-10-21")["esito"] == "confermata"
    assert verifica_indicatore("Non abbiamo mai aumentato le accise", r, t, ind, "2022-10-21")["esito"] == "smentita"
    assert verifica_indicatore("Parliamo di accise domani", r, t, ind, "2022-10-21") is None


def test_verifica_non_scambia_frasi_complesse():
    from memoria.analisi.affermazioni import carica_regole, verifica_indicatore
    from memoria.sezioni.impegni import carica_temi
    ind = {"accisa-benzina": {"nome": "a", "unita": "€ al litro", "fonte": "f", "fonte_url": "u", "serie": [("2022-10-17", 0.478), ("2026-10-19", 0.673)]}}
    frase = "È quello che abbiamo fatto, il taglio delle accise sul carburante, che è stato un modo per impedire che esplodesse l'aumento dei prezzi"
    assert verifica_indicatore(frase, carica_regole(), carica_temi(), ind, "2022-10-21") is None
