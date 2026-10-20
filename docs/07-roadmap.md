# Roadmap

## Fatto (questa versione)
- [x] Pipeline quotidiana: Camera, Senato, Wikidata, Governo (RSS), CHES, programmi 2022
- [x] 24 politici (12 + 12) e 10 partiti, finestra mobile di 5 anni, gestione fine attività
- [x] Indicatori: partecipazione vs mediana, fedeltà al gruppo, cambi di gruppo, incarichi di governo
- [x] 3 proposizioni con 14 votazioni collegate (Camera + Senato) e rilevazione automatica dei cambi
- [x] Sito statico con schede politici/partiti/temi, aggiornamenti, metodo, fonti
- [x] Proposte AI di dichiarazioni con controllo testuale e coda di revisione
- [x] GitHub Actions: aggiornamento quotidiano, test, pubblicazione; moduli di segnalazione

## Fase 1 – Contenuti (nov–dic 2026)
- [ ] Portare i temi a **10–15 proposizioni**, scelte in modo che riguardino entrambi gli schieramenti.
      Candidati (da verificare con `scripts/cerca_votazioni.py`): premierato, cittadinanza, salario minimo
      (attenzione: voto sulla delega, polarità da valutare), MES, superbonus e crediti d'imposta,
      Patto di stabilità, nucleare, Ponte sullo Stretto, flat tax, pensioni (Quota 100/103), immigrazione
      (protocollo Albania), green pass (2021), riforma elettorale 2026, accise sui carburanti.
- [ ] 40+ dichiarazioni verificate, bilanciate per schieramento, a partire dai resoconti stenografici
      (`ocd:intervento` della Camera ha i link allo stenografico).
- [ ] Revisione del metodo da parte di un fact-checker esterno e del comitato di garanzia.
- [ ] Nome definitivo, dominio, identità visiva; immagini di anteprima per la condivisione.

## Fase 2 – Fonti (gen–mar 2027)
- [ ] Parlamento europeo (voti 2021–22 di Tajani e Calenda; eurodeputati dei partiti).
- [ ] Feed Camera (progetti di legge annunciati, resoconti), comunicati del Consiglio dei ministri.
- [ ] Atti presentati (primo firmatario) e interventi in Aula per persona.
- [ ] Accordo con Openpolis per usare le missioni alla Camera (`n_mission`).
- [ ] Programmi 2022 → elenco di promesse verificabili (doppia revisione) e stato di attuazione
      collegato a leggi in Gazzetta Ufficiale (solo "approvata / non approvata", nessuna valutazione).

## Fase 3 – Scala (primavera 2027)
- [ ] Tutti i parlamentari e tutti i ministri (la pipeline è già generica: basta configurarli; servirà
      un archivio SQLite/DuckDB e cache più aggressiva per il Senato).
- [ ] Pagina per collegio elettorale; confronto tra candidati uscenti.
- [ ] Programmi 2027 appena depositati, a confronto con i voti della legislatura.
- [ ] Rapporto trimestrale di equilibrio generato automaticamente.

## Fase 4 – Dopo le elezioni 2027
- [ ] Nuova legislatura, nuovi eletti; i non rieletti restano consultabili fino alla fine della loro attività.
- [ ] Livello regionale (presidenti di Regione) se le fonti lo permettono.

## Rischi tecnici noti
| Rischio | Mitigazione |
|---|---|
| Il firewall del Senato blocca il job di GitHub Actions | Pausa tra richieste, cache lunga per i periodi chiusi, dati del giorno prima mantenuti; se necessario, esecuzione da un server con IP fisso |
| Wikidata limitato a 1 richiesta/minuto | Due query aggregate + ripiego su QLever |
| Cambi di formato delle fonti | Test automatici, errori visibili in `/fonti`, dati precedenti mantenuti |
| Repository troppo grande per i dati giornalieri | I JSON cambiano poco ogni giorno (diff piccoli); se cresce, spostare lo storico in release/archivi |
