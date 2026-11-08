# Be Human — istruzioni per Claude

> Il progetto è descritto in `docs/` (visione, metodologia, fonti, architettura, roadmap). Questo file raccoglie solo
> le regole di lavoro che valgono per tutti i progetti dell'owner.

## Regole di lavoro
- 🖱️ **Tutto ciò che può fare Claude in Chrome lo fa Claude in Chrome: l'owner riceve un PROMPT, non una lista di clic (2026-11-08, vale per TUTTI i progetti).**
  👤 Testuale: *«Per qualsiasi cosa che claude in browser puo fare dammi sempre un prompt per farglielo fare cosi non faccio io e tu completi meglio tutte le info. Mettilo nel tuo modo di lavorare.»* e *«L'indicazione di utilizzare claude in browser è valida per tutti i progetti»*.
  - Quando un passo richiede il browser dell'owner (un pannello web, una console, un sito dove è già collegato), si scrive un **prompt pronto** in un file del repo, glielo si manda, e gli si chiede di incollarlo in Claude in Chrome e di **incollare qui il resoconto**.
  - Forma del prompt: chi parla e per conto di chi; **regole in testa** (segreti mai mostrati né rigenerati · niente cancellazioni · niente costi o pagamenti · niente invii/pubblicazioni non chiesti · non toccare ciò che non è nel prompt); **passi numerati con il controllo prima della modifica** e cosa fare se il controllo fallisce («fermati e dimmelo»); **resoconto finale** con campi precisi.
  - Restano all'owner solo password, codici, consensi, pagamenti e i gesti che il browser non sa fare (app sul telefono, dispositivi fisici): per quelli una lista breve.
  - ⛔ Nessun valore segreto nel prompt, e Claude in Chrome non deve copiarne in chat.
