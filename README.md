# MasterWork Quality

Applicazione Flask mobile-first per una piccola officina: registrazione avvio/fine lavoro e pezzi, controllo primo pezzo e controlli qualità, anomalie e tabellone titolare.

## Funzioni incluse

- Accesso tramite PIN per operatore o titolare;
- operatore: scelta ordine, avvio, quantità prodotta, primo pezzo, controllo durante la produzione, anomalia e fine lavoro;
- titolare: tabellone lavori, avanzamento, lavori attivi, pezzi giornalieri e anomalie aperte;
- struttura a **Blueprint**: `auth`, `work`, `quality`, `dashboard`;
- database SQLite in locale e PostgreSQL su Railway tramite `DATABASE_URL`;
- base `QualityPlan` pronta per importare in seguito MasterQuality.

## Avvio locale

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python seed.py
flask --app wsgi run --debug
```

Apri `http://127.0.0.1:5000`.

Dati demo: titolare PIN `9999`; operatore Marco PIN `1234`.

## Pubblicazione GitHub e Railway

1. Crea un nuovo repository GitHub vuoto e carica questa cartella:
   ```bash
   git init
   git add .
   git commit -m "Prima versione MasterWork Quality"
   git branch -M main
   git remote add origin URL_DEL_TUO_REPOSITORY
   git push -u origin main
   ```
2. Su Railway: **New Project → Deploy from GitHub Repo** e seleziona il repository.
3. Aggiungi un servizio **PostgreSQL** al progetto.
4. In **Variables** del servizio web imposta:
   - `SECRET_KEY`: una stringa lunga casuale;
   - `DATABASE_URL`: riferimento al database PostgreSQL creato da Railway (di norma viene collegato automaticamente).
5. Railway userà `railway.toml` e avvierà Gunicorn. Dopo il primo deploy esegui il popolamento demo dal terminale del servizio:
   ```bash
   python seed.py
   ```
   In alternativa, crea utenti, ordini e piani attraverso il pannello amministrativo che aggiungeremo nella fase successiva.

## Modulo Manutenzione macchinari (ISO 9001 §7.1.3)

Accessibile solo al titolare da **Manutenzioni** nel menu in alto, o direttamente su `/maintenance/`.

- **Dashboard** (`/maintenance/`): scadenze critiche entro 7 giorni, elenco macchinari, form rapido per aggiungere un macchinario o importare un file Excel;
- **Pipeline** (`/maintenance/pipeline`): tabellone a 3 colonne (Da programmare · In esecuzione · Concluso). Spostando un intervento in "In esecuzione" si indica se avviene in officina o presso un fornitore esterno; concludendolo si registra esito, note e una foto opzionale;
- **Dettaglio macchinario** (`/maintenance/machines/<id>`): piani di manutenzione attivi, registro storico interventi (con foto allegate) e form per aggiungere piani o interventi manuali;
- **Calendario** (`/maintenance/calendar`): scadenzario visuale (FullCalendar), click su un evento per aprire il macchinario;
- **Stampa scheda** (`/maintenance/plans/<id>/print`): scheda intervento stampabile;
- **Import Excel** (`/maintenance/import`): colonne attese `codice, nome_macchina, incaricato, tipologia, frequenza, scadenza, locazione, ditta_esterna` (le ultime due opzionali).

**Comportamento sulla ricorrenza**: quando un intervento viene concluso, il piano resta con stato "concluso" come traccia storica/audit (utile per la stampa scheda), e viene automaticamente creato un nuovo piano con la scadenza ricalcolata (oggi + frequenza) per il ciclo successivo — non si perde mai lo storico e non serve reinserire nulla a mano.

Le foto caricate (foto controllo, foto intervento) vengono salvate in `app/static/uploads/manutenzioni/`. Su Railway questo spazio non è persistente tra deploy: per un uso a lungo termine valuta uno storage esterno (es. Cloudinary, S3) — per ora è sufficiente per l'uso quotidiano.

## Modulo Sicurezza sul lavoro (D.Lgs 81/08)

Accessibile solo al titolare da **Sicurezza** nel menu in alto, o su `/safety/`. Usa la stessa anagrafica operai di MasterWork Quality (tabella `User`, ruolo `operator`).

- **Dashboard** (`/safety/`): formazione e DPI in scadenza nei prossimi 30 giorni, elenco operai;
- **Scheda operaio** (`/safety/workers/<id>`): storico formazione svolta (con attestato allegabile) e DPI consegnati (con ricevuta firmata allegabile), badge di idoneità cantiere calcolato in tempo reale;
- **Catalogo corsi** (`/safety/courses`) e **catalogo DPI** (`/safety/ppe-catalog`): definisci corsi/DPI, la loro validità/scadenza in mesi, e se sono **obbligatori per andare in cantiere**;
- **Cantieri** (`/safety/sites`): anagrafica cantieri (committente, indirizzo, date), assegnazione operai con **verifica automatica di idoneità** (mostra esattamente quale formazione o DPI manca o è scaduto per ciascun operaio assegnato), upload documenti di sicurezza (es. POS — Piano Operativo di Sicurezza).

**Verifica di idoneità**: è calcolata al volo confrontando ogni operaio con l'elenco aggiornato di corsi/DPI marcati come "obbligatori per cantiere" — se aggiungi un nuovo requisito obbligatorio, tutti gli operai vengono ricontrollati automaticamente, anche quelli già assegnati a cantieri esistenti. Non c'è validazione legale del contenuto dei corsi/DPI: la responsabilità di definire cosa è effettivamente obbligatorio per legge (RSPP, formazione ex Accordo Stato-Regioni, categorie DPI art. 74, ecc.) resta del titolare/RSPP — il sistema si limita a tracciare scadenze e a bloccare/segnalare in base a quello che tu stesso configuri nel catalogo.

Anche qui le foto/documenti (attestati, ricevute DPI, POS) vengono salvati in `app/static/uploads/sicurezza/`, non persistente tra deploy Railway — stesso discorso di storage esterno valido per il modulo manutenzione.

## Prima dell’uso reale

- Sostituire il PIN in chiaro con PIN cifrati;
- configurare backup PostgreSQL e una chiave segreta stabile;
- aggiungere gestione utenti, ordini e importazione MasterQuality;
- aggiungere caricamento sicuro di foto e documenti (es. spazio file cloud);
- definire esattamente frequenze e campi dei controlli per ogni articolo.

## Upgrade operativo compliance
SA8000 e ISO 14001 includono registri filtrabili, modifica/eliminazione, evidenze con upload validato, azioni correttive e gestione documenti. I moduli convertiti sono compilati tramite campi testuali strutturati (non più `contenteditable`). ESG segue il wizard cliente → evidenze → KPI → rapporto HTML/revisione/firma. Il limite upload è 16 MB e i nomi sono normalizzati e resi univoci.
