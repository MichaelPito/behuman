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
  attivo: boolean;
  indicatori: Indicatori;
  coerenza: Coerenza;
};

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
export const partiti = () => leggi<{ slug: string; nome: string; sigla: string; schieramento: string; attivo: boolean; coerenza: Coerenza }[]>("partiti.json", []);
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
