# Registro dei rilasci

## V2.2.0 — 21 novembre 2026

- Aggiunta la sezione **Suggerimenti** su Mac e Windows. Il modulo salva la proposta sul computer, la accoda per il repository privato e mostra la ricevuta con il collegamento all’issue.
- Le installazioni degli utenti usano il loro accesso GitHub CLI. Il Mac configurato per lo sviluppo può inoltrare la propria coda tramite il connettore GitHub di Codex. Un invio con esito incerto viene dapprima cercato su GitHub.
- Il proprietario autorizza una proposta specifica pubblicando il comando dell’issue in un nuovo commento. Il controllo verifica l’identità GitHub e l’impronta del testo. Un commento di revoca o la chiusura dell’issue ferma il lavoro successivo. Le modifiche approvate passano per una pull request da rivedere.
- Backup V2.1.1 in `../backup/ClipLab-V2.1.1`. Le prove includono salvataggio, riavvio, gestione di invii incerti, autorizzazioni e revoca. I test delle varianti Windows sono eseguiti su Mac.

## V2.1.1 — 20 novembre 2026

- Corretti i dati simulati dei test di proprietà del motore: includono ora la cartella dati effettiva. Il controllo dell’app continua a distinguere installazioni con cartelle dati diverse.
- Eliminato il redirect delle versioni precedenti verso la porta fissa 8768. La vecchia interfaccia indica di riaprire il comando di avvio appropriato per Mac o Windows: il launcher individua l’istanza corretta e apre il relativo indirizzo, anche sulle altre porte disponibili. Non viene tentata una ricerca tra server di altre installazioni dal browser.
- Se un sottotitolo senza tempi per parola viene ritagliato, viene stimata la distribuzione delle parole e conservato soltanto il testo relativo al taglio. I tempi stimati sono marcati e conservati dopo il salvataggio; l’editor invita a controllare l’anteprima. Le pause prive di parole non ripristinano l’intera frase.
- Ripristinato il badge **100% gratuito**, accanto al numero di versione. Anche il numero nella barra laterale viene aggiornato dal motore; gli asset statici includono la versione nell’URL per evitare il riutilizzo di vecchio codice dalla cache.
- Rimossa la vecchia installazione `ClipLab 2` V2.0 dopo aver verificato che non contenesse progetti o credenziali. Tutti i suoi modelli erano identici a quelli della cartella corrente e restano conservati lì.
- Backup del rilascio precedente V2.1.0 in `../backup/ClipLab-V2.1.0`; pacchetti Mac e Windows allineati alla V2.1.1.

Verifiche: **59 test Python** superati sia con le impostazioni normali sia con `CLIPLAB_DATA_DIR` e `CLIPLAB_MODELS_DIR` personalizzati. Test JavaScript di connessione, editor e comportamento delle versioni precedenti su Mac/Windows superati. Prove reali HTTP/FFmpeg su Mac, incluso il ritrovamento di un motore sulla porta 8778, l’avvio contemporaneo di due copie e l’arresto indipendente. I rami Windows sono simulati sul Mac: la verifica nativa su PC Windows resta da eseguire.

## V2.1.0 — 20 novembre 2026

- Aggiunta l’edizione Windows x64 con comandi `.cmd` per configurazione, avvio, preparazione modelli, arresto e diagnostica. I componenti sono installati localmente senza richiedere Python o Node.js già configurati.
- Node.js Windows scaricato dal sito ufficiale con verifica SHA-256 e conservazione della licenza. Verificato anche il contenuto dell’archivio ufficiale del bootstrap uv.
- Blocco tra processi portabile tramite `filelock`, avvio Windows separato dalla console e arresto tramite il server Uvicorn, senza segnali Unix. FFmpeg viene copiato come `ffmpeg.exe` senza richiedere permessi per collegamenti simbolici.
- File di progetto, configurazioni, HTML, sottotitoli e log leggono/scrivono UTF-8 esplicitamente. L’interfaccia usa “computer” e mostra il comando di avvio appropriato al sistema operativo.
- Aggiunto **README.txt** nella cartella e nei pacchetti, con istruzioni per chi riceve l’app, installazione, utilizzo, account, programmazione e risoluzione dei problemi.
- Backup del codice V2.0.1 in `../backup/ClipLab-V2.0.1`, con manifest SHA-256; la rotazione esclude i dati personali.

Verifiche: **52 test Python** superati, test JavaScript superati e prove HTTP/FFmpeg sulla versione condivisa eseguite su Mac, compresi avvio simultaneo di due copie e arresto controllato. Risolte e verificate **63 dipendenze** per Python 3.12 / Windows x64 usando soltanto pacchetti binari. Il download reale del runtime Node Windows è stato verificato con checksum; il relativo eseguibile non è stato eseguito su Mac.

**Limite delle verifiche:** installazione `.cmd`, rendering e pubblicazione nativi su Windows non sono stati eseguiti su un PC Windows reale. Il pacchetto include la diagnostica per la prima installazione. Nessun test pubblica contenuti reali sugli account social.

## V2.0.1 — 20 novembre 2026

Rilascio correttivo dell’audit sulla cartella `ClipLab`. Backup autentico della V2.0 in `../backup/ClipLab-V2.0`, con manifest SHA-256 dei file.

1. **Sottotitoli e ampliamento del taglio:** le parti nuove vengono recuperate dalla trascrizione originale, conservando le correzioni. Gli intervalli già rivisti vengono registrati, così i sottotitoli cancellati volontariamente non ricompaiono. L’editor invia l’intervallo effettivamente rivisto e ricarica la traccia dopo il salvataggio. Per i vecchi progetti privi di questi metadati l’intervallo è dedotto dai sottotitoli salvati; non è possibile ricostruire con certezza eventuali cancellazioni storiche ai margini.
2. **Interruzione:** il segnale di annullamento viene rimosso a fine analisi anche in caso di errore o annullamento. L’interruzione su un progetto inattivo non lascia segnali persistenti. Le attività contemporanee sullo stesso progetto condividono il segnale senza azzerarsi a vicenda.
3. **Upload ripetuto:** `/publish` restituisce HTTP 409 se la clip è già su YouTube, prima di accodare il lavoro. Anche l’uscita idempotente del client ripristina lo stato pubblicato.
4. **Flusso automatico:** un errore di rendering/upload viene registrato sulla singola clip e le successive continuano. L’annullamento volontario interrompe invece l’intero flusso. Il progetto riassume le clip non completate.
5. **Download e HTTP 416:** un `.part` già completo viene verificato e promosso; uno errato viene eliminato e il download riparte senza Range. Con checksum disponibile la sola dimensione non basta.
6. **Video senza parlato:** il titolo della proposta iniziale è limitato a 100 caratteri.
7. **Concorrenza:** editor e coda usano lo stesso blocco per clip. Un lavoro programmato attende la fine dell’esportazione; una pubblicazione in corso impedisce modifiche concorrenti. Il completamento TikTok non fa regredire una clip già pubblicata su YouTube allo stato esportato.
8. **Più copie:** il launcher identifica installazione e cartella dati, riutilizza il relativo motore o sceglie una porta libera. Nessun confronto rigido con il numero `2.0`. I problemi di permessi sulle porte vengono segnalati invece di essere scambiati per porte occupate.
9. **Casi minori:** l’editor termina l’attesa quando la ritrascrizione fallisce o viene rifiutata; una richiesta di ritrascrizione non accettata non invalida la coda; il preparatore modelli rispetta `CLIPLAB_DATA_DIR` e `CLIPLAB_MODELS_DIR`.
10. **Versione:** `version.py` è l’unica fonte. La barra superiore mostra V2.0.1; pagina e API condividono lo stesso valore.

### Verifiche

- 42 test Python superati, inclusi 22 nuovi casi di regressione dell’audit.
- Test JavaScript della connessione e dei casi di ritrascrizione/ampliamento superati; sintassi degli script verificata.
- Due copie temporanee della V2.0.1 avviate contemporaneamente su porte diverse. Fermarne una lascia attiva l’altra.
- Prova HTTP e FFmpeg: taglio esteso da 0–2 a 0–4 secondi, MP4 e SRT con correzioni conservate e testo nella parte nuova, audio presente, durata e risoluzione verificate.
- POST `/publish` duplicato verificato tramite HTTP: risposta 409 e stato pubblicato conservato.

Le prove non hanno pubblicato contenuti reali né usato credenziali personali. Gli invii alle piattaforme sono simulati nei test; le prove HTTP/rendering usano copie e sorgenti temporanee.

## V2.0 — 19 novembre 2026

Editor di inquadratura e sottotitoli, Whisper Small, tracking volti, layout podcast, esportazioni 1080p senza watermark aggiunto e coda locale YouTube/TikTok.
