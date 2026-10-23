// Lettura dei JSON prodotti dalla pipeline (cartella /data alla radice del repo).
import fs from "node:fs";
import path from "node:path";

const DATA_DIR = process.env.DATA_DIR || path.resolve(process.cwd(), "..", "data");

function leggi<T>(rel: string, fallback: T): T {
  const p = path.join(DATA_DIR, rel);
  if (!fs.existsSync(p)) return fallback;
  return JSON.parse(fs.readFileSync(p, "utf-8")) as T;
}

export type Posizione = {
  proposizione: string;
  data: string;
  posizione: "a_favore" | "contro" | "astensione";
  tipo: "voto" | "voto_gruppo" | "dichiarazione" | "programma";
  descrizione: string;
  fonte_url?: string;
  citazione?: string;
  dettagli?: Record<string, any>;
};

export type Cambio = { proposizione: string; prima: Posizione; dopo: Posizione };

export type Indicatori = Record<
  string,
  {
    presenza: { presenti: number; totale: number; percentuale: number | null };
    fedelta_gruppo: { allineati: number; difformi: number; percentuale_allineati: number | null; voti_difformi: string[] };
    voti_finali_e_fiducia: number;
  }
>;

export type Coerenza = {
  proposizioni_con_posizioni: number;
  proposizioni_confrontabili: number;
  proposizioni_con_cambi: number;
  cambi_totali: number;
};

export type PoliticoBreve = {
  slug: string;
  nome: string;
  ruolo: string;
  schieramento: "governo" | "opposizione" | "altro";
  partito: { slug: string | null; nome: string; sigla: string };
  foto?: string | null;
  sesso?: "F" | "M" | null;
  orientamento?: "sinistra" | "centro" | "destra" | null;
  valutazione_coerenza?: ValutazioneCoerenza;
  attivo: boolean;
  indicatori: Indicatori;
  coerenza: Coerenza;
};

export type ValutazioneCoerenza = {
  stato: "dati_insufficienti" | "nessun_cambio" | "con_cambi";
  temi_confrontabili: number;
  temi_senza_cambi: number;
  temi_con_cambi?: number;
  testo: string;
};

export type Orientamento = { etichetta: "sinistra" | "centro" | "destra" | null; valore?: number; anno?: number; componenti?: number; fonte?: string; nota?: string };

export type VotoFinale = {
  id: string;
  camera: string;
  legislatura: number;
  data: string;
  descrizione: string;
  atto: string | null;
  titolo: string | null;
  fiducia: boolean;
  approvato: boolean;
  voto: string;
  gruppo: string | null;
  linea_gruppo: string | null;
  url: string | null;
};

export type Politico = PoliticoBreve & {
  attivo_fino: string | null;
  periodo: { dal: string; al: string };
  anagrafica: Record<string, string | null>;
  cariche: { carica: string; di?: string; gruppo?: string; inizio: string | null; fine: string | null; fonte: string; fonte_nome?: string; motivo_fine?: string | null }[];
  partiti_storico: { partito: string; wikidata: string; inizio: string | null; fine: string | null }[];
  parlamento: Record<
    string,
    {
      presenze_mensili: { mese: string; presenti: number; assenti: number; totale: number; legislatura: number }[];
      voti_finali: VotoFinale[];
      gruppi: { gruppo: string; legislatura: number; inizio: string | null; fine: string | null }[];
      scheda_ufficiale?: string;
    }
  >;
  posizioni: Posizione[];
  cambi_posizione: Cambio[];
  note?: string | null;
  aggiornato_il: string;
  sintesi?: string[];
  orientamento?: Orientamento;
};

export type Partito = {
  slug: string;
  nome: string;
  sigla: string;
  schieramento: string;
  sito?: string | null;
  wikidata: string;
  periodo: { dal: string; al: string };
  attivo: boolean;
  gruppi_parlamentari: Record<string, string[]>;
  membri_monitorati: { slug: string; nome: string; ruolo: string }[];
  coalizioni: { governo: string; inizio: string; fine: string | null; ruolo: string; nota?: string; fonte?: string }[];
  ideologia: Record<string, any>;
  posizioni: Posizione[];
  cambi_posizione: Cambio[];
  coerenza: Coerenza;
  valutazione_coerenza?: ValutazioneCoerenza;
  orientamento?: Orientamento;
  sintesi?: string[];
  note?: string | null;
};

export type Tema = {
  id: string;
  nome: string;
  descrizione?: string;
  proposizioni: {
    id: string;
    testo: string;
    contesto?: string;
    voti: { id: string; camera: string; data: string | null; titolo: string | null; url: string | null; polarita: string; nota?: string }[];
    soggetti: { slug: string; nome: string; tipo: "partito" | "politico"; posizioni: Posizione[]; cambi: number }[];
  }[];
};

export type Aggiornamento = {
  titolo: string;
  url: string;
  data: string | null;
  sommario: string;
  fonte: string;
  politici: string[];
};

export const meta = () =>
  leggi<{ aggiornato_il: string; finestra: { dal: string; al: string; anni: number }; fonti: any[]; fonti_ok: Record<string, string>; errori: any[] }>(
    "meta.json",
    { aggiornato_il: "", finestra: { dal: "", al: "", anni: 5 }, fonti: [], fonti_ok: {}, errori: [] },
  );
export const politici = () => leggi<PoliticoBreve[]>("politici.json", []);
export const politico = (slug: string) => leggi<Politico>(`politici/${slug}.json`, null as any);
export const partiti = () =>
  leggi<{ slug: string; nome: string; sigla: string; schieramento: string; attivo: boolean; coerenza: Coerenza; orientamento?: Orientamento }[]>("partiti.json", []);
export const partito = (slug: string) => leggi<Partito>(`partiti/${slug}.json`, null as any);
export const temi = () => leggi<Tema[]>("temi.json", []);
export const aggiornamenti = () => leggi<Aggiornamento[]>("aggiornamenti.json", []);
export const mediane = () => leggi<Record<string, number | null>>("mediane.json", {});

export const proposizioniIndice = () => {
  const out: Record<string, { testo: string; tema: string; temaNome: string }> = {};
  for (const t of temi()) for (const p of t.proposizioni) out[p.id] = { testo: p.testo, tema: t.id, temaNome: t.nome };
  return out;
};

// ----------------------------------------------------------------- formattazione
const MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
export function dataIt(d?: string | null): string {
  if (!d) return "—";
  const [y, m, g] = d.split("-");
  if (!g) return `${MESI[Number(m) - 1]} ${y}`;
  return `${Number(g)} ${MESI[Number(m) - 1]} ${y}`;
}

export const ETICHETTA_POSIZIONE: Record<string, string> = {
  a_favore: "A favore",
  contro: "Contro",
  astensione: "Astensione",
};
export const SIMBOLO_POSIZIONE: Record<string, string> = { a_favore: "▲", contro: "▼", astensione: "●" };
export const ETICHETTA_TIPO: Record<string, string> = {
  voto: "Voto personale",
  voto_gruppo: "Voto del gruppo parlamentare",
  dichiarazione: "Dichiarazione",
  programma: "Programma elettorale",
};
export const pct = (n: number | null | undefined) => (n == null ? "—" : `${n.toLocaleString("it-IT")}%`);

// Ordinamento per cognome (ultima parola del nome), come negli elenchi istituzionali.
export const perCognome = (a: { nome: string }, b: { nome: string }) => {
  const c = (n: string) => n.split(" ").slice(-1)[0] + " " + n;
  return c(a.nome).localeCompare(c(b.nome), "it");
};

export const ETICHETTA_ORIENTAMENTO: Record<string, string> = { sinistra: "Sinistra", centro: "Centro", destra: "Destra" };
export const iniziali = (nome: string) => nome.split(" ").map((s) => s[0]).slice(0, 2).join("");
export const ordinaPerData = <T extends { data?: string | null }>(xs: T[]) => [...xs].sort((a, b) => (a.data ?? "").localeCompare(b.data ?? ""));

// Ultimo voto finale (non di fiducia) registrato nelle schede: serve per l'emiciclo della home.
export function ultimoVotoFinale(camera = "Camera"): (VotoFinale & { esito?: { favorevoli: number; contrari: number; astenuti: number } }) | null {
  let migliore: any = null;
  for (const p of politici()) {
    const s = politico(p.slug);
    for (const v of s?.parlamento?.[camera]?.voti_finali ?? []) {
      if (v.fiducia || !(v as any).esito) continue;
      if (!migliore || v.data > migliore.data || (v.data === migliore.data && v.id > migliore.id)) migliore = v;
    }
  }
  return migliore;
}

// Tutti i cambi di posizione (politici e partiti), dal più recente.
export function tuttiICambi() {
  const out: { soggetto: string; slug: string; tipo: "politico" | "partito"; c: Cambio }[] = [];
  for (const p of politici()) for (const c of politico(p.slug)?.cambi_posizione ?? []) out.push({ soggetto: p.nome, slug: p.slug, tipo: "politico", c });
  for (const p of partiti()) for (const c of partito(p.slug)?.cambi_posizione ?? []) out.push({ soggetto: p.nome, slug: p.slug, tipo: "partito", c });
  return out.sort((a, b) => b.c.dopo.data.localeCompare(a.c.dopo.data));
}

export type VotazioneTema = { id: string; camera: string; data: string; titolo: string; url?: string; gruppi: Record<string, Record<string, number>>; nomi_gruppi?: Record<string, string> };
export const votazioniTemi = () => leggi<Record<string, VotazioneTema>>("votazioni_temi.json", {});
export function totaliVotazione(v?: VotazioneTema) {
  const t = { favorevoli: 0, contrari: 0, astenuti: 0 };
  for (const g of Object.values(v?.gruppi ?? {})) {
    t.favorevoli += (g["Favorevole"] ?? 0);
    t.contrari += (g["Contrario"] ?? 0);
    t.astenuti += (g["Astensione"] ?? 0);
  }
  return t;
}

// ----------------------------------------------------------------- governo
export type Voto = { camera: string; fase: string; data: string; tipo: "finale" | "fiducia"; favorevoli: number; contrari: number; astenuti: number; fonte: string };
export type Fase = { fase: string; ramo: string; presentato: string; stato: string; data_stato: string; url: string | null };
export type Pronuncia = { numero: number; anno: number; tipo: string; data_deposito: string | null; ecli: string | null; esito: string; dispositivo: string; url: string };
export type Raccolta = { id: string; titolo: string; quesito: string; firme_online: number | null; soglia: number | null; inizio: string | null; fine: string | null; url: string };
export type Referendum = {
  id: string; nome: string; tipo: string; data: string; giorni?: string; id_ddl?: string; legge?: string; fonte?: string;
  risultato: { si: number; no: number; votanti: number; elettori: number; perc_si: number; perc_no: number; affluenza: number | null } | null;
};
export type Legge = {
  id: string; numero: number; data: string; tipo: string; titolo: string; titolo_breve: string | null; iniziativa: string | null;
  presentata_da: string[]; del_governo: boolean; decreto_legge_del: string | null; gazzetta: string | null; normattiva: string | null;
  iter: Fase[]; voti: Voto[]; scheda_senato: string;
  in_pratica: { argomento: string; cosa_e: string; fatti: string[] };
  descrizione_governo: { testo: string; titolo: string; data: string | null; url: string; somiglianza?: number } | null;
  reazioni: { corte: Pronuncia[]; firme: Raccolta[]; referendum: Referendum[] };
};
export type Riforma = {
  id_ddl: string; titolo: string; iter: Fase[]; voti: Voto[]; stato: string; data_stato: string; esito: string;
  approvata_definitivamente: boolean; pubblicata_come_legge: boolean; scheda_senato: string | null; referendum: Referendum[];
};
export type Governo = {
  governo: { nome: string | null; inizio: string; fonte: string | null };
  statistiche: {
    leggi: number; del_governo: number; decreti_convertiti: number; con_fiducia: number; voti_fiducia: number; con_descrizione_governo: number; con_pronunce_corte: number;
    per_anno: { anno: string; leggi: number; del_governo: number; decreti: number; con_fiducia: number }[];
    per_tipo: { tipo: string; n: number }[];
  };
  riforme: Riforma[];
  referendum: Referendum[];
  leggi: Legge[];
};
export const governo = () => leggi<Governo | null>("governo.json", null);
export const slugLegge = (l: { id: string }) => l.id.toLowerCase();
export const numeroLegge = (l: Legge) => `${l.tipo === "legge costituzionale" ? "Legge costituzionale" : "Legge"} ${dataIt(l.data)}, n. ${l.numero}`;

// ----------------------------------------------------------------- dichiarazioni
export type InterventoCamera = {
  data: string; leg: number; seduta: number; argomento: string; fase: string | null; categoria: string; ruolo: string | null; gruppo: string | null;
  estratto: string; parole: number; url: string; verificata?: string;
};
export type InterventoGoverno = { data: string; titolo: string; estratto: string; parole: number; url: string; fonte: string };
export type InterventoSenato = { id: string; data: string; seduta: number; interventi: number; ddl: { fase: string; titolo: string; url: string }[] };
export type Verificata = {
  data: string | null; data_verifica: string; frase: string; url: string; fonte_originale: string | null; fonte_tipo: string;
  testo_ufficiale?: { estratto: string; url: string };
};
export type RiepilogoDichiarazioni = {
  totale: number; camera: number; parole_camera: number; governo: number; senato: number; verificate: number; prima: string | null; ultima: string | null;
  per_anno: { anno: string; camera: number; governo: number; senato: number; verificate: number }[];
  categorie: { categoria: string; n: number }[];
  argomenti_frequenti: { argomento: string; n: number; dal: string; al: string }[];
  fonti_verificate: { fonte: string; n: number }[];
};
export type Dichiarazioni = {
  slug: string; nome: string; partito: { slug: string | null; nome: string; sigla: string }; schieramento: string; dal: string; al: string;
  riepilogo: RiepilogoDichiarazioni; recap: string; valutazione_coerenza?: ValutazioneCoerenza; coerenza?: Coerenza;
  verificate: Verificata[]; camera: InterventoCamera[]; governo: InterventoGoverno[]; senato: InterventoSenato[];
};
export type IndiceDichiarazioni = {
  politici: { slug: string; nome: string; partito: Dichiarazioni["partito"]; schieramento: string; riepilogo: Pick<RiepilogoDichiarazioni, "totale" | "camera" | "senato" | "governo" | "verificate" | "prima" | "ultima">; recap: string; valutazione_coerenza?: ValutazioneCoerenza }[];
  discusse: (Verificata & { slug: string; nome: string; partito: Dichiarazioni["partito"]; schieramento: string })[];
  recenti: { slug: string; nome: string; partito: Dichiarazioni["partito"]; schieramento: string; fonte: string; data: string; testo: string; contesto: string; url: string }[];
};
export const dichiarazioni = (slug: string) => leggi<Dichiarazioni | null>(`dichiarazioni/${slug}.json`, null);
export const indiceDichiarazioni = () => leggi<IndiceDichiarazioni>("dichiarazioni.json", { politici: [], discusse: [], recenti: [] });

// Stati dell'iter come li scrive il Senato, in parole intere.
const STATI: Record<string, string> = {
  "approvato": "approvato",
  "approvato con modificazioni": "approvato con modifiche",
  "esame in comm.": "in esame in commissione",
  "da assegnare": "da assegnare a una commissione",
  "assegnato": "assegnato a una commissione",
  "in corso di esame in commissione": "in esame in commissione",
  "appr. def. non pubbl": "approvazione definitiva, non pubblicata come legge",
  "appr. definit. Legge": "approvazione definitiva: è legge",
  "in corso di esame in assemblea": "in esame in Aula",
};
export const statoIter = (s: string) => STATI[s] ?? STATI[s.trim()] ?? s;

// ----------------------------------------------------------------- promesse prima/dopo l'incarico
export type FraseImpegno = { tema: string; data: string; fonte: string; frase: string; url: string; verifica?: string; sezione?: string; metodo?: string; direzione: string | null; verbo: string | null };
export type MisuraImpegno = {
  id: string; nome: string; unita: string; fonte: string; fonte_url: string; frequenza: string;
  alla_prima_richiesta: { data: string; valore: number } | null; all_incarico: { data: string; valore: number };
  un_anno_prima: { data: string; valore: number } | null; oggi: { data: string; valore: number };
  variazione_dall_incarico: number | null; variazione_dalla_prima_richiesta: number | null; serie: [string, number][]; esito: string;
};
export type TemaImpegno = {
  tema: string; nome: string; direzione_chiesta: string; prima: FraseImpegno[]; prima_totale: number; programma: FraseImpegno[]; programma_totale: number;
  dopo: FraseImpegno[]; dopo_totale: number; indicatori: MisuraImpegno[]; leggi: { id: string; data: string; numero: number; argomento: string; tipo: string }[];
  esito: string; esito_etichetta: string; testo: string; richieste_per_tipo: Record<string, number>;
};
export type ImpegniPolitico = {
  slug: string; nome: string; incarico: { carica: string; dal: string }; temi: TemaImpegno[];
  riepilogo: { temi: number; raggiunto: number; direzione_chiesta: number; invariato: number; direzione_opposta: number; misto: number; senza_indicatore: number; testo: string };
};
export const impegni = () =>
  leggi<{ politici: Record<string, ImpegniPolitico>; temi: { id: string; nome: string }[]; programmi: Record<string, FraseImpegno[]> }>("impegni.json", { politici: {}, temi: [], programmi: {} });
export const ESITO_CLASSE: Record<string, string> = {
  raggiunto: "accent", direzione_chiesta: "accent", invariato: "sky", direzione_opposta: "plum", misto: "sun", senza_indicatore: "",
};
